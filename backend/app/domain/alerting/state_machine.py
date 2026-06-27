from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.alerting.events import AlertEvent, AlertFired, AlertResolved, StateChanged
from app.domain.alerting.sliding_window import (
    WindowConfig,
    WindowState,
    after_failure,
    after_success,
    freeze_window,
    should_alert,
    should_resolve,
)
from app.domain.models import ServiceState


@dataclass(frozen=True)
class TransitionResult:
    new_state: ServiceState
    new_window: WindowState
    events: list[AlertEvent] = field(default_factory=list)


@dataclass(frozen=True)
class AlertStateUpdate:
    """Flattened FSM output consumed by the repository's atomic callback."""
    new_state: ServiceState
    consecutive_failures: int
    consecutive_successes: int
    failure_start: datetime | None
    events: list[AlertEvent] = field(default_factory=list)


def transition(
    service_id: UUID,
    service_name: str,
    current_state: ServiceState,
    is_breach: bool,
    is_cleared: bool,
    window: WindowState,
    cfg: WindowConfig,
    now: datetime,
) -> TransitionResult:
    """Pure FSM transition.

    ``is_breach`` and ``is_cleared`` encode the probe result as a three-way signal:
    - is_breach=True,  is_cleared=False → active failure / above alert threshold
    - is_breach=False, is_cleared=True  → healthy / below resolve threshold
    - is_breach=False, is_cleared=False → hysteresis zone (between thresholds): freeze counters

    They must not both be True.
    """
    if is_breach and is_cleared:
        raise ValueError("is_breach and is_cleared cannot both be True.")

    events: list[AlertEvent] = []

    if is_breach:
        new_window = after_failure(window, now)

        if current_state in (
            ServiceState.UP,
            ServiceState.UNKNOWN,
            ServiceState.DOWN,
            ServiceState.RESOLVED,
        ):
            new_state = ServiceState.WARNING
            events.append(
                StateChanged(
                    service_id=service_id,
                    service_name=service_name,
                    previous_state=current_state,
                    new_state=ServiceState.WARNING,
                    changed_at=now,
                )
            )
        elif current_state is ServiceState.WARNING:
            if should_alert(new_window, cfg, now):
                new_state = ServiceState.CRITICAL
                events.append(
                    AlertFired(
                        service_id=service_id,
                        service_name=service_name,
                        previous_state=ServiceState.WARNING,
                        new_state=ServiceState.CRITICAL,
                        fired_at=now,
                    )
                )
            else:
                new_state = ServiceState.WARNING
        else:
            # CRITICAL: already alerted, stay quiet
            new_state = ServiceState.CRITICAL

    elif is_cleared:
        new_window = after_success(window)

        if current_state in (
            ServiceState.UP,
            ServiceState.UNKNOWN,
            ServiceState.DOWN,
        ):
            new_state = ServiceState.UP
        elif current_state is ServiceState.WARNING:
            new_state = ServiceState.UP
            events.append(
                StateChanged(
                    service_id=service_id,
                    service_name=service_name,
                    previous_state=ServiceState.WARNING,
                    new_state=ServiceState.UP,
                    changed_at=now,
                )
            )
        elif current_state is ServiceState.CRITICAL:
            if should_resolve(new_window, cfg):
                new_state = ServiceState.RESOLVED
                events.append(
                    AlertResolved(
                        service_id=service_id,
                        service_name=service_name,
                        resolved_at=now,
                    )
                )
            else:
                new_state = ServiceState.CRITICAL  # accumulating successes, not yet resolved
        else:
            # RESOLVED → UP on next clear
            new_state = ServiceState.UP
            events.append(
                StateChanged(
                    service_id=service_id,
                    service_name=service_name,
                    previous_state=ServiceState.RESOLVED,
                    new_state=ServiceState.UP,
                    changed_at=now,
                )
            )

    else:
        # Hysteresis zone: neither breach nor cleared — freeze counters, stay in current state
        new_window = freeze_window(window)
        new_state = current_state

    return TransitionResult(new_state=new_state, new_window=new_window, events=events)
