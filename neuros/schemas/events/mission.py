"""
NEUROS V2 — Mission Event Schema
"""

from __future__ import annotations

from dataclasses import dataclass, field
from neuros.schemas.events.base import BaseEvent, _default_event_id, _default_timestamp

@dataclass
class MissionEvent(BaseEvent):
    event_id: str = field(default_factory=_default_event_id)
    timestamp: float = field(default_factory=_default_timestamp)
    event_type: str = field(default="MissionEvent", init=True)
    source: str = "mission_manager"
    
    version: str = "1.0"
    mission_id: str = ""
    status: str = ""
    goal: str = ""
