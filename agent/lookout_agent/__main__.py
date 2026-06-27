from __future__ import annotations

import asyncio
import logging
import signal
from datetime import datetime, timezone

from lookout_agent.collectors.containers import collect_container_metrics
from lookout_agent.collectors.system import collect_system_metrics
from lookout_agent.config import AgentSettings
from lookout_agent.models import MetricBatch
from lookout_agent.transport import MetricTransport

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("lookout_agent")


async def run(settings: AgentSettings) -> None:
    loop = asyncio.get_running_loop()
    shutdown = asyncio.Event()

    def _request_shutdown() -> None:
        if not shutdown.is_set():
            shutdown.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _request_shutdown)

    transport = MetricTransport(settings)
    logger.info(
        "Agent %s started — pushing to %s every %ds",
        settings.AGENT_ID,
        settings.BACKEND_URL,
        settings.COLLECT_INTERVAL_S,
    )

    while not shutdown.is_set():
        try:
            metrics = collect_system_metrics()
            if settings.ENABLE_DOCKER:
                metrics += collect_container_metrics()

            batch = MetricBatch(
                agent_id=settings.AGENT_ID,
                timestamp=datetime.now(timezone.utc),
                metrics=metrics,
            )
            await transport.send(batch)
        except Exception:
            logger.exception("Unexpected error in collection loop")

        # Wait for the next tick — returns early if shutdown is requested
        try:
            await asyncio.wait_for(shutdown.wait(), timeout=settings.COLLECT_INTERVAL_S)
        except asyncio.TimeoutError:
            pass

    logger.info("Agent shutting down...")


def main() -> None:
    settings = AgentSettings()
    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
