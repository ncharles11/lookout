from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AgentMetric(BaseModel):
    name: str
    value: float
    labels: dict[str, str | float | int | None] = {}


class MetricBatch(BaseModel):
    agent_id: str
    timestamp: datetime
    metrics: list[AgentMetric]
