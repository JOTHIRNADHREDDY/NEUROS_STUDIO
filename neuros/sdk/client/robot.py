"""
NEUROS Robot Client

The primary developer-facing API. This is what users import:

    from neuros import Robot

    robot = Robot(name="my_rover", board="simulator")
    robot.move_forward(speed=0.5, duration_s=2.0)
    robot.navigate_to("kitchen")
    robot.detect_object("red bottle")

The Robot class sends high-level commands to the runtime.
It NEVER controls hardware directly.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger("neuros.sdk.robot")


class Robot:
    """
    NEUROS Robot — high-level client API.

    Sends commands to the NEUROS Runtime which routes them through:
    Agent -> Planner -> Skill -> Execution Manager -> Sandbox -> Validator -> HAL

    Usage:
        robot = Robot(name="rover01", board="simulator")
        robot.start()
        robot.move_forward(speed=0.5)
        robot.navigate_to("kitchen")
        robot.stop()
    """

    def __init__(
        self,
        name: str = "neuros-robot",
        board: str = "simulator",
        robot_type: str = "rover",
        config_path: str | None = None,
    ) -> None:
        self.name = name
        self.board = board
        self.robot_type = robot_type
        self._config_path = config_path
        self._started = False
        self._capabilities: set[str] = set()
        self._execution_manager: Any = None
        self._skill_engine: Any = None
        self._bus: Any = None
        self._hal: Any = None
        self._planner: Any = None
        logger.info("Robot '%s' created (board=%s, type=%s)", name, board, robot_type)

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> None:
        """Initialize and start the robot runtime."""
        if self._started:
            logger.warning("Robot '%s' already started.", self.name)
            return

        logger.info("Starting robot '%s'...", self.name)

        # Initialize core systems (lazy imports to avoid circular deps)
        from neuros.bus.bus import NeuralBus
        from neuros.skills.engine import SkillEngine
        from neuros.skills.v1 import (
            MoveSkill, StopSkill, TurnSkill, ReverseSkill,
            NavigateToSkill, ExploreSkill, FollowPathSkill,
            DetectObjectSkill, TrackObjectSkill, ScanAreaSkill,
            PickObjectSkill, PlaceObjectSkill, GripSkill, ReleaseSkill,
            SystemCheckSkill, SelfTestSkill,
        )
        from neuros.safety.validator import SafetyValidator
        from neuros.safety.sandbox import SkillSandbox
        from neuros.safety.emergency_stop import EmergencyStop
        from neuros.agents.planner import PlannerAgent

        # Wire up
        self._bus = NeuralBus()
        self._skill_engine = SkillEngine()
        self._planner = PlannerAgent()

        # Register all v1 skills
        for skill_cls in [
            MoveSkill, StopSkill, TurnSkill, ReverseSkill,
            NavigateToSkill, ExploreSkill, FollowPathSkill,
            DetectObjectSkill, TrackObjectSkill, ScanAreaSkill,
            PickObjectSkill, PlaceObjectSkill, GripSkill, ReleaseSkill,
            SystemCheckSkill, SelfTestSkill,
        ]:
            try:
                self._skill_engine.register_skill(skill_cls())
            except Exception:
                pass

        # Set default capabilities based on robot type
        type_caps = {
            "rover": {"mobility", "navigation", "vision", "diagnostics"},
            "arm": {"manipulation", "vision", "diagnostics"},
            "drone": {"mobility", "navigation", "vision", "diagnostics"},
            "humanoid": {"mobility", "navigation", "manipulation", "vision", "speech", "diagnostics"},
        }
        self._capabilities = type_caps.get(self.robot_type, {"diagnostics"})

        self._started = True
        logger.info("Robot '%s' STARTED. Capabilities: %s", self.name, self._capabilities)

    def stop(self) -> None:
        """Stop the robot."""
        logger.info("Robot '%s' stopping.", self.name)
        self._started = False

    # ── Capability Check ──────────────────────────────────────────────────

    def has_capability(self, capability: str) -> bool:
        """Check if the robot has a specific capability."""
        return capability in self._capabilities

    def add_capability(self, capability: str) -> None:
        self._capabilities.add(capability)

    # ── High-Level Commands ───────────────────────────────────────────────

    def move_forward(self, speed: float = 0.5, duration_s: float = 1.0) -> None:
        """Move the robot forward."""
        self._submit_skill("move", {"direction": "forward", "speed": speed, "duration_s": duration_s}, "mobility")

    def move_backward(self, speed: float = 0.5, duration_s: float = 1.0) -> None:
        """Move the robot backward."""
        self._submit_skill("reverse", {"speed": speed, "duration_s": duration_s}, "mobility")

    def turn(self, angle_deg: float, speed: float = 0.5) -> None:
        """Turn the robot by an angle."""
        self._submit_skill("turn", {"angle_deg": angle_deg, "speed": speed}, "mobility")

    def stop_moving(self) -> None:
        """Stop all movement."""
        self._submit_skill("stop", {}, "mobility")

    def navigate_to(self, location: str | None = None, x: float = 0.0, y: float = 0.0) -> None:
        """Navigate to a location or coordinates."""
        params: dict[str, Any] = {}
        if location:
            params["location_name"] = location
        else:
            params["x"] = x
            params["y"] = y
        self._submit_skill("navigate_to", params, "navigation")

    def detect_object(self, target: str, confidence: float = 0.5) -> None:
        """Detect an object in the camera feed."""
        self._submit_skill("detect_object", {"target": target, "confidence": confidence}, "vision")

    def pick_object(self, target: str) -> None:
        """Pick up an object."""
        self._submit_skill("pick_object", {"target": target}, "manipulation")

    def place_object(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> None:
        """Place a held object."""
        self._submit_skill("place_object", {"x": x, "y": y, "z": z}, "manipulation")

    def explore(self, radius_m: float = 5.0) -> None:
        """Explore the surroundings."""
        self._submit_skill("explore", {"radius_m": radius_m}, "navigation")

    def scan_area(self, sweep_degrees: float = 360.0) -> None:
        """Scan the area with the camera."""
        self._submit_skill("scan_area", {"sweep_degrees": sweep_degrees}, "vision")

    def system_check(self) -> None:
        """Run a system health check."""
        self._submit_skill("system_check", {})

    def emergency_stop(self) -> None:
        """EMERGENCY STOP — bypasses everything."""
        logger.critical("🚨 EMERGENCY STOP on robot '%s'", self.name)
        if self._bus:
            from neuros.bus.message import Message
            self._bus.publish(Message(topic="/robot/safety/emergency_stop", data={"triggered": True, "source": "sdk"}), source_id="sdk")

    # ── Natural Language Interface ────────────────────────────────────────

    async def execute(self, command: str) -> dict[str, Any]:
        """
        Execute a natural language command.
        Routes through Planner Agent -> Skill Engine.
        """
        if not self._planner:
            return {"error": "Robot not started. Call robot.start() first."}

        response = await self._planner.run(command)
        logger.info("Planned %d actions for: '%s'", len(response.actions), command)

        results = []
        for action in response.actions:
            skill_name = action.get("skill", "")
            params = action.get("params", {})
            self._submit_skill(skill_name, params)
            results.append({"skill": skill_name, "status": "submitted"})

        return {
            "intent": response.intent,
            "actions": results,
            "message": response.message,
        }

    # ── Internal ──────────────────────────────────────────────────────────

    def _submit_skill(self, skill_name: str, params: dict[str, Any], required_capability: str | None = None) -> None:
        """Submit a skill to the execution pipeline."""
        if not self._started:
            logger.warning("Robot not started. Call robot.start() first.")
            return

        if required_capability and not self.has_capability(required_capability):
            logger.error("Cannot execute %s: Robot missing required capability '%s'", skill_name, required_capability)
            raise RuntimeError(f"Robot missing capability: {required_capability}")

        logger.info("Submitting skill: %s(%s)", skill_name, params)

        if self._bus:
            from neuros.bus.message import Message
            self._bus.publish(
                Message(topic="/robot/skill/submit", data={"skill": skill_name, "params": params, "source": "sdk"}),
                source_id="sdk",
            )

    # ── Info ──────────────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "board": self.board,
            "type": self.robot_type,
            "started": self._started,
            "capabilities": sorted(self._capabilities),
            "skills_registered": len(self._skill_engine) if self._skill_engine else 0,
        }

    def __repr__(self) -> str:
        return f"<Robot name={self.name!r} board={self.board!r} type={self.robot_type!r}>"
