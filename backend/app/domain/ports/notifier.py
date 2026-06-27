from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.alerting.events import AlertFired, AlertResolved


class Notifier(ABC):
    """Port for dispatching alert notifications to external channels."""

    @abstractmethod
    async def send_alert(self, event: AlertFired) -> None:
        """Send a CRITICAL alert notification."""
        raise NotImplementedError

    @abstractmethod
    async def send_resolve(self, event: AlertResolved) -> None:
        """Send an alert-resolved notification."""
        raise NotImplementedError
