from __future__ import annotations

from app.domain.alerting.events import AlertFired, AlertResolved
from app.domain.ports.notifier import Notifier


class NoOpNotifier(Notifier):
    """Silent notifier used when no webhook URL is configured."""

    async def send_alert(self, event: AlertFired) -> None:
        pass

    async def send_resolve(self, event: AlertResolved) -> None:
        pass
