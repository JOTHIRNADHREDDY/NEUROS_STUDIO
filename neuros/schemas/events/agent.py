"""
NEUROS V2 — Agent Event Schema

Emitted whenever an AI agent (planner, robotics, vision, memory, code)
receives intent, produces reasoning, and returns a response.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from neuros.schemas.events.base import BaseEvent, _default_event_id, _default_timestamp


@dataclass
class AgentEvent(BaseEvent):
    """Records a single agent inference cycle.

    Attributes
    ----------
    agent_id:
        Unique identifier for the agent instance.
    agent_type:
        Kind of agent (``"planner"``, ``"robotics"``, ``"vision"``,
        ``"memory"``, ``"code"``).
    action:
        The high-level action the agent decided on (e.g.
        ``"plan_navigation"``, ``"describe_scene"``).
    intent:
        Natural-language or structured intent received from the
        upstream caller (user or another agent).
    context:
        Contextual payload fed to the LLM alongside the intent.
    response:
        The agent's output — may be natural language, a structured
        command, or a plan.
    tokens_used:
        Total token consumption for this inference call (prompt +
        completion).
    """

    # -- BaseEvent overrides --
    event_id: str = field(default_factory=_default_event_id)
    timestamp: float = field(default_factory=_default_timestamp)
    event_type: str = field(default="AgentEvent", init=True)
    source: str = "agent_runtime"

    # -- Domain fields --
    agent_id: str = ""
    agent_type: str = ""
    action: str = ""
    intent: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    response: str = ""
    tokens_used: int = 0
