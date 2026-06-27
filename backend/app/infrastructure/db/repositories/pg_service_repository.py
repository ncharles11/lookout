from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

import asyncpg

from app.domain.alerting.state_machine import AlertStateUpdate
from app.domain.models import Service, ServiceCreate, ServiceState, ServiceType
from app.domain.ports.service_repository import ServiceRepository

_COLUMNS = (
    "id, name, type, target, interval_s, expected_status, "
    "enabled, current_state, created_at, agent_id, "
    "consecutive_failures, consecutive_successes, failure_start"
)

_SELECT_LOCKED = f"SELECT {_COLUMNS} FROM services WHERE id = $1 FOR UPDATE"
_UPDATE_ALERT = """
    UPDATE services
    SET current_state        = $1,
        consecutive_failures  = $2,
        consecutive_successes = $3,
        failure_start        = $4
    WHERE id = $5
"""


class PgServiceRepository(ServiceRepository):
    """asyncpg-backed implementation of the service repository port."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @staticmethod
    def _to_domain(row: asyncpg.Record) -> Service:
        """Map an asyncpg ``Record`` to a domain ``Service`` model."""
        return Service(
            id=row["id"],
            name=row["name"],
            type=ServiceType(row["type"]),
            target=row["target"],
            interval_s=row["interval_s"],
            expected_status=row["expected_status"],
            enabled=row["enabled"],
            current_state=ServiceState(row["current_state"]),
            created_at=row["created_at"],
            consecutive_failures=row["consecutive_failures"],
            consecutive_successes=row["consecutive_successes"],
            failure_start=row["failure_start"],
        )

    async def get_all_enabled(self) -> list[Service]:
        query = f"SELECT {_COLUMNS} FROM services WHERE enabled = TRUE ORDER BY created_at"
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)
        return [self._to_domain(row) for row in rows]

    async def get_all(self) -> list[Service]:
        query = f"SELECT {_COLUMNS} FROM services ORDER BY created_at"
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)
        return [self._to_domain(row) for row in rows]

    async def create(self, data: ServiceCreate) -> Service:
        query = f"""
            INSERT INTO services (name, type, target, interval_s, expected_status, enabled)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING {_COLUMNS}
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                data.name,
                data.type.value,
                data.target,
                data.interval_s,
                data.expected_status,
                data.enabled,
            )
        if row is None:
            raise RuntimeError("Failed to create service: no row returned.")
        return self._to_domain(row)

    async def update_state(self, service_id: UUID, state: ServiceState) -> None:
        query = "UPDATE services SET current_state = $1 WHERE id = $2"
        async with self._pool.acquire() as conn:
            await conn.execute(query, state.value, service_id)

    async def get_by_agent_id(self, agent_id: str) -> Service | None:
        query = f"SELECT {_COLUMNS} FROM services WHERE agent_id = $1"
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, agent_id)
        return self._to_domain(row) if row else None

    async def upsert_push_service(self, agent_id: str) -> Service:
        query = f"""
            INSERT INTO services (name, type, agent_id, enabled, interval_s)
            VALUES ($1, 'push', $2, TRUE, 0)
            ON CONFLICT (agent_id) DO UPDATE SET name = EXCLUDED.name
            RETURNING {_COLUMNS}
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, f"agent:{agent_id}", agent_id)
        if row is None:
            raise RuntimeError(
                f"Failed to upsert push service for agent {agent_id}"
            )
        return self._to_domain(row)

    async def get_by_id(self, service_id: UUID) -> Service | None:
        query = f"SELECT {_COLUMNS} FROM services WHERE id = $1"
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, service_id)
        return self._to_domain(row) if row else None

    async def update_alert_state(
        self,
        service_id: UUID,
        new_state: ServiceState,
        consecutive_failures: int,
        consecutive_successes: int,
        failure_start: datetime | None,
    ) -> None:
        query = """
            UPDATE services
            SET current_state        = $1,
                consecutive_failures  = $2,
                consecutive_successes = $3,
                failure_start        = $4
            WHERE id = $5
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                query,
                new_state.value,
                consecutive_failures,
                consecutive_successes,
                failure_start,
                service_id,
            )

    async def fetch_locked_and_apply(
        self,
        service_id: UUID,
        compute: Callable[[Service], AlertStateUpdate],
    ) -> AlertStateUpdate | None:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(_SELECT_LOCKED, service_id)
                if row is None:
                    return None
                service = self._to_domain(row)
                update = compute(service)  # synchronous FSM — safe inside transaction
                await conn.execute(
                    _UPDATE_ALERT,
                    update.new_state.value,
                    update.consecutive_failures,
                    update.consecutive_successes,
                    update.failure_start,
                    service_id,
                )
        return update
