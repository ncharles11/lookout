from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from app.domain.alerting.events import AlertFired, AlertResolved
from app.domain.alerting.sliding_window import WindowConfig, WindowState
from app.domain.alerting.state_machine import transition
from app.domain.models import Observation
from app.domain.ports.notifier import Notifier
from app.domain.ports.service_repository import ServiceRepository

logger = logging.getLogger("lookout.application.evaluate_alerts")


async def evaluate_alerts(
    service_id: UUID,
    service_name: str,
    observation: Observation,
    service_repo: ServiceRepository,
    notifier: Notifier,
    window_cfg: WindowConfig,
) -> None:
    """Orchestrate the anti-flapping FSM for one observation.

    Flow:
    1. Fetch fresh service state + window counters from DB.
    2. Run the pure FSM transition.
    3. Persist the new state + window counters atomically.
    4. Dispatch AlertFired / AlertResolved events to the notifier.
    """
    service = await service_repo.get_by_id(service_id)
    if service is None:
        logger.warning("evaluate_alerts: service %s not found — skipping", service_id)
        return

    window = WindowState(
        consecutive_failures=service.consecutive_failures,
        consecutive_successes=service.consecutive_successes,
        failure_start=service.failure_start,
    )

    # For binary probes (HTTP/TCP): is_breach = failed, is_cleared = succeeded.
    # Both signals are complementary for boolean is_up.
    is_breach = not observation.is_up
    is_cleared = observation.is_up

    now = observation.time if observation.time.tzinfo is not None else datetime.now(timezone.utc)

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

    await service_repo.update_alert_state(
        service_id=service.id,
        new_state=result.new_state,
        consecutive_failures=result.new_window.consecutive_failures,
        consecutive_successes=result.new_window.consecutive_successes,
        failure_start=result.new_window.failure_start,
    )

    for event in result.events:
        if isinstance(event, AlertFired):
            logger.warning(
                "ALERT FIRED — %s: %s → %s",
                service.name, event.previous_state.value, event.new_state.value,
            )
            await notifier.send_alert(event)
        elif isinstance(event, AlertResolved):
            logger.info("ALERT RESOLVED — %s", service.name)
            await notifier.send_resolve(event)
