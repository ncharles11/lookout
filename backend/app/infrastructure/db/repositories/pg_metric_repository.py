from __future__ import annotations

import json

import asyncpg

from app.domain.models import Observation
from app.domain.ports.metric_repository import MetricRepository

_INSERT_METRIC = """
    INSERT INTO metrics (time, service_id, metric, value, labels)
    VALUES ($1, $2, $3, $4, $5)
"""


class PgMetricRepository(MetricRepository):
    """asyncpg-backed implementation of the metric repository port."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def save_observation(self, obs: Observation) -> None:
        """Persist an observation as two metric rows: latency and up/down."""
        latency_labels = json.dumps({"status_code": obs.status_code})
        up_labels = json.dumps({"status_code": obs.status_code})

        rows = [
            (obs.time, obs.service_id, "latency_ms", obs.latency_ms, latency_labels),
            (
                obs.time,
                obs.service_id,
                "is_up",
                1.0 if obs.is_up else 0.0,
                up_labels,
            ),
        ]

        async with self._pool.acquire() as conn:
            await conn.executemany(_INSERT_METRIC, rows)
