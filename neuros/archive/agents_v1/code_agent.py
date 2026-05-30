"""NEUROS Code Agent — Code generation for Studio only, NOT runtime."""

from __future__ import annotations

import logging
from typing import Any

from neuros.agents.base import BaseAgent, AgentResponse

logger = logging.getLogger("neuros.agents.code")


class CodeAgent(BaseAgent):
    """
    Generates code snippets for use in NEUROS Studio.
    This agent is ONLY for development assistance.
    Generated code must be reviewed by a human before deployment.
    It NEVER executes code directly on the robot.
    """

    def __init__(self) -> None:
        super().__init__(name="code", role="Code generation for Studio (non-runtime)")

    async def process(
        self, message: str, context: dict[str, Any] | None = None
    ) -> AgentResponse:
        context = context or {}
        message_lower = message.lower()

        if any(w in message_lower for w in ["skill", "create skill", "new skill"]):
            skill_name = context.get("skill_name", "custom_skill")
            code = self._generate_skill_template(skill_name)
            return AgentResponse(
                agent_name=self.name,
                intent="generate_skill",
                actions=[{"code": code, "language": "python", "type": "skill"}],
                message=f"Generated skill template: {skill_name}",
                confidence=0.9,
            )

        elif any(w in message_lower for w in ["node", "create node"]):
            node_name = context.get("node_name", "custom_node")
            code = self._generate_node_template(node_name)
            return AgentResponse(
                agent_name=self.name,
                intent="generate_node",
                actions=[{"code": code, "language": "python", "type": "node"}],
                message=f"Generated node template: {node_name}",
                confidence=0.9,
            )

        return AgentResponse(
            agent_name=self.name,
            intent="unknown_code",
            message="Specify what to generate (e.g., 'create a skill', 'create a node').",
            confidence=0.3,
        )

    def _generate_skill_template(self, name: str) -> str:
        class_name = "".join(w.capitalize() for w in name.split("_")) + "Skill"
        return f'''"""Custom Skill: {name}"""

from neuros.skills.base import BaseSkill, SkillContext, SkillResult
import time


class {class_name}(BaseSkill):
    @property
    def name(self) -> str:
        return "{name}"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "TODO: describe this skill"

    @property
    def required_capabilities(self) -> list[str]:
        return []  # TODO: add required capabilities

    @property
    def parameters_schema(self) -> dict:
        return {{
            "type": "object",
            "properties": {{}},
        }}

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        start = time.perf_counter()
        # TODO: implement skill logic
        return self._ok({{"status": "done"}}, start)
'''

    def _generate_node_template(self, name: str) -> str:
        class_name = "".join(w.capitalize() for w in name.split("_")) + "Node"
        return f'''"""Custom Node: {name}"""


class {class_name}:
    def __init__(self, bus):
        self.bus = bus
        self.bus.subscribe("/robot/cmd/{name}", self.on_command)

    def on_command(self, msg):
        # TODO: handle command
        pass

    def tick(self):
        # TODO: periodic logic
        pass
'''
