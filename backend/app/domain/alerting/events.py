from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.models import ServiceState


@dataclass(frozen=True)
class AlertFired:
    """Emitted when a service transitions into CRITICAL state."""
    service_id: UUID
    service_name: str
    previous_state: ServiceState
    new_state: ServiceState       # always CRITICAL
    fired_at: datetime


@dataclass(frozen=True)
class AlertResolved:
    """Emitted when a service transitions out of CRITICAL into RESOLVED."""
    service_id: UUID
    service_name: str
    resolved_at: datetime


@dataclass(frozen=True)
class StateChanged:
    """Emitted on any non-alert state transition (UP↔WARNING, RESOLVED→UP, etc.)."""
    service_id: UUID
    service_name: str
    previous_state: ServiceState
    new_state: ServiceState
    changed_at: datetime


AlertEvent = AlertFired | AlertResolved | StateChanged
