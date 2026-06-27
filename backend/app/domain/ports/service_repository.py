from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

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
