from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, TypedDict

from fastapi import FastAPI

from app.api.v1 import services as services_api
from app.config import get_settings
from app.infrastructure.db.repositories.pg_metric_repository import PgMetricRepository
from app.infrastructure.db.repositories.pg_service_repository import (
    PgServiceRepository,
)
from app.infrastructure.db.session import close_pool, get_pool, init_pool
from app.infrastructure.prober.http_tcp_prober import HttpTcpProber
from app.infrastructure.prober.scheduler import ProbeScheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lookout")


class HealthResponse(TypedDict):
    status: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle."""
    settings = get_settings()

    await init_pool()
    pool = get_pool()

    metric_repo = PgMetricRepository(pool)
    service_repo = PgServiceRepository(pool)
    prober = HttpTcpProber()

    scheduler = ProbeScheduler(
        service_repo=service_repo,
        metric_repo=metric_repo,
        prober=prober,
        concurrency=settings.PROBE_CONCURRENCY,
    )

    # Wire the concrete repository into the API layer via dependency override.
    app.dependency_overrides[services_api.get_service_repository] = (
        lambda: service_repo
    )

    await scheduler.start()
    logger.info("Lookout backend started")

    try:
        yield
    finally:
        await scheduler.stop()
        await close_pool()
        logger.info("Lookout backend stopped")


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(title="Lookout", version="0.1.0", lifespan=lifespan)
    app.include_router(services_api.router)

    @app.get("/health")
    async def health() -> HealthResponse:
        return {"status": "ok"}

    return app


app = create_app()
