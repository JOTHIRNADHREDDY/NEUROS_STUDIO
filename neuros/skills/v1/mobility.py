"""
NEUROS V1 Mobility Skills — Move, Stop, Turn, Reverse.

These skills publish high-level commands to the Neural Bus.
The HAL translates them into hardware-specific instructions.
Python NEVER directly controls PWM or motor timing.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from neuros.skills.base import BaseSkill, SkillContext, SkillResult

logger = logging.getLogger("neuros.skills.v1.mobility")


class MoveSkill(BaseSkill):
    """Move the robot in a direction at a given speed for a duration."""

    @property
    def name(self) -> str:
        return "move"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "Move the robot forward, backward, left, or right."

    @property
    def required_capabilities(self) -> list[str]:
        return ["mobility"]

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["forward", "backward", "left", "right"],
                },
                "speed": {"type": "number", "minimum": 0.0, "maximum": 2.0},
                "duration_s": {"type": "number", "minimum": 0.1, "maximum": 60.0},
            },
            "required": ["direction", "speed", "duration_s"],
        }

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        start = time.perf_counter()
        direction = params["direction"]
        speed = params["speed"]
        duration = params["duration_s"]

        logger.info("MoveSkill: %s at %.2f m/s for %.1fs", direction, speed, duration)

        # Publish command to Neural Bus — HAL handles actual motor control
        if context.bus:
            context.bus.publish(
                "/robot/cmd/move",
                {
                    "direction": direction,
                    "speed": speed,
                    "duration_s": duration,
                    "source": "skill:move:v1",
                },
            )

        return self._ok(
            {"direction": direction, "speed": speed, "duration_s": duration},
            start,
        )


class StopSkill(BaseSkill):
    """Immediately stop all robot movement."""

    @property
    def name(self) -> str:
        return "stop"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "Stop all robot movement immediately."

    @property
    def required_capabilities(self) -> list[str]:
        return ["mobility"]

    @property
    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}, "additionalProperties": False}

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        start = time.perf_counter()
        logger.info("StopSkill: Stopping all movement.")

        if context.bus:
            context.bus.publish(
                "/robot/cmd/stop",
                {"source": "skill:stop:v1"},
            )

        return self._ok({"stopped": True}, start)


class TurnSkill(BaseSkill):
    """Turn the robot by a specified angle."""

    @property
    def name(self) -> str:
        return "turn"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "Turn the robot by a given angle in degrees."

    @property
    def required_capabilities(self) -> list[str]:
        return ["mobility"]

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "angle_deg": {"type": "number", "minimum": -360.0, "maximum": 360.0},
                "speed": {"type": "number", "minimum": 0.0, "maximum": 2.0},
            },
            "required": ["angle_deg"],
        }

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        start = time.perf_counter()
        angle = params["angle_deg"]
        speed = params.get("speed", 0.5)

        logger.info("TurnSkill: %.1f° at speed %.2f", angle, speed)

        if context.bus:
            context.bus.publish(
                "/robot/cmd/turn",
                {"angle_deg": angle, "speed": speed, "source": "skill:turn:v1"},
            )

        return self._ok({"angle_deg": angle, "speed": speed}, start)


class ReverseSkill(BaseSkill):
    """Move the robot in reverse."""

    @property
    def name(self) -> str:
        return "reverse"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "Move the robot backward at a given speed."

    @property
    def required_capabilities(self) -> list[str]:
        return ["mobility"]

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "speed": {"type": "number", "minimum": 0.0, "maximum": 1.5},
                "duration_s": {"type": "number", "minimum": 0.1, "maximum": 30.0},
            },
            "required": ["speed", "duration_s"],
        }

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        start = time.perf_counter()
        speed = params["speed"]
        duration = params["duration_s"]

        logger.info("ReverseSkill: %.2f m/s for %.1fs", speed, duration)

        if context.bus:
            context.bus.publish(
                "/robot/cmd/move",
                {
                    "direction": "backward",
                    "speed": speed,
                    "duration_s": duration,
                    "source": "skill:reverse:v1",
                },
            )

        return self._ok({"speed": speed, "duration_s": duration}, start)
