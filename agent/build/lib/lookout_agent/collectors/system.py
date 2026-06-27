from __future__ import annotations

import psutil

from lookout_agent.models import AgentMetric


def collect_system_metrics() -> list[AgentMetric]:
    """Collect CPU, RAM, and disk usage via psutil."""
    metrics: list[AgentMetric] = []

    # CPU
    cpu = psutil.cpu_percent(interval=1)
    metrics.append(AgentMetric(name="cpu_percent", value=cpu))

    # RAM
    ram = psutil.virtual_memory()
    metrics.append(AgentMetric(name="ram_used_bytes", value=float(ram.used)))
    metrics.append(AgentMetric(name="ram_total_bytes", value=float(ram.total)))
    metrics.append(AgentMetric(name="ram_percent", value=ram.percent))

    # Disk (root partition)
    disk = psutil.disk_usage("/")
    metrics.append(AgentMetric(name="disk_used_bytes", value=float(disk.used)))
    metrics.append(AgentMetric(name="disk_total_bytes", value=float(disk.total)))
    metrics.append(AgentMetric(name="disk_percent", value=disk.percent))

    return metrics
