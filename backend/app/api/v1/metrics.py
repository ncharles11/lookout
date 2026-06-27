from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import verify_agent_token
from app.api.v1.services import get_service_repository
from app.application.ingest_push_metrics import ingest_push_metrics
from app.domain.models import MetricBatch
from app.domain.ports.metric_repository import MetricRepository
from app.domain.ports.service_repository import ServiceRepository


def get_metric_repository() -> MetricRepository:
    """Dependency provider for the metric repository.

    Overridden at application startup via ``app.dependency_overrides``.
    """
    raise NotImplementedError("MetricRepository dependency not wired.")


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
) -> None:
    """Receive a metric batch from a remote agent."""
    await ingest_push_metrics(batch, metric_repo, service_repo)
