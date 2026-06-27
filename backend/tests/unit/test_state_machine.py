from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.domain.alerting.events import AlertFired, AlertResolved, StateChanged
from app.domain.alerting.sliding_window import WindowConfig, WindowState
from app.domain.alerting.state_machine import transition
from app.domain.models import ServiceState

# ── Fixtures ────────────────────────────────────────────────────────────────

SERVICE_ID: UUID = uuid4()
SERVICE_NAME = "test-svc"
T0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
DEFAULT_CFG = WindowConfig(
    consecutive_failures_to_alert=3,
    failure_duration_s=60.0,
    consecutive_successes_to_resolve=2,
)


def fail(state: ServiceState, window: WindowState, cfg: WindowConfig = DEFAULT_CFG, now: datetime = T0) -> ...:
    return transition(SERVICE_ID, SERVICE_NAME, state, is_breach=True,  is_cleared=False, window=window, cfg=cfg, now=now)


def ok(state: ServiceState, window: WindowState, cfg: WindowConfig = DEFAULT_CFG, now: datetime = T0) -> ...:
    return transition(SERVICE_ID, SERVICE_NAME, state, is_breach=False, is_cleared=True,  window=window, cfg=cfg, now=now)


def hysteresis(state: ServiceState, window: WindowState, cfg: WindowConfig = DEFAULT_CFG, now: datetime = T0) -> ...:
    return transition(SERVICE_ID, SERVICE_NAME, state, is_breach=False, is_cleared=False, window=window, cfg=cfg, now=now)


def has_event(result, event_type: type) -> bool:
    return any(isinstance(e, event_type) for e in result.events)


# ── Test 1: Quick recovery — single failure then success, NO AlertFired ─────

class TestQuickRecovery:
    def test_single_failure_moves_to_warning(self):
        r = fail(ServiceState.UP, WindowState())
        assert r.new_state is ServiceState.WARNING
        assert not has_event(r, AlertFired)

    def test_warning_plus_success_goes_to_up(self):
        r1 = fail(ServiceState.UP, WindowState())
        r2 = ok(ServiceState.WARNING, r1.new_window)
        assert r2.new_state is ServiceState.UP
        assert not has_event(r2, AlertFired)
        assert has_event(r2, StateChanged)

    def test_two_failures_then_success_no_alert(self):
        r1 = fail(ServiceState.UP,      WindowState())
        r2 = fail(ServiceState.WARNING, r1.new_window)
        assert r2.new_state is ServiceState.WARNING
        assert not has_event(r2, AlertFired)

        r3 = ok(ServiceState.WARNING, r2.new_window)
        assert r3.new_state is ServiceState.UP
        assert not has_event(r3, AlertFired)


# ── Test 2: Confirmed failure — UP → WARNING → CRITICAL, AlertFired ─────────

class TestConfirmedFailure:
    def test_three_consecutive_failures_trigger_critical(self):
        r1 = fail(ServiceState.UP,      WindowState())
        assert r1.new_state is ServiceState.WARNING

        r2 = fail(ServiceState.WARNING, r1.new_window)
        assert r2.new_state is ServiceState.WARNING
        assert not has_event(r2, AlertFired)

        r3 = fail(ServiceState.WARNING, r2.new_window)
        assert r3.new_state is ServiceState.CRITICAL
        assert has_event(r3, AlertFired)

    def test_alert_not_repeated_while_already_critical(self):
        r_crit = fail(
            ServiceState.WARNING,
            WindowState(consecutive_failures=2, failure_start=T0),
        )
        assert r_crit.new_state is ServiceState.CRITICAL

        r_stay = fail(ServiceState.CRITICAL, r_crit.new_window)
        assert r_stay.new_state is ServiceState.CRITICAL
        assert not has_event(r_stay, AlertFired)

    def test_critical_requires_consecutive_successes_to_resolve(self):
        r_crit = fail(
            ServiceState.WARNING,
            WindowState(consecutive_failures=2, failure_start=T0),
        )
        assert r_crit.new_state is ServiceState.CRITICAL

        # First success: not enough
        r1 = ok(ServiceState.CRITICAL, r_crit.new_window)
        assert r1.new_state is ServiceState.CRITICAL

        # Second success: resolve
        r2 = ok(ServiceState.CRITICAL, r1.new_window)
        assert r2.new_state is ServiceState.RESOLVED
        assert has_event(r2, AlertResolved)

    def test_resolved_transitions_to_up_on_next_success(self):
        r = ok(ServiceState.RESOLVED, WindowState())
        assert r.new_state is ServiceState.UP
        assert has_event(r, StateChanged)

    def test_resolved_goes_back_to_warning_on_failure(self):
        r = fail(ServiceState.RESOLVED, WindowState())
        assert r.new_state is ServiceState.WARNING
        assert not has_event(r, AlertFired)


# ── Test 3: Hysteresis — oscillation between thresholds does not spam ───────

class TestHysteresis:
    def test_hysteresis_zone_freezes_counters_and_state(self):
        state = ServiceState.CRITICAL
        window = WindowState(consecutive_failures=3, failure_start=T0)

        for _ in range(10):
            r = hysteresis(state, window)
            assert r.new_state is ServiceState.CRITICAL
            assert r.events == []
            # Success counter never advances
            assert r.new_window.consecutive_successes == 0
            state = r.new_state
            window = r.new_window

    def test_resolve_only_after_cleared_signal_not_hysteresis(self):
        state = ServiceState.CRITICAL
        window = WindowState(consecutive_failures=3, failure_start=T0)

        # Oscillate in hysteresis zone — should remain CRITICAL
        for _ in range(5):
            r = hysteresis(state, window)
            state = r.new_state
            window = r.new_window

        assert state is ServiceState.CRITICAL

        # One clear signal: start accumulating successes
        r1 = ok(state, window)
        assert r1.new_state is ServiceState.CRITICAL  # need 2

        # Second clear signal: resolve
        r2 = ok(r1.new_state, r1.new_window)
        assert r2.new_state is ServiceState.RESOLVED
        assert has_event(r2, AlertResolved)

    def test_no_additional_alerts_during_hysteresis_oscillation(self):
        fast_cfg = WindowConfig(
            consecutive_failures_to_alert=1,
            failure_duration_s=9999.0,
            consecutive_successes_to_resolve=1,
        )
        # Reach CRITICAL (2 failures with fast_cfg)
        r1 = fail(ServiceState.UP,      WindowState(), cfg=fast_cfg)
        r2 = fail(ServiceState.WARNING,  r1.new_window, cfg=fast_cfg)
        assert r2.new_state is ServiceState.CRITICAL
        assert has_event(r2, AlertFired)

        # 20 oscillations in hysteresis zone — zero additional alerts
        state, window = r2.new_state, r2.new_window
        extra_alerts = 0
        for _ in range(20):
            r = hysteresis(state, window, cfg=fast_cfg)
            extra_alerts += sum(1 for e in r.events if isinstance(e, AlertFired))
            state, window = r.new_state, r.new_window

        assert extra_alerts == 0
        assert state is ServiceState.CRITICAL

    def test_failure_counter_not_incremented_in_hysteresis(self):
        window = WindowState(consecutive_failures=3, failure_start=T0)
        r = hysteresis(ServiceState.CRITICAL, window)
        assert r.new_window.consecutive_failures == 3  # frozen, not incremented
