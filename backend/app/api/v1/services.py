from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.domain.models import Service, ServiceCreate
from app.domain.ports.service_repository import ServiceRepository


def get_service_repository() -> ServiceRepository:
    """Dependency provider for the service repository.

    This is overridden at application startup via ``app.dependency_overrides``
    once the concrete, pool-backed repository is available.
    """
    raise NotImplementedError(
        "ServiceRepository dependency is not wired. "
        "Override get_service_repository at startup."
    )


router = APIRouter(prefix="/api/v1", tags=["services"])


@router.post(
    "/config/services",
    response_model=Service,
    status_code=status.HTTP_201_CREATED,
)
async def create_service(
    data: ServiceCreate,
    repo: ServiceRepository = Depends(get_service_repository),
) -> Service:
    """Register a new service to be monitored."""
    return await repo.create(data)


@router.get(
    "/services/status",
    response_model=list[Service],
    status_code=status.HTTP_200_OK,
)
async def get_services_status(
    repo: ServiceRepository = Depends(get_service_repository),
) -> list[Service]:
    """Return all services with their current health state."""
    return await repo.get_all()
