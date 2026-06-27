from __future__ import annotations

import asyncio
import logging

from app.application.run_blackbox_probe import run_blackbox_probe
from app.domain.alerting.sliding_window import WindowConfig
from app.domain.models import Service
from app.domain.ports.metric_repository import MetricRepository
from app.domain.ports.notifier import Notifier
from app.domain.ports.service_repository import ServiceRepository
from app.infrastructure.prober.http_tcp_prober import HttpTcpProber

logger = logging.getLogger("lookout.scheduler")


class ProbeScheduler:
    """Schedules one perpetual probe loop per enabled service.

    Concurrency across all loops is capped by a semaphore so that no more than
    ``concurrency`` probes execute simultaneously.
    """

    def __init__(
        self,
        service_repo: ServiceRepository,
        metric_repo: MetricRepository,
        prober: HttpTcpProber,
        concurrency: int,
        notifier: Notifier,
        window_cfg: WindowConfig,
    ) -> None:
        self._service_repo = service_repo
        self._metric_repo = metric_repo
        self._prober = prober
        self._semaphore = asyncio.Semaphore(concurrency)
        self._tasks: list[asyncio.Task[None]] = []
        self._stopped = asyncio.Event()
        self._notifier = notifier
        self._window_cfg = window_cfg

    async def start(self) -> None:
        """Load enabled services and spawn a probe loop task for each."""
        services = await self._service_repo.get_all_enabled()
        for service in services:
            task = asyncio.create_task(
                self._run_loop(service),
                name=f"probe-loop:{service.id}",
            )
            self._tasks.append(task)
        logger.info("Started %d probe loop(s)", len(self._tasks))

    async def add_service(self, service: Service) -> None:
        """Dynamically add a probe loop for a newly registered service.

        Push-type services are skipped: they report metrics inbound rather than
        being actively probed.
        """
        if not service.enabled or service.type.value == "push":
            return
        task = asyncio.create_task(
            self._run_loop(service),
            name=f"probe-loop:{service.id}",
        )
        self._tasks.append(task)
        logger.info(
            "Hot-added probe loop for service %s (%s)", service.name, service.id
        )

    async def _run_loop(self, service: Service) -> None:
        """Probe a service forever, sleeping ``interval_s`` between cycles."""
        interval = max(service.interval_s, 1)
        while not self._stopped.is_set():
            try:
                async with self._semaphore:
                    await run_blackbox_probe(
                        service=service,
                        prober=self._prober,
                        metric_repo=self._metric_repo,
                        service_repo=self._service_repo,
                        notifier=self._notifier,
                        window_cfg=self._window_cfg,
                    )
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - never let a loop die on a transient error
                logger.exception("Probe loop error for service %s", service.id)
            await asyncio.sleep(interval)

    async def stop(self) -> None:
        """Cancel all probe loops and wait for them to finish."""
        self._stopped.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("Probe scheduler stopped")
