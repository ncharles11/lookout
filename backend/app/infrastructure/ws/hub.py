from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import WebSocket

from app.domain.alerting.events import AlertEvent, AlertFired, AlertResolved, StateChanged
from app.domain.ports.event_publisher import EventPublisher

logger = logging.getLogger("lookout.ws.hub")


class ConnectionManager:
    """Thread-safe (asyncio) registry of active WebSocket connections."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)
        logger.info("WS client connected — total: %d", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)
        logger.info("WS client disconnected — total: %d", len(self._connections))

    async def broadcast(self, payload: dict[str, Any]) -> None:
        if not self._connections:
            return
        message = json.dumps(payload, default=str)
        dead: set[WebSocket] = set()
        for ws in set(self._connections):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        self._connections -= dead


class WebSocketHub(EventPublisher):
    """EventPublisher adapter that fans out domain events to all WS clients."""

    def __init__(self, manager: ConnectionManager) -> None:
        self._manager = manager

    async def publish_state_change(self, event: AlertEvent) -> None:
        await self._manager.broadcast(self._serialize(event))

    @staticmethod
    def _serialize(event: AlertEvent) -> dict[str, Any]:
        base: dict[str, Any] = {
            "type": "state_change",
            "service_id": str(event.service_id),
            "service_name": event.service_name,
        }
        if isinstance(event, AlertFired):
            return {
                **base,
                "new_state": event.new_state.value,
                "previous_state": event.previous_state.value,
                "fired_at": event.fired_at.isoformat(),
            }
        if isinstance(event, AlertResolved):
            return {**base, "new_state": "RESOLVED", "resolved_at": event.resolved_at.isoformat()}
        if isinstance(event, StateChanged):
            return {
                **base,
                "new_state": event.new_state.value,
                "previous_state": event.previous_state.value,
                "changed_at": event.changed_at.isoformat(),
            }
        return base
