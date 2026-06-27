from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.models import AgentMetric, Observation


class MetricRepository(ABC):
    """Port for persisting probe observations as time-series metrics."""

    @abstractmethod
    async def save_observation(self, obs: Observation) -> None:
        """Persist a single observation as one or more metric rows."""
        raise NotImplementedError

    @abstractmethod
    async def save_agent_batch(
        self,
        service_id: UUID,
        batch_time: datetime,
        metrics: list[AgentMetric],
    ) -> None:
        """Persist a batch of agent (whitebox) metrics as metric rows."""
        raise NotImplementedError
