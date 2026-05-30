"""NEUROS Vision Agent — Camera processing and object detection."""

from __future__ import annotations

import logging
from typing import Any

from neuros.agents.base import BaseAgent, AgentResponse

logger = logging.getLogger("neuros.agents.vision")


class VisionAgent(BaseAgent):
    """Processes camera feeds and runs object detection/tracking."""

    def __init__(self) -> None:
        super().__init__(name="vision", role="Camera processing and object detection")

    async def process(
        self, message: str, context: dict[str, Any] | None = None
    ) -> AgentResponse:
        context = context or {}
        message_lower = message.lower()

        if any(w in message_lower for w in ["detect", "find", "see", "identify"]):
            target = context.get("target", "object")
            camera = context.get("camera_id", "default")
            return AgentResponse(
                agent_name=self.name,
                intent="detect_object",
                actions=[{
                    "skill": "detect_object",
                    "params": {"target": target, "camera_id": camera, "confidence": 0.5},
                }],
                message=f"Detecting '{target}' on camera '{camera}'.",
                confidence=0.85,
            )

        elif any(w in message_lower for w in ["track", "follow"]):
            target = context.get("target", "object")
            return AgentResponse(
                agent_name=self.name,
                intent="track_object",
                actions=[{
                    "skill": "track_object",
                    "params": {"target": target, "camera_id": "default"},
                }],
                message=f"Tracking '{target}'.",
                confidence=0.8,
            )

        elif any(w in message_lower for w in ["scan", "look around", "sweep"]):
            return AgentResponse(
                agent_name=self.name,
                intent="scan_area",
                actions=[{"skill": "scan_area", "params": {"sweep_degrees": 360.0}}],
                message="Scanning surroundings.",
                confidence=0.9,
            )

        return AgentResponse(
            agent_name=self.name,
            intent="unknown_vision",
            message="Could not determine vision task.",
            confidence=0.2,
        )
