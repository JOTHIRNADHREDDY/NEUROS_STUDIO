"""
NEUROS V2 — Schemas Package

Top-level convenience re-exports for all typed event schemas::

    from neuros.schemas import MotorEvent, BatteryEvent, SkillStatus
"""

from neuros.schemas.events import (
    AgentEvent,
    BaseEvent,
    BatteryEvent,
    CameraEvent,
    MotorEvent,
    NavigationEvent,
    NavigationStatus,
    SkillEvent,
    SkillStatus,
    SystemEvent,
    SystemLevel,
)

__all__: list[str] = [
    # Base
    "BaseEvent",
    # Domain events
    "AgentEvent",
    "BatteryEvent",
    "CameraEvent",
    "MotorEvent",
    "NavigationEvent",
    "SkillEvent",
    "SystemEvent",
    # Enums
    "NavigationStatus",
    "SkillStatus",
    "SystemLevel",
]
