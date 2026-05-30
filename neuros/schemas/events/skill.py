"""
NEUROS V2 — Skill Event Schema

Emitted by the skill execution pipeline as skills transition through
their lifecycle: QUEUED → RUNNING → COMPLETED / FAILED / CANCELLED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from neuros.schemas.events.base import BaseEvent, _default_event_id, _default_timestamp


class SkillStatus(str, Enum):
    """Lifecycle states for a skill invocation."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class SkillEvent(BaseEvent):
    """Tracks the lifecycle of a single skill execution.

    Attributes
    ----------
    skill_id:
        Unique identifier for this particular invocation.
    skill_name:
        Registered name of the skill (e.g. ``"move_forward"``).
    version:
        Semantic version of the skill implementation.
    status:
        Current lifecycle phase.
    parameters:
        Input parameters passed to the skill.
    result:
        Output payload (populated after completion or failure).
    duration_ms:
        Wall-clock execution time in milliseconds.  ``None`` while
        the skill is still running.
    """

    # -- BaseEvent overrides --
    event_id: str = field(default_factory=_default_event_id)
    timestamp: float = field(default_factory=_default_timestamp)
    event_type: str = field(default="SkillEvent", init=True)
    source: str = "skill_executor"

    # -- Domain fields --
    skill_id: str = ""
    skill_name: str = ""
    version: str = "1.0.0"
    status: SkillStatus = SkillStatus.QUEUED
    parameters: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    duration_ms: float | None = None
