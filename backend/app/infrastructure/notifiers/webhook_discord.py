from __future__ import annotations

import logging

import httpx

from app.domain.alerting.events import AlertFired, AlertResolved
from app.domain.ports.notifier import Notifier

logger = logging.getLogger("lookout.notifiers.discord")

_COLOR_CRITICAL = 0xE74C3C   # red
_COLOR_RESOLVED = 0x2ECC71   # green


class DiscordWebhookNotifier(Notifier):
    """Sends rich Discord embeds via an incoming webhook URL."""

    def __init__(self, webhook_url: str) -> None:
        self._url = webhook_url

    async def send_alert(self, event: AlertFired) -> None:
        payload = {
            "embeds": [
                {
                    "title": f"🚨 ALERT — {event.service_name}",
                    "description": (
                        f"Service **{event.service_name}** transitioned "
                        f"`{event.previous_state.value}` → `{event.new_state.value}`"
                    ),
                    "color": _COLOR_CRITICAL,
                    "fields": [
                        {"name": "Service ID", "value": str(event.service_id), "inline": True},
                        {"name": "State",      "value": event.new_state.value,  "inline": True},
                    ],
                    "footer": {"text": f"Fired at {event.fired_at.isoformat()}"},
                }
            ]
        }
        await self._post(payload)

    async def send_resolve(self, event: AlertResolved) -> None:
        payload = {
            "embeds": [
                {
                    "title": f"✅ RESOLVED — {event.service_name}",
                    "description": f"Service **{event.service_name}** has recovered.",
                    "color": _COLOR_RESOLVED,
                    "fields": [
                        {"name": "Service ID", "value": str(event.service_id), "inline": True},
                    ],
                    "footer": {"text": f"Resolved at {event.resolved_at.isoformat()}"},
                }
            ]
        }
        await self._post(payload)

    async def _post(self, payload: dict[str, object]) -> None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._url, json=payload)
                resp.raise_for_status()
        except Exception:
            logger.exception("Discord webhook delivery failed")
