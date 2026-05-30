"""
NEUROS Robotics Agent

Translates planned actions into skill execution commands.
Acts as the bridge between the Planner and the Execution Manager.
"""

from __future__ import annotations

import logging
from typing import Any

from neuros.agents.base import BaseAgent, AgentResponse

logger = logging.getLogger("neuros.agents.robotics")


class RoboticsAgent(BaseAgent):
    """
    Executes robot actions by submitting skills to the Execution Manager.

    Receives action lists from the Planner and converts them into
    concrete skill execution requests.
    """

    def __init__(self) -> None:
        super().__init__(name="robotics", role="Robot action execution via skills")

    async def process(
        self, message: str, context: dict[str, Any] | None = None
    ) -> AgentResponse:
        context = context or {}
        actions = context.get("actions", [])

        if not actions:
            return AgentResponse(
                agent_name=self.name,
                intent="no_actions",
                message="No actions to execute.",
                confidence=0.0,
            )

        executed = []
        for action in actions:
            skill_name = action.get("skill", "")
            params = action.get("params", {})
            executed.append({
                "skill": skill_name,
                "params": params,
                "status": "submitted",
            })

        return AgentResponse(
            agent_name=self.name,
            intent="execute_skills",
            actions=executed,
            message=f"Submitted {len(executed)} skills for execution.",
            confidence=0.9,
        )
