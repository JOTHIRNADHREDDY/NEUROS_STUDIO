"""
NEUROS V1 Navigation Skills — NavigateTo, Explore, FollowPath.

Navigation skills publish goal events to the Neural Bus.
ROS2 Nav2 (via Bridge) or onboard planners handle the actual path execution.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from neuros.skills.base import BaseSkill, SkillContext, SkillResult

logger = logging.getLogger("neuros.skills.v1.navigation")


class NavigateToSkill(BaseSkill):
    """Navigate the robot to a specific coordinate or named location."""

    @property
    def name(self) -> str:
        return "navigate_to"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "Navigate the robot to a target position (x, y) or named location."

    @property
    def required_capabilities(self) -> list[str]:
        return ["navigation"]

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "x": {"type": "number"},
                "y": {"type": "number"},
                "theta": {"type": "number"},
                "location_name": {"type": "string"},
                "max_speed": {"type": "number", "minimum": 0.0, "maximum": 2.0},
            },
        }

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        start = time.perf_counter()
        x = params.get("x", 0.0)
        y = params.get("y", 0.0)
        theta = params.get("theta")
        location = params.get("location_name")

        target = location if location else f"({x}, {y})"
        logger.info("NavigateToSkill: target=%s", target)

        if context.bus:
            context.bus.publish(
                "/robot/cmd/navigate",
                {
                    "x": x,
                    "y": y,
                    "theta": theta,
                    "location_name": location,
                    "max_speed": params.get("max_speed", 0.5),
                    "source": "skill:navigate_to:v1",
                },
            )

        return self._ok(
            {"target": target, "x": x, "y": y, "theta": theta},
            start,
        )


class ExploreSkill(BaseSkill):
    """Explore the surroundings within a radius."""

    @property
    def name(self) -> str:
        return "explore"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "Explore the area within a given radius."

    @property
    def required_capabilities(self) -> list[str]:
        return ["navigation", "vision"]

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "radius_m": {"type": "number", "minimum": 0.5, "maximum": 50.0},
                "duration_s": {"type": "number", "minimum": 5.0, "maximum": 600.0},
            },
            "required": ["radius_m"],
        }

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        start = time.perf_counter()
        radius = params["radius_m"]
        duration = params.get("duration_s", 60.0)

        logger.info("ExploreSkill: radius=%.1fm, duration=%.0fs", radius, duration)

        if context.bus:
            context.bus.publish(
                "/robot/cmd/explore",
                {
                    "radius_m": radius,
                    "duration_s": duration,
                    "source": "skill:explore:v1",
                },
            )

        return self._ok({"radius_m": radius, "duration_s": duration}, start)


class FollowPathSkill(BaseSkill):
    """Follow a sequence of waypoints."""

    @property
    def name(self) -> str:
        return "follow_path"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "Follow a predefined sequence of waypoints."

    @property
    def required_capabilities(self) -> list[str]:
        return ["navigation"]

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "waypoints": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                        },
                        "required": ["x", "y"],
                    },
                    "minItems": 1,
                },
                "loop": {"type": "boolean"},
                "max_speed": {"type": "number", "minimum": 0.0, "maximum": 2.0},
            },
            "required": ["waypoints"],
        }

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        start = time.perf_counter()
        waypoints = params["waypoints"]
        loop = params.get("loop", False)

        logger.info(
            "FollowPathSkill: %d waypoints, loop=%s", len(waypoints), loop
        )

        if context.bus:
            context.bus.publish(
                "/robot/cmd/follow_path",
                {
                    "waypoints": waypoints,
                    "loop": loop,
                    "max_speed": params.get("max_speed", 0.5),
                    "source": "skill:follow_path:v1",
                },
            )

        return self._ok(
            {"waypoints_count": len(waypoints), "loop": loop},
            start,
        )
