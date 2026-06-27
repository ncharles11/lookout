from __future__ import annotations

from uuid import UUID

import asyncpg

from app.domain.models import Service, ServiceCreate, ServiceState, ServiceType
from app.domain.ports.service_repository import ServiceRepository

_COLUMNS = (
    "id, name, type, target, interval_s, expected_status, "
    "enabled, current_state, created_at"
)


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
