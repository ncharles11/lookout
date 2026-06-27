from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from app.domain.alerting.events import AlertFired, AlertResolved, StateChanged
from app.domain.alerting.sliding_window import WindowConfig, WindowState
from app.domain.alerting.state_machine import AlertStateUpdate, transition
from app.domain.models import Observation, Service
from app.domain.ports.event_publisher import EventPublisher
from app.domain.ports.notifier import Notifier
from app.domain.ports.service_repository import ServiceRepository

logger = logging.getLogger("lookout.application.evaluate_alerts")


async def evaluate_alerts(
    service_id: UUID,
    service_name: str,
    observation: Observation,
    service_repo: ServiceRepository,
    notifier: Notifier,
    publisher: EventPublisher,
    window_cfg: WindowConfig,
) -> None:
    """Orchestrate the anti-flapping FSM — atomically locked against concurrent probes."""
    now = (
        observation.time
        if observation.time.tzinfo is not None
        else datetime.now(timezone.utc)
    )
    is_breach = not observation.is_up
    is_cleared = observation.is_up

    def compute(service: Service) -> AlertStateUpdate:
        window = WindowState(
            consecutive_failures=service.consecutive_failures,
            consecutive_successes=service.consecutive_successes,
            failure_start=service.failure_start,
        )
        result = transition(
            service_id=service.id,
            service_name=service.name,
            current_state=service.current_state,
            is_breach=is_breach,
            is_cleared=is_cleared,
            window=window,
            cfg=window_cfg,
            now=now,
        )
        return AlertStateUpdate(
            new_state=result.new_state,
            consecutive_failures=result.new_window.consecutive_failures,
            consecutive_successes=result.new_window.consecutive_successes,
            failure_start=result.new_window.failure_start,
            events=list(result.events),
        )

    update = await service_repo.fetch_locked_and_apply(service_id, compute)
    if update is None:
        logger.warning("evaluate_alerts: service %s not found — skipping", service_id)
        return

    for event in update.events:
        # Broadcast every state transition to the WebSocket hub
        await publisher.publish_state_change(event)
        if isinstance(event, AlertFired):
            logger.warning(
                "ALERT FIRED — %s: %s → %s",
                service_name, event.previous_state.value, event.new_state.value,
            )
            await notifier.send_alert(event)
        elif isinstance(event, AlertResolved):
            logger.info("ALERT RESOLVED — %s", service_name)
            await notifier.send_resolve(event)
