from __future__ import annotations

from datetime import timezone

from app.application.evaluate_alerts import evaluate_alerts
from app.domain.alerting.sliding_window import WindowConfig
from app.domain.models import MetricBatch, Observation
from app.domain.ports.metric_repository import MetricRepository
from app.domain.ports.notifier import Notifier
from app.domain.ports.service_repository import ServiceRepository


async def ingest_push_metrics(
    batch: MetricBatch,
    metric_repo: MetricRepository,
    service_repo: ServiceRepository,
    notifier: Notifier,
    window_cfg: WindowConfig,
) -> None:
    """Persist a push metric batch and signal the FSM that the agent is alive."""
    service = await service_repo.upsert_push_service(batch.agent_id)
    await metric_repo.save_agent_batch(
        service_id=service.id,
        batch_time=batch.timestamp,
        metrics=batch.metrics,
    )

    alive_obs = Observation(
        service_id=service.id,
        time=batch.timestamp.replace(tzinfo=timezone.utc)
        if batch.timestamp.tzinfo is None
        else batch.timestamp,
        latency_ms=-1.0,
        status_code=None,
        is_up=True,
        error=None,
    )
    await evaluate_alerts(
        service_id=service.id,
        service_name=service.name,
        observation=alive_obs,
        service_repo=service_repo,
        notifier=notifier,
        window_cfg=window_cfg,
    )
