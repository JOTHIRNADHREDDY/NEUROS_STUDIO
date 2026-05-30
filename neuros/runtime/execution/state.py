"""
NEUROS Execution State

Defines the state and priority models for execution tasks.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any


class TaskStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    RETRYING = "retrying"


class TaskPriority(IntEnum):
    """Lower number = higher priority."""
    EMERGENCY = 0
    CRITICAL = 10
    HIGH = 20
    NORMAL = 50
    LOW = 80
    BACKGROUND = 100


@dataclass
class TaskEntry:
    """A single task in the execution queue."""
    skill_name: str
    params: dict[str, Any]
    skill_version: str = "v1"
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.QUEUED
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    result: Any = None
    error: str | None = None
    retries: int = 0
    max_retries: int = 2
    timeout_s: float = 30.0
    source: str = "user"

    @property
    def elapsed_ms(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.completed_at or time.time()
        return (end - self.started_at) * 1000

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "skill_name": self.skill_name,
            "skill_version": self.skill_version,
            "priority": self.priority.name,
            "status": self.status.value,
            "elapsed_ms": self.elapsed_ms,
            "retries": self.retries,
            "error": self.error,
            "source": self.source,
        }
