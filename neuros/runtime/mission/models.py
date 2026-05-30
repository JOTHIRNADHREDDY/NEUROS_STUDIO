"""
NEUROS Mission Models

Defines the data structures for missions.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class MissionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class MissionStep:
    skill_name: str
    params: dict[str, Any]
    status: MissionStatus = MissionStatus.PENDING
    task_id: str | None = None
    result: Any = None
    error: str | None = None
    started_at: float | None = None
    completed_at: float | None = None


@dataclass
class Mission:
    goal: str
    mission_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    steps: list[MissionStep] = field(default_factory=list)
    status: MissionStatus = MissionStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    error: str | None = None
    
    @property
    def current_step_index(self) -> int:
        for i, step in enumerate(self.steps):
            if step.status in (MissionStatus.PENDING, MissionStatus.RUNNING):
                return i
        return len(self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "goal": self.goal,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "steps": [
                {
                    "skill_name": s.skill_name,
                    "status": s.status.value,
                    "task_id": s.task_id,
                }
                for s in self.steps
            ],
        }
