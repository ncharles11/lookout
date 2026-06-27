from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from app.domain.alerting.state_machine import AlertStateUpdate
from app.domain.models import Service, ServiceCreate, ServiceState


class ServiceRepository(ABC):
    """Port for reading and mutating monitored services."""

    @abstractmethod
    async def get_all_enabled(self) -> list[Service]:
        """Return every service whose ``enabled`` flag is true."""
        raise NotImplementedError

    @abstractmethod
    async def create(self, data: ServiceCreate) -> Service:
        """Persist a new service and return the fully materialised record."""
        raise NotImplementedError

    @abstractmethod
    async def get_all(self) -> list[Service]:
        """Return every service, regardless of enabled state."""
        raise NotImplementedError

    @abstractmethod
    async def update_state(self, service_id: UUID, state: ServiceState) -> None:
        """Update the ``current_state`` of the given service."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_agent_id(self, agent_id: str) -> Service | None:
        """Return the push service bound to ``agent_id``, or None if absent."""
        raise NotImplementedError

    @abstractmethod
    async def upsert_push_service(self, agent_id: str) -> Service:
        """Create or return the push service for ``agent_id`` (idempotent)."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, service_id: UUID) -> "Service | None":
        """Fetch a service by primary key, including its window state."""
        raise NotImplementedError

    @abstractmethod
    async def update_alert_state(
        self,
        service_id: UUID,
        new_state: "ServiceState",
        consecutive_failures: int,
        consecutive_successes: int,
        failure_start: "datetime | None",
    ) -> None:
        """Atomically update state + anti-flapping counters."""
        raise NotImplementedError

    @abstractmethod
    async def fetch_locked_and_apply(
        self,
        service_id: UUID,
        compute: Callable[["Service"], AlertStateUpdate],
    ) -> AlertStateUpdate | None:
        """
        Atomically within one asyncpg transaction:
        1. SELECT the service row FOR UPDATE (exclusive row-level lock).
        2. Call compute(service) synchronously — the FSM runs here, inside the lock.
        3. Persist AlertStateUpdate.new_state + window counters.
        Returns the AlertStateUpdate, or None if the service does not exist.
        """
        raise NotImplementedError
