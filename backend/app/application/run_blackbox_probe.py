from __future__ import annotations

from app.domain.models import Observation, Service, ServiceState
from app.domain.ports.metric_repository import MetricRepository
from app.domain.ports.service_repository import ServiceRepository
from app.infrastructure.prober.http_tcp_prober import HttpTcpProber


async def run_blackbox_probe(
    service: Service,
    prober: HttpTcpProber,
    metric_repo: MetricRepository,
    service_repo: ServiceRepository,
) -> Observation:
    """Run a single black-box probe cycle for a service.

    Steps:
        1. Probe the service.
        2. Persist the observation as metrics.
        3. Derive and persist the new service state.
        4. Return the observation.
    """
    obs = await prober.probe(service)
    await metric_repo.save_observation(obs)
    new_state = ServiceState.UP if obs.is_up else ServiceState.DOWN
    await service_repo.update_state(service.id, new_state)
    return obs
