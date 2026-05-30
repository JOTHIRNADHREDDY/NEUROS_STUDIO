"""
NEUROS Planner Agent

Decomposes high-level goals into ordered sequences of skill calls.
Example: "Find the red bottle" -> [scan_area, detect_object, navigate_to, pick_object]
"""

from __future__ import annotations

import logging
from typing import Any

from neuros.agents.base import BaseAgent, AgentResponse

logger = logging.getLogger("neuros.agents.planner")

# Built-in planning templates for common goals
_PLAN_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "find_object": [
        {"skill": "scan_area", "params": {"sweep_degrees": 360}},
        {"skill": "detect_object", "params": {"target": "{target}"}},
        {"skill": "navigate_to", "params": {"x": "{target_x}", "y": "{target_y}"}},
    ],
    "pick_and_place": [
        {"skill": "detect_object", "params": {"target": "{target}"}},
        {"skill": "navigate_to", "params": {"x": "{target_x}", "y": "{target_y}"}},
        {"skill": "pick_object", "params": {"target": "{target}"}},
        {"skill": "navigate_to", "params": {"x": "{dest_x}", "y": "{dest_y}"}},
        {"skill": "place_object", "params": {}},
    ],
    "patrol": [
        {"skill": "follow_path", "params": {"waypoints": "{waypoints}", "loop": True}},
    ],
    "explore": [
        {"skill": "explore", "params": {"radius_m": "{radius}"}},
    ],
    "go_to": [
        {"skill": "navigate_to", "params": {"location_name": "{location}"}},
    ],
}


class PlannerAgent(BaseAgent):
    """
    Decomposes goals into skill sequences.

    In MVP mode, uses template matching.
    In future versions, will use LLM for dynamic plan generation.
    """

    def __init__(self) -> None:
        super().__init__(name="planner", role="Goal decomposition into skill sequences")
        self._templates = dict(_PLAN_TEMPLATES)

    def add_template(self, name: str, steps: list[dict[str, Any]]) -> None:
        """Register a custom planning template."""
        self._templates[name] = steps

    async def process(
        self, message: str, context: dict[str, Any] | None = None
    ) -> AgentResponse:
        context = context or {}
        message_lower = message.lower()

        # Simple intent matching for MVP
        if any(w in message_lower for w in ["find", "locate", "search", "look for"]):
            intent = "find_object"
            target = self._extract_target(message)
            actions = self._instantiate_template(intent, {"target": target})

        elif any(w in message_lower for w in ["pick", "grab", "take"]):
            intent = "pick_and_place"
            target = self._extract_target(message)
            actions = self._instantiate_template(intent, {"target": target})

        elif any(w in message_lower for w in ["patrol", "guard", "watch"]):
            intent = "patrol"
            actions = self._instantiate_template(intent, {})

        elif any(w in message_lower for w in ["explore", "scout", "survey"]):
            intent = "explore"
            actions = self._instantiate_template(intent, {"radius": 5.0})

        elif any(w in message_lower for w in ["go to", "navigate", "move to", "drive to"]):
            intent = "go_to"
            location = self._extract_location(message)
            actions = self._instantiate_template(intent, {"location": location})

        elif any(w in message_lower for w in ["stop", "halt", "freeze"]):
            intent = "stop"
            actions = [{"skill": "stop", "params": {}}]

        elif any(w in message_lower for w in ["check", "status", "health", "diagnostic"]):
            intent = "diagnostics"
            actions = [{"skill": "system_check", "params": {}}]

        else:
            intent = "unknown"
            actions = []

        return AgentResponse(
            agent_name=self.name,
            intent=intent,
            actions=actions,
            message=f"Planned {len(actions)} steps for intent: {intent}",
            confidence=0.8 if actions else 0.2,
        )

    def _instantiate_template(
        self, template_name: str, variables: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Fill template variables with actual values."""
        template = self._templates.get(template_name, [])
        actions = []
        for step in template:
            params = {}
            for k, v in step.get("params", {}).items():
                if isinstance(v, str) and v.startswith("{") and v.endswith("}"):
                    var_name = v[1:-1]
                    params[k] = variables.get(var_name, v)
                else:
                    params[k] = v
            actions.append({"skill": step["skill"], "params": params})
        return actions

    def _extract_target(self, message: str) -> str:
        """Extract the target object from a natural language message."""
        # Simple heuristic: last noun phrase
        words = message.lower().split()
        skip = {"find", "the", "a", "an", "locate", "search", "for", "look", "pick", "grab", "take", "up", "get"}
        targets = [w for w in words if w not in skip]
        return " ".join(targets[-2:]) if targets else "object"

    def _extract_location(self, message: str) -> str:
        """Extract location from a navigation message."""
        words = message.lower().split()
        skip = {"go", "to", "the", "navigate", "move", "drive"}
        locations = [w for w in words if w not in skip]
        return " ".join(locations) if locations else "home"
