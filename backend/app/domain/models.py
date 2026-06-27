from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ServiceType(str, Enum):
    """The kind of probe a service requires."""

    HTTP = "http"
    TCP = "tcp"
    PUSH = "push"  # whitebox: metrics pushed in by a remote agent, not probed


class ServiceState(str, Enum):
    """The last observed health state of a service."""

    UNKNOWN = "UNKNOWN"
    UP = "UP"
    DOWN = "DOWN"  # keep for backward compat; FSM won't produce it
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    RESOLVED = "RESOLVED"


class Service(BaseModel):
    """A monitored target. Pure domain model — no persistence concerns."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    type: ServiceType
    target: str | None = None
    interval_s: int = 60
    expected_status: int | None = 200
    enabled: bool = True
    current_state: ServiceState = ServiceState.UNKNOWN
    created_at: datetime
    # Anti-flapping window state (persisted in DB)
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    failure_start: datetime | None = None


class Observation(BaseModel):
    """A single probe result for a service at a point in time."""

    model_config = ConfigDict(from_attributes=True)

    service_id: UUID
    time: datetime
    latency_ms: float  # -1.0 if unreachable
    status_code: int | None  # None for TCP or failed probes
    is_up: bool
    error: str | None = None


class ServiceCreate(BaseModel):
    """Input payload for registering a new service."""

    name: str
    type: ServiceType
    target: str
    interval_s: int = 60
    expected_status: int | None = 200
    enabled: bool = True


class AgentMetric(BaseModel):
    """A single named measurement reported by a remote (whitebox) agent."""

    name: str  # e.g. "cpu_percent"
    value: float
    labels: dict[str, str | float | int | None] = {}


class MetricBatch(BaseModel):
    """A batch of agent metrics pushed in a single ingestion request."""

    agent_id: str
    timestamp: datetime
    metrics: list[AgentMetric]
