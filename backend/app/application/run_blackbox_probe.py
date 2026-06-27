from __future__ import annotations

from app.application.evaluate_alerts import evaluate_alerts
from app.domain.alerting.sliding_window import WindowConfig
from app.domain.models import Observation, Service
from app.domain.ports.event_publisher import EventPublisher
from app.domain.ports.metric_repository import MetricRepository
from app.domain.ports.notifier import Notifier
from app.domain.ports.service_repository import ServiceRepository
from app.infrastructure.prober.http_tcp_prober import HttpTcpProber


async def run_blackbox_probe(
    service: Service,
    prober: HttpTcpProber,
    metric_repo: MetricRepository,
    service_repo: ServiceRepository,
    notifier: Notifier,
    publisher: EventPublisher,
    window_cfg: WindowConfig,
) -> Observation:
    """Run one blackbox probe cycle: probe → persist → evaluate FSM."""
    obs = await prober.probe(service)
    await metric_repo.save_observation(obs)
    await evaluate_alerts(
        service_id=service.id,
        service_name=service.name,
        observation=obs,
        service_repo=service_repo,
        notifier=notifier,
        publisher=publisher,
        window_cfg=window_cfg,
    )
    return obs
