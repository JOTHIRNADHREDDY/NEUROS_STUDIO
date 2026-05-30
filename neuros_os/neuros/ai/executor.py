"""
neuros.ai.executor
===================
IntentExecutor — translates a parsed Intent into Robot API calls.

This is the "actuator" side of the AI pipeline:
  Intent → IntentExecutor → Robot.publish / node create / mission start

Extensible action registry
---------------------------
  Add new actions without touching the executor:
    IntentExecutor.register("my_action", my_handler_fn)

  Handler signature: (robot, intent, orchestrator) -> bool
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from neuros.api.robot     import Robot
    from neuros.ai.llm.orchestrator import LLMOrchestrator, Intent

logger = logging.getLogger("neuros.ai.executor")

# Registry: action_name → handler(robot, intent, orchestrator) → bool
_ACTION_REGISTRY: Dict[str, Callable] = {}


def register(action: str, handler: Callable) -> None:
    _ACTION_REGISTRY[action] = handler


class IntentExecutor:
    """
    Executes parsed intents on a Robot.

    Parameters
    ----------
    robot        : target Robot instance
    orchestrator : the LLMOrchestrator (for follow-up queries)
    """

    def __init__(self, robot: "Robot", orchestrator: "LLMOrchestrator") -> None:
        self._robot = robot
        self._llm   = orchestrator

    def execute(self, intent: "Intent") -> bool:
        """Execute an intent. Returns True on success."""
        if not intent.is_valid():
            logger.warning("[EXEC] unknown intent: %r", intent.raw_text)
            return False

        # Look up in registry first (allows external extensions)
        handler = _ACTION_REGISTRY.get(intent.action)
        if handler:
            try:
                return bool(handler(self._robot, intent, self._llm))
            except Exception as e:
                logger.error("[EXEC] handler '%s' raised: %s", intent.action, e)
                return False

        # Built-in handlers
        return self._built_in(intent)

    def _built_in(self, intent: "Intent") -> bool:
        r = self._robot
        a = intent.action
        p = intent.params

        try:
            # ── LED / buzzer ────────────────────────────────────────────
            if a == "blink":
                hz = float(p.get("hz", 1.0))
                r.publish("cmd/led/status", {"pattern": "blink", "hz": hz})
                logger.info("[EXEC] blink at %.1f Hz", hz)
                return True

            if a == "led_on":
                r.publish("cmd/led/status", {"state": "on"})
                return True

            if a == "led_off":
                r.publish("cmd/led/status", {"state": "off"})
                return True

            if a == "led_pattern":
                r.publish("cmd/led/status", {
                    "pattern": p.get("pattern", "blink"),
                    "hz":      float(p.get("hz", 1.0)),
                })
                return True

            if a == "buzzer_tone":
                r.publish("cmd/buzzer/buzzer", {
                    "state": "on",
                    "frequency_hz": float(p.get("frequency_hz", 440)),
                })
                return True

            if a == "buzzer_pattern":
                r.publish("cmd/buzzer/buzzer", {
                    "pattern": p.get("pattern", "beep"),
                })
                return True

            # ── Motors ──────────────────────────────────────────────────
            if a == "stop":
                r.publish("cmd/stop", {})
                logger.info("[EXEC] stop all motors")
                return True

            if a == "move_forward":
                speed = float(p.get("speed", 0.5))
                r.publish("cmd/motor/motor_left",  {"speed": speed})
                r.publish("cmd/motor/motor_right", {"speed": speed})
                # Auto-stop after duration if specified
                dur = float(p.get("duration_s", 0))
                if dur > 0:
                    import threading
                    def _stop():
                        time.sleep(dur)
                        r.publish("cmd/stop", {})
                    threading.Thread(target=_stop, daemon=True).start()
                return True

            if a == "move_backward":
                speed = -abs(float(p.get("speed", 0.5)))
                r.publish("cmd/motor/motor_left",  {"speed": speed})
                r.publish("cmd/motor/motor_right", {"speed": speed})
                return True

            if a == "turn_left":
                angle  = float(p.get("angle_deg", 90))
                speed  = float(p.get("speed", 0.4))
                r.publish("cmd/motor/motor_left",  {"speed": -speed})
                r.publish("cmd/motor/motor_right", {"speed":  speed})
                return True

            if a == "turn_right":
                speed = float(p.get("speed", 0.4))
                r.publish("cmd/motor/motor_left",  {"speed":  speed})
                r.publish("cmd/motor/motor_right", {"speed": -speed})
                return True

            if a == "motor_speed":
                left  = float(p.get("left",  p.get("speed", 0.5)))
                right = float(p.get("right", p.get("speed", 0.5)))
                r.publish("cmd/motor/motor_left",  {"speed": left})
                r.publish("cmd/motor/motor_right", {"speed": right})
                return True

            # ── Navigation ───────────────────────────────────────────────
            if a == "go_to":
                x = float(p.get("x", 0.0))
                y = float(p.get("y", 0.0))
                r.publish("/robot/nav/waypoint/goal", {"x": x, "y": y})
                logger.info("[EXEC] go_to (%.2f, %.2f)", x, y)
                return True

            if a == "patrol":
                waypoints = p.get("waypoints", [
                    {"x": 1.0, "y": 0.0}, {"x": 1.0, "y": 1.0},
                    {"x": 0.0, "y": 1.0}, {"x": 0.0, "y": 0.0},
                ])
                r.publish("/robot/nav/waypoint/mission", {"waypoints": waypoints})
                logger.info("[EXEC] patrol %d waypoints", len(waypoints))
                return True

            if a == "follow_line":
                r.publish("/robot/cmd/mode", {"mode": "line_follow"})
                return True

            if a == "avoid_obstacles":
                r.publish("/robot/cmd/mode", {"mode": "obstacle_avoid"})
                return True

            # ── Servo ────────────────────────────────────────────────────
            if a == "servo_angle":
                name  = p.get("servo", "pan")
                angle = float(p.get("angle_deg", 90))
                r.publish(f"cmd/servo/{name}", {"angle_deg": angle})
                return True

            # ── AI / camera ──────────────────────────────────────────────
            if a == "camera_on":
                r.publish("/robot/cmd/camera", {"state": "on"})
                return True

            if a == "camera_off":
                r.publish("/robot/cmd/camera", {"state": "off"})
                return True

            if a == "detect_objects":
                r.publish("/robot/cmd/ai/detect", {"model": p.get("model", "yolo")})
                return True

            # ── System ───────────────────────────────────────────────────
            if a == "emergency_stop":
                r._kernel.emergency_stop("LLM command")
                return True

            if a == "reset_estop":
                from neuros.safety import SafetySupervisor
                for node in r._nodes.values():
                    if isinstance(node, SafetySupervisor):
                        node.reset_estop()
                return True

            if a == "status":
                import json
                status = r.status()
                print("\n" + json.dumps(status, indent=2))
                return True

            if a == "add_node":
                return self._add_node(intent)

            if a == "mission_plan":
                return self._mission_plan(intent)

            logger.warning("[EXEC] no handler for action '%s'", a)
            return False

        except Exception as e:
            logger.error("[EXEC] execution error for '%s': %s", a, e)
            return False

    def _add_node(self, intent: "Intent") -> bool:
        """Generate and install a new node using NodeCodegen."""
        try:
            from neuros.ai.codegen.generator import NodeCodegen
            codegen = NodeCodegen(self._llm)
            gen     = codegen.generate(intent.params.get("description", ""))
            if gen.node_class:
                node = gen.node_class(gen.node_name, hz=float(intent.params.get("hz", 10)))
                self._robot.add_node(node)
                logger.info("[EXEC] installed generated node '%s'", gen.node_name)
                return True
        except Exception as e:
            logger.error("[EXEC] add_node failed: %s", e)
        return False

    def _mission_plan(self, intent: "Intent") -> bool:
        """Use MissionPlanner to build and start a multi-step mission."""
        try:
            from neuros.ai.planner.mission import MissionPlanner
            planner = MissionPlanner(self._llm)
            graph   = planner.plan(intent.params.get("description", intent.raw_text))
            planner.execute(graph, self._robot)
            return True
        except Exception as e:
            logger.error("[EXEC] mission_plan failed: %s", e)
        return False
