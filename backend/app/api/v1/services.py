from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.domain.models import Service, ServiceCreate
from app.domain.ports.service_repository import ServiceRepository
from app.infrastructure.prober.scheduler import ProbeScheduler


def get_service_repository() -> ServiceRepository:
    """Dependency provider for the service repository.

    This is overridden at application startup via ``app.dependency_overrides``
    once the concrete, pool-backed repository is available.
    """
    raise NotImplementedError(
        "ServiceRepository dependency is not wired. "
        "Override get_service_repository at startup."
    )


def get_scheduler() -> ProbeScheduler:
    """Dependency provider for the probe scheduler.

    Overridden at application startup via ``app.dependency_overrides``.
    """
    raise NotImplementedError("ProbeScheduler dependency not wired.")


router = APIRouter(prefix="/api/v1", tags=["services"])


@router.post(
    "/config/services",
    response_model=Service,
    status_code=status.HTTP_201_CREATED,
)
async def create_service(
    data: ServiceCreate,
    repo: Annotated[ServiceRepository, Depends(get_service_repository)],
    scheduler: Annotated[ProbeScheduler, Depends(get_scheduler)],
) -> Service:
    """Register a new service to be monitored and start probing it live."""
    service = await repo.create(data)
    await scheduler.add_service(service)
    return service


@router.get(
    "/services/status",
    response_model=list[Service],
    status_code=status.HTTP_200_OK,
)
async def get_services_status(
    repo: Annotated[ServiceRepository, Depends(get_service_repository)],
) -> list[Service]:
    """Return all services with their current health state."""
    return await repo.get_all()
