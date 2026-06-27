from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import verify_agent_token
from app.api.v1.services import get_service_repository
from app.application.ingest_push_metrics import ingest_push_metrics
from app.domain.alerting.sliding_window import WindowConfig
from app.domain.models import MetricBatch
from app.domain.ports.event_publisher import EventPublisher
from app.domain.ports.metric_repository import MetricRepository
from app.domain.ports.notifier import Notifier
from app.domain.ports.service_repository import ServiceRepository


def get_metric_repository() -> MetricRepository:
    """Dependency provider for the metric repository.

    Overridden at application startup via ``app.dependency_overrides``.
    """
    raise NotImplementedError("MetricRepository dependency not wired.")


def get_notifier() -> Notifier:
    """Dependency provider for the notifier.

    Overridden at application startup via ``app.dependency_overrides``.
    """
    raise NotImplementedError("Notifier dependency not wired.")


def get_window_config() -> WindowConfig:
    """Dependency provider for the anti-flapping window config.

    Overridden at application startup via ``app.dependency_overrides``.
    """
    raise NotImplementedError("WindowConfig dependency not wired.")


def get_publisher() -> EventPublisher:
    """Dependency provider for the event publisher (WebSocket hub).

    Overridden at application startup via ``app.dependency_overrides``.
    """
    raise NotImplementedError("EventPublisher dependency not wired.")


router = APIRouter(prefix="/api/v1", tags=["metrics"])


@router.post(
    "/metrics/push",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def push_metrics(
    batch: MetricBatch,
    agent_id: Annotated[str, Depends(verify_agent_token)],
    metric_repo: Annotated[MetricRepository, Depends(get_metric_repository)],
    service_repo: Annotated[ServiceRepository, Depends(get_service_repository)],
    notifier: Annotated[Notifier, Depends(get_notifier)],
    publisher: Annotated[EventPublisher, Depends(get_publisher)],
    window_cfg: Annotated[WindowConfig, Depends(get_window_config)],
) -> None:
    """Receive a metric batch from a remote agent."""
    await ingest_push_metrics(
        batch, metric_repo, service_repo, notifier, publisher, window_cfg
    )
