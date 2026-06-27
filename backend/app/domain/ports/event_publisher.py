from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.alerting.events import AlertEvent


class EventPublisher(ABC):
    """Port for broadcasting domain events to connected real-time clients."""

    @abstractmethod
    async def publish_state_change(self, event: AlertEvent) -> None:
        """Broadcast a state-change event to all connected subscribers."""
        raise NotImplementedError
