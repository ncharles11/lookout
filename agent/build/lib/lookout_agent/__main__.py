from __future__ import annotations

import asyncio
import logging
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


async def run_collection_loop(settings: AgentSettings) -> None:
    transport = MetricTransport(settings)
    logger.info(
        "Agent %s started — pushing to %s every %ds",
        settings.AGENT_ID,
        settings.BACKEND_URL,
        settings.COLLECT_INTERVAL_S,
    )
    while True:
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

        await asyncio.sleep(settings.COLLECT_INTERVAL_S)


def main() -> None:
    settings = AgentSettings()
    asyncio.run(run_collection_loop(settings))


if __name__ == "__main__":
    main()
