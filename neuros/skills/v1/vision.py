"""
NEUROS V1 Vision Skills — DetectObject, TrackObject, ScanArea.
"""

from __future__ import annotations

import logging
import time

from neuros.skills.base import BaseSkill, SkillContext, SkillResult

logger = logging.getLogger("neuros.skills.v1.vision")


class DetectObjectSkill(BaseSkill):
    """Detect a specific object in the camera feed."""

    @property
    def name(self) -> str:
        return "detect_object"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "Detect a target object using the camera."

    @property
    def required_capabilities(self) -> list[str]:
        return ["vision"]

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "target": {"type": "string"},
                "camera_id": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            },
            "required": ["target"],
        }

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        start = time.perf_counter()
        target = params["target"]
        camera = params.get("camera_id", "default")
        confidence = params.get("confidence", 0.5)

        logger.info("DetectObjectSkill: target=%s, camera=%s, conf=%.2f", target, camera, confidence)

        if context.bus:
            context.bus.publish(
                "/robot/cmd/detect",
                {"target": target, "camera_id": camera, "confidence": confidence, "source": "skill:detect_object:v1"},
            )

        return self._ok({"target": target, "camera_id": camera, "confidence": confidence}, start)


class TrackObjectSkill(BaseSkill):
    """Continuously track a target object."""

    @property
    def name(self) -> str:
        return "track_object"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "Track a target object in real-time using the camera."

    @property
    def required_capabilities(self) -> list[str]:
        return ["vision"]

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "target": {"type": "string"},
                "camera_id": {"type": "string"},
                "timeout_s": {"type": "number", "minimum": 1.0, "maximum": 300.0},
            },
            "required": ["target"],
        }

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        start = time.perf_counter()
        target = params["target"]
        camera = params.get("camera_id", "default")

        logger.info("TrackObjectSkill: target=%s, camera=%s", target, camera)

        if context.bus:
            context.bus.publish(
                "/robot/cmd/track",
                {"target": target, "camera_id": camera, "source": "skill:track_object:v1"},
            )

        return self._ok({"target": target, "camera_id": camera, "tracking": True}, start)


class ScanAreaSkill(BaseSkill):
    """Scan the environment by sweeping the camera."""

    @property
    def name(self) -> str:
        return "scan_area"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "Scan the surrounding area by sweeping the camera."

    @property
    def required_capabilities(self) -> list[str]:
        return ["vision"]

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "camera_id": {"type": "string"},
                "sweep_degrees": {"type": "number", "minimum": 10.0, "maximum": 360.0},
            },
        }

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        start = time.perf_counter()
        camera = params.get("camera_id", "default")
        sweep = params.get("sweep_degrees", 180.0)

        logger.info("ScanAreaSkill: camera=%s, sweep=%.0f°", camera, sweep)

        if context.bus:
            context.bus.publish(
                "/robot/cmd/scan",
                {"camera_id": camera, "sweep_degrees": sweep, "source": "skill:scan_area:v1"},
            )

        return self._ok({"camera_id": camera, "sweep_degrees": sweep}, start)
