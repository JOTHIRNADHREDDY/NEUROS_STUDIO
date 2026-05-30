"""
NEUROS V2 — Events Package

Re-exports every concrete event class and status/level enums so
consumers can do::

    from neuros.schemas.events import MotorEvent, SkillStatus
"""

from neuros.schemas.events.agent import AgentEvent
from neuros.schemas.events.base import BaseEvent
from neuros.schemas.events.battery import BatteryEvent
from neuros.schemas.events.camera import CameraEvent
from neuros.schemas.events.motor import MotorEvent
from neuros.schemas.events.navigation import NavigationEvent, NavigationStatus
from neuros.schemas.events.skill import SkillEvent, SkillStatus
from neuros.schemas.events.system import SystemEvent, SystemLevel

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
