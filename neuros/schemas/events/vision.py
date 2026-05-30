"""
NEUROS V2 — Vision Event Schema
"""

from __future__ import annotations

from dataclasses import dataclass, field
from neuros.schemas.events.base import BaseEvent, _default_event_id, _default_timestamp

@dataclass
class VisionEvent(BaseEvent):
    event_id: str = field(default_factory=_default_event_id)
    timestamp: float = field(default_factory=_default_timestamp)
    event_type: str = field(default="VisionEvent", init=True)
    source: str = "vision_worker"
    
    version: str = "1.0"
    object: str = ""
    confidence: float = 0.0
    x: float = 0.0
    y: float = 0.0
