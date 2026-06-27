from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.models import Observation


class MetricRepository(ABC):
    """Port for persisting probe observations as time-series metrics."""

    @abstractmethod
    async def save_observation(self, obs: Observation) -> None:
        """Persist a single observation as one or more metric rows."""
        raise NotImplementedError
