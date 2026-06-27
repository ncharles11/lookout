from __future__ import annotations

import asyncio
import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.api.v1.services import get_service_repository
from app.domain.ports.service_repository import ServiceRepository
from app.infrastructure.ws.hub import ConnectionManager

logger = logging.getLogger("lookout.api.ws")


def get_connection_manager() -> ConnectionManager:
    """Overridden at startup with the shared ConnectionManager singleton."""
    raise NotImplementedError("ConnectionManager dependency not wired.")


router = APIRouter()


@router.websocket("/ws/v1/dashboard")
async def dashboard_ws(
    websocket: WebSocket,
    manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    service_repo: Annotated[ServiceRepository, Depends(get_service_repository)],
) -> None:
    """WebSocket endpoint: sends a snapshot on connect, then streams state_change events."""
    await manager.connect(websocket)
    try:
        # ── Initial snapshot ──────────────────────────────────────────────
        services = await service_repo.get_all()
        snapshot = {
            "type": "snapshot",
            "services": [
                {
                    "id": str(s.id),
                    "name": s.name,
                    "type": s.type.value,
                    "target": s.target,
                    "current_state": s.current_state.value,
                    "interval_s": s.interval_s,
                    "enabled": s.enabled,
                }
                for s in services
            ],
        }
        await websocket.send_text(json.dumps(snapshot))

        # ── Keep-alive loop ────────────────────────────────────────────────
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_text('{"type":"ping"}')
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WS error — closing connection")
    finally:
        manager.disconnect(websocket)
