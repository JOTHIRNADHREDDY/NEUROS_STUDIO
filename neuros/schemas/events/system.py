"""
NEUROS V2 — System Event Schema

Emitted by system-level monitors (health checks, watchdogs, resource
probes) to surface host-level telemetry and diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from neuros.schemas.events.base import BaseEvent, _default_event_id, _default_timestamp


class SystemLevel(str, Enum):
    """Severity levels for system events."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class SystemEvent(BaseEvent):
    """Host-level diagnostic / health event.

    Attributes
    ----------
    component:
        Name of the reporting subsystem (e.g. ``"cpu_monitor"``,
        ``"memory_watchdog"``, ``"thermal_sensor"``).
    level:
        Severity level.
    message:
        Human-readable description of the event.
    cpu_percent:
        CPU utilisation at time of emission (0 – 100).
    memory_percent:
        RAM utilisation at time of emission (0 – 100).
    temperature:
        Board / SoC temperature in °C, or ``None`` when unavailable.
    """

    # -- BaseEvent overrides --
    event_id: str = field(default_factory=_default_event_id)
    timestamp: float = field(default_factory=_default_timestamp)
    event_type: str = field(default="SystemEvent", init=True)
    source: str = "system_monitor"

    # -- Domain fields --
    component: str = ""
    level: SystemLevel = SystemLevel.INFO
    message: str = ""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    temperature: float | None = None
