from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class WindowConfig:
    """Configures anti-flapping thresholds for the sliding window."""
    consecutive_failures_to_alert: int = 3
    failure_duration_s: float = 60.0
    consecutive_successes_to_resolve: int = 2


@dataclass(frozen=True)
class WindowState:
    """Immutable snapshot of the anti-flapping counter state for a single service."""
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    failure_start: datetime | None = None


def after_failure(state: WindowState, now: datetime) -> WindowState:
    """Advance the window after a failed probe."""
    return WindowState(
        consecutive_failures=state.consecutive_failures + 1,
        consecutive_successes=0,
        failure_start=state.failure_start if state.failure_start is not None else now,
    )


def after_success(state: WindowState) -> WindowState:
    """Advance the window after a successful probe."""
    return WindowState(
        consecutive_failures=0,
        consecutive_successes=state.consecutive_successes + 1,
        failure_start=None,
    )


def freeze_window(state: WindowState) -> WindowState:
    """Neither failure nor recovery: hysteresis zone. Reset success counter, keep failure tracking."""
    return WindowState(
        consecutive_failures=state.consecutive_failures,
        consecutive_successes=0,
        failure_start=state.failure_start,
    )


def should_alert(state: WindowState, cfg: WindowConfig, now: datetime) -> bool:
    """True when the window has accumulated enough evidence to fire a CRITICAL alert."""
    if state.consecutive_failures >= cfg.consecutive_failures_to_alert:
        return True
    if state.failure_start is not None:
        elapsed = (now - state.failure_start).total_seconds()
        return elapsed >= cfg.failure_duration_s
    return False


def should_resolve(state: WindowState, cfg: WindowConfig) -> bool:
    """True when enough consecutive successes have accumulated to resolve CRITICAL."""
    return state.consecutive_successes >= cfg.consecutive_successes_to_resolve
