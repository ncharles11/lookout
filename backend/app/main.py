from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from typing_extensions import TypedDict

from app.api.v1 import metrics as metrics_api
from app.api.v1 import services as services_api
from app.api.v1 import ws as ws_api
from app.config import get_settings
from app.domain.alerting.sliding_window import WindowConfig
from app.infrastructure.db.repositories.pg_metric_repository import PgMetricRepository
from app.infrastructure.db.repositories.pg_service_repository import PgServiceRepository
from app.infrastructure.db.session import close_pool, get_pool, init_pool
from app.infrastructure.notifiers.noop_notifier import NoOpNotifier
from app.infrastructure.notifiers.webhook_discord import DiscordWebhookNotifier
from app.infrastructure.prober.http_tcp_prober import HttpTcpProber
from app.infrastructure.prober.scheduler import ProbeScheduler
from app.infrastructure.ws.hub import ConnectionManager, WebSocketHub

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lookout")


class HealthResponse(TypedDict):
    status: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    await init_pool()
    pool = get_pool()

    metric_repo = PgMetricRepository(pool)
    service_repo = PgServiceRepository(pool)
    prober = HttpTcpProber()

    notifier = (
        DiscordWebhookNotifier(settings.DISCORD_WEBHOOK_URL)
        if settings.DISCORD_WEBHOOK_URL
        else NoOpNotifier()
    )
    window_cfg = WindowConfig(
        consecutive_failures_to_alert=settings.ALERT_CONSECUTIVE_FAILURES,
        failure_duration_s=settings.ALERT_FAILURE_DURATION_S,
        consecutive_successes_to_resolve=settings.ALERT_CONSECUTIVE_SUCCESSES,
    )

    # WebSocket hub (singleton connection manager + publisher adapter)
    ws_manager = ConnectionManager()
    publisher = WebSocketHub(ws_manager)

    scheduler = ProbeScheduler(
        service_repo=service_repo,
        metric_repo=metric_repo,
        prober=prober,
        concurrency=settings.PROBE_CONCURRENCY,
        notifier=notifier,
        window_cfg=window_cfg,
        publisher=publisher,
    )

    app.dependency_overrides[services_api.get_service_repository] = lambda: service_repo
    app.dependency_overrides[services_api.get_scheduler]          = lambda: scheduler
    app.dependency_overrides[metrics_api.get_metric_repository]   = lambda: metric_repo
    app.dependency_overrides[metrics_api.get_notifier]            = lambda: notifier
    app.dependency_overrides[metrics_api.get_window_config]       = lambda: window_cfg
    app.dependency_overrides[metrics_api.get_publisher]           = lambda: publisher
    app.dependency_overrides[ws_api.get_connection_manager]       = lambda: ws_manager

    await scheduler.start()
    logger.info("Lookout backend started — WS hub ready")

    try:
        yield
    finally:
        await scheduler.stop()
        await close_pool()
        logger.info("Lookout backend stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="Lookout", version="0.1.0", lifespan=lifespan)
    app.include_router(services_api.router)
    app.include_router(metrics_api.router)
    app.include_router(ws_api.router)

    @app.get("/health")
    async def health() -> HealthResponse:
        return {"status": "ok"}

    return app


app = create_app()
