"""
NEUROS V2 — Motor Event Schema

Emitted whenever the execution manager dispatches a motor command through
the HAL, or when the motor driver reports back telemetry.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from neuros.schemas.events.base import BaseEvent, _default_event_id, _default_timestamp


@dataclass
class MotorEvent(BaseEvent):
    """Represents a motor command or telemetry reading.

    Attributes
    ----------
    motor_id:
        Logical name of the motor (e.g. ``"left_drive"``, ``"right_drive"``).
    speed:
        Normalised speed value (0.0 – 1.0).
    direction:
        Human-readable direction label (``"forward"``, ``"reverse"``,
        ``"stopped"``).
    pwm:
        Raw PWM duty-cycle value sent to the motor driver.
        *Python never controls PWM loops directly* — this is the
        value passed through the HAL for the real-time controller
        to apply.
    current_draw:
        Measured motor current in amps.
    """

    # -- BaseEvent overrides --
    event_id: str = field(default_factory=_default_event_id)
    timestamp: float = field(default_factory=_default_timestamp)
    event_type: str = field(default="MotorEvent", init=True)
    source: str = "motor_controller"

    # -- Domain fields --
    motor_id: str = ""
    speed: float = 0.0
    direction: str = "stopped"
    pwm: int = 0
    current_draw: float = 0.0
