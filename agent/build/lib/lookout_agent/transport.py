from __future__ import annotations

import asyncio
import logging

import httpx

from lookout_agent.config import AgentSettings
from lookout_agent.models import MetricBatch

logger = logging.getLogger("lookout_agent.transport")

_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0  # seconds


class MetricTransport:
    def __init__(self, settings: AgentSettings) -> None:
        self._url = f"{settings.BACKEND_URL.rstrip('/')}/api/v1/metrics/push"
        self._headers = {
            "Authorization": f"Bearer {settings.API_KEY}",
            "Content-Type": "application/json",
        }

    async def send(self, batch: MetricBatch) -> None:
        """POST the batch to the backend with exponential backoff retry."""
        payload = batch.model_dump_json()
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        self._url, content=payload, headers=self._headers
                    )
                resp.raise_for_status()
                logger.debug("Batch sent (%d metrics)", len(batch.metrics))
                return
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "HTTP %s on attempt %d: %s",
                    exc.response.status_code,
                    attempt,
                    exc,
                )
            except Exception as exc:
                logger.warning("Transport error on attempt %d: %s", attempt, exc)
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_BACKOFF_BASE**attempt)
        logger.error("Failed to send batch after %d attempts", _MAX_RETRIES)
