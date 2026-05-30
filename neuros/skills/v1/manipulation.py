"""
NEUROS V1 Manipulation Skills — Pick, Place, Grip, Release.
"""

from __future__ import annotations

import logging
import time

from neuros.skills.base import BaseSkill, SkillContext, SkillResult

logger = logging.getLogger("neuros.skills.v1.manipulation")


class PickObjectSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "pick_object"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "Pick up a target object using the gripper."

    @property
    def required_capabilities(self) -> list[str]:
        return ["manipulation", "vision"]

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "target": {"type": "string"},
                "gripper_id": {"type": "string"},
                "approach_speed": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            },
            "required": ["target"],
        }

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        start = time.perf_counter()
        target = params["target"]
        gripper = params.get("gripper_id", "default")

        logger.info("PickObjectSkill: target=%s, gripper=%s", target, gripper)

        if context.bus:
            context.bus.publish(
                "/robot/cmd/pick",
                {"target": target, "gripper_id": gripper, "source": "skill:pick_object:v1"},
            )

        return self._ok({"target": target, "gripper_id": gripper, "picked": True}, start)


class PlaceObjectSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "place_object"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "Place a held object at a target location."

    @property
    def required_capabilities(self) -> list[str]:
        return ["manipulation"]

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "x": {"type": "number"},
                "y": {"type": "number"},
                "z": {"type": "number"},
                "gripper_id": {"type": "string"},
            },
        }

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        start = time.perf_counter()
        gripper = params.get("gripper_id", "default")
        location = {"x": params.get("x", 0), "y": params.get("y", 0), "z": params.get("z", 0)}

        logger.info("PlaceObjectSkill: location=%s, gripper=%s", location, gripper)

        if context.bus:
            context.bus.publish(
                "/robot/cmd/place",
                {"location": location, "gripper_id": gripper, "source": "skill:place_object:v1"},
            )

        return self._ok({"location": location, "placed": True}, start)


class GripSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "grip"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "Close the gripper with specified force."

    @property
    def required_capabilities(self) -> list[str]:
        return ["manipulation"]

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "gripper_id": {"type": "string"},
                "force": {"type": "number", "minimum": 0.0, "maximum": 100.0},
            },
        }

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        start = time.perf_counter()
        gripper = params.get("gripper_id", "default")
        force = params.get("force", 50.0)

        logger.info("GripSkill: gripper=%s, force=%.1f", gripper, force)

        if context.bus:
            context.bus.publish(
                "/robot/cmd/grip",
                {"gripper_id": gripper, "force": force, "source": "skill:grip:v1"},
            )

        return self._ok({"gripper_id": gripper, "force": force, "gripping": True}, start)


class ReleaseSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "release"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "Open the gripper to release an object."

    @property
    def required_capabilities(self) -> list[str]:
        return ["manipulation"]

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "gripper_id": {"type": "string"},
            },
        }

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        start = time.perf_counter()
        gripper = params.get("gripper_id", "default")

        logger.info("ReleaseSkill: gripper=%s", gripper)

        if context.bus:
            context.bus.publish(
                "/robot/cmd/release",
                {"gripper_id": gripper, "source": "skill:release:v1"},
            )

        return self._ok({"gripper_id": gripper, "released": True}, start)
