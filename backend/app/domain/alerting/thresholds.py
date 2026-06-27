from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThresholdConfig:
    """Hysteresis threshold pair for a continuous metric (e.g. cpu_percent)."""
    alert_threshold: float    # value >= this → in breach
    resolve_threshold: float  # value <  this → cleared (must be < alert_threshold)

    def __post_init__(self) -> None:
        if self.resolve_threshold >= self.alert_threshold:
            raise ValueError(
                f"resolve_threshold ({self.resolve_threshold}) must be "
                f"strictly less than alert_threshold ({self.alert_threshold})"
            )


def is_in_breach(value: float, cfg: ThresholdConfig) -> bool:
    """True when the value has crossed the alert threshold upward."""
    return value >= cfg.alert_threshold


def is_cleared(value: float, cfg: ThresholdConfig) -> bool:
    """True when the value has fallen below the resolve threshold (hysteresis gap satisfied)."""
    return value < cfg.resolve_threshold
