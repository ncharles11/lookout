from __future__ import annotations

import logging

from lookout_agent.models import AgentMetric

logger = logging.getLogger("lookout_agent.containers")


def collect_container_metrics() -> list[AgentMetric]:
    """Collect Docker container statuses. Returns [] if Docker is unavailable."""
    try:
        import docker  # type: ignore[import]

        client = docker.from_env()
        containers = client.containers.list(all=True)
    except Exception as exc:
        logger.debug("Docker unavailable: %s", exc)
        return []

    metrics: list[AgentMetric] = []
    for c in containers:
        is_running = 1.0 if c.status == "running" else 0.0
        metrics.append(
            AgentMetric(
                name="container_running",
                value=is_running,
                labels={
                    "container_name": c.name,
                    "image": c.image.tags[0] if c.image.tags else "unknown",
                },
            )
        )
    return metrics
