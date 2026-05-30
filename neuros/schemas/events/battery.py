"""
NEUROS V2 — Battery Event Schema

Emitted by the power-management subsystem whenever a telemetry reading
is received from the battery monitor IC or simulator.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from neuros.schemas.events.base import BaseEvent, _default_event_id, _default_timestamp


@dataclass
class BatteryEvent(BaseEvent):
    """Snapshot of the robot's battery state.

    Attributes
    ----------
    voltage:
        Current battery terminal voltage (V).
    current:
        Instantaneous current draw (A).  Positive = discharging.
    percentage:
        Estimated state-of-charge (0 – 100 %).
    is_charging:
        ``True`` if an external charger is connected and active.
    is_critical:
        ``True`` if voltage has fallen below the critical threshold
        defined in ``safety.yaml → limits.battery.critical_voltage``.
    """

    # -- BaseEvent overrides --
    event_id: str = field(default_factory=_default_event_id)
    timestamp: float = field(default_factory=_default_timestamp)
    event_type: str = field(default="BatteryEvent", init=True)
    source: str = "battery_monitor"

    # -- Domain fields --
    voltage: float = 0.0
    current: float = 0.0
    percentage: float = 100.0
    is_charging: bool = False
    is_critical: bool = False
