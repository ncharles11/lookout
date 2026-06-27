from __future__ import annotations

from app.domain.models import MetricBatch
from app.domain.ports.metric_repository import MetricRepository
from app.domain.ports.service_repository import ServiceRepository


async def ingest_push_metrics(
    batch: MetricBatch,
    metric_repo: MetricRepository,
    service_repo: ServiceRepository,
) -> None:
    """Persist a push metric batch from a remote agent.

    1. Resolve (or auto-create) the push service for this agent.
    2. Write all metrics into the hypertable.
    """
    service = await service_repo.upsert_push_service(batch.agent_id)
    await metric_repo.save_agent_batch(
        service_id=service.id,
        batch_time=batch.timestamp,
        metrics=batch.metrics,
    )
