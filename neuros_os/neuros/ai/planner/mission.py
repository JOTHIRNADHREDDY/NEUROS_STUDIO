"""
neuros.ai.planner.mission
==========================
Mission Planner — Phase 3.

Converts a natural language mission description into a directed
mission graph that the NEUROS executor runs step-by-step.

Mission graph
-------------
  MissionGraph is a list of MissionNodes (steps).
  Each MissionNode specifies:
    - action      : what to do (maps to IntentExecutor actions)
    - params      : action parameters
    - condition   : optional pre-condition (sensor value check)
    - on_success  : next node index (default: advance)
    - on_failure  : next node index or "abort"
    - timeout_s   : max time for this step (0 = no timeout)

Example: "patrol zone A, avoid obstacles, return home when battery < 20%"
→ MissionGraph:
    0: avoid_obstacles  (always running)
    1: go_to (1, 0)
    2: go_to (1, 2)
    3: go_to (0, 2)
    4: check battery soc_pct < 20  → if True: goto 5, else: goto 1
    5: go_to (0, 0)  [home]
    6: stop

The LLM generates the graph JSON. Stub mode uses simple rule patterns.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from neuros.ai.llm.orchestrator import LLMOrchestrator
    from neuros.api.robot           import Robot

logger = logging.getLogger("neuros.ai.planner")


@dataclass
class MissionNode:
    """A single step in a mission graph."""
    index:      int
    action:     str
    params:     Dict[str, Any]         = field(default_factory=dict)
    condition:  Optional[str]          = None    # e.g. "battery.soc_pct < 20"
    on_success: int                    = -1      # -1 = advance to next
    on_failure: int | str              = "abort"
    timeout_s:  float                  = 0.0
    label:      str                    = ""

    def __post_init__(self):
        if self.on_success == -1:
            self.on_success = self.index + 1


@dataclass
class MissionGraph:
    """Directed graph of mission steps."""
    name:        str
    description: str
    nodes:       List[MissionNode]     = field(default_factory=list)
    loop:        bool                  = False
    source:      str                   = "stub"   # "llm" | "stub"

    def __len__(self) -> int:
        return len(self.nodes)

    def summary(self) -> str:
        lines = [f"Mission: {self.name} ({len(self.nodes)} steps, loop={self.loop})"]
        for n in self.nodes:
            cond = f" [if {n.condition}]" if n.condition else ""
            lines.append(f"  {n.index}: {n.action} {n.params}{cond}")
        return "\n".join(lines)


_MISSION_SYSTEM = """\
You are a robot mission planner for NEUROS OS.
Convert the user's mission description into a structured mission graph.

Respond ONLY with valid JSON, no other text:
{
  "name": "mission_name",
  "description": "what this mission does",
  "loop": false,
  "nodes": [
    {
      "index": 0,
      "action": "action_name",
      "params": {},
      "condition": null,
      "on_success": 1,
      "on_failure": "abort",
      "timeout_s": 0,
      "label": "human readable step name"
    }
  ]
}

Available actions: go_to, patrol, move_forward, move_backward, turn_left,
turn_right, stop, avoid_obstacles, follow_line, blink, led_on, led_off,
buzzer_pattern, camera_on, detect_objects, emergency_stop, status

For go_to: params = {"x": float, "y": float}
For patrol: params = {"waypoints": [{"x":f,"y":f},...], "loop": bool}
For move_forward: params = {"speed": float, "duration_s": float}
For blink: params = {"hz": float}
For condition: use strings like "battery.soc_pct < 20" or "obstacle.distance_m < 0.5"
"""


class MissionPlanner:
    """
    Plans multi-step robot missions from natural language.

    Parameters
    ----------
    llm         : LLMOrchestrator instance
    """

    def __init__(self, llm: "LLMOrchestrator") -> None:
        self._llm = llm

    def plan(self, description: str) -> MissionGraph:
        """Convert a natural language description into a MissionGraph."""
        if self._llm._provider.value != "stub":
            try:
                return self._llm_plan(description)
            except Exception as e:
                logger.warning("[PLANNER] LLM planning failed (%s) — using stub", e)
        return self._stub_plan(description)

    def execute(self, graph: MissionGraph, robot: "Robot") -> threading.Thread:
        """
        Execute a mission graph on a robot in a background thread.
        Returns the thread (daemon, safe to ignore).
        """
        logger.info("[PLANNER] starting mission: %s", graph.name)

        def _run():
            from neuros.ai.executor import IntentExecutor
            from neuros.ai.llm.orchestrator import Intent
            executor = IntentExecutor(robot, self._llm)
            current  = 0
            runs     = 0
            max_runs = 1 if not graph.loop else 9999

            while runs < max_runs:
                if current >= len(graph.nodes):
                    if graph.loop:
                        current = 0
                        runs   += 1
                        continue
                    break

                node = graph.nodes[current]
                logger.info("[PLANNER] step %d/%d: %s %s",
                            current, len(graph.nodes) - 1, node.action, node.params)

                # Check pre-condition
                if node.condition and not self._check_condition(node.condition, robot):
                    logger.info("[PLANNER] condition '%s' false — skipping", node.condition)
                    current = node.on_success
                    continue

                # Execute step
                intent  = Intent(
                    action   = node.action,
                    params   = node.params,
                    raw_text = node.label or node.action,
                )
                t0      = time.monotonic()
                success = executor.execute(intent)
                elapsed = time.monotonic() - t0

                # Wait for timed steps
                if node.timeout_s > elapsed:
                    time.sleep(node.timeout_s - elapsed)

                if success:
                    current = node.on_success
                else:
                    if node.on_failure == "abort":
                        logger.error("[PLANNER] step %d failed — aborting mission", node.index)
                        robot.publish("cmd/stop", {})
                        return
                    current = int(node.on_failure)

            logger.info("[PLANNER] mission '%s' complete", graph.name)

        t = threading.Thread(target=_run, name=f"mission-{graph.name}", daemon=True)
        t.start()
        return t

    def _llm_plan(self, description: str) -> MissionGraph:
        import urllib.request
        # Use the LLM to generate the mission graph JSON
        context = ""
        if self._llm._context_builder:
            ctx     = self._llm._context_builder.build()
            context = ctx.to_prompt_block()

        system = _MISSION_SYSTEM
        if context:
            system += f"\n\nROBOT CONTEXT:\n{context}"

        messages = [{"role": "user", "content": description}]

        if self._llm._provider.value == "anthropic":
            raw = self._llm._call_anthropic(system, messages)
        elif self._llm._provider.value == "nvidia":
            raw = self._llm._call_nvidia(system, messages)
        elif self._llm._provider.value == "openai":
            raw = self._llm._call_openai(system, messages)
        elif self._llm._provider.value == "ollama":
            raw = self._llm._call_ollama(system, messages)
        else:
            return self._stub_plan(description)

        return self._parse_graph_json(raw, description)

    def _parse_graph_json(self, raw: str, description: str) -> MissionGraph:
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().strip("`")
        match   = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return self._stub_plan(description)
        try:
            data  = json.loads(match.group())
            nodes = [
                MissionNode(
                    index      = n["index"],
                    action     = n.get("action", "stop"),
                    params     = n.get("params",  {}),
                    condition  = n.get("condition"),
                    on_success = n.get("on_success", n["index"] + 1),
                    on_failure = n.get("on_failure", "abort"),
                    timeout_s  = float(n.get("timeout_s", 0)),
                    label      = n.get("label", ""),
                )
                for n in data.get("nodes", [])
            ]
            return MissionGraph(
                name        = data.get("name",        "llm_mission"),
                description = data.get("description", description),
                nodes       = nodes,
                loop        = bool(data.get("loop",   False)),
                source      = "llm",
            )
        except Exception as e:
            logger.warning("[PLANNER] graph JSON parse error: %s", e)
            return self._stub_plan(description)

    @staticmethod
    def _stub_plan(description: str) -> MissionGraph:
        """Rule-based mission generation for common patterns."""
        d = description.lower()
        nodes: List[MissionNode] = []

        if "patrol" in d:
            wps = [{"x": 1.0, "y": 0.0}, {"x": 1.0, "y": 1.0},
                   {"x": 0.0, "y": 1.0}, {"x": 0.0, "y": 0.0}]
            nodes = [
                MissionNode(0, "avoid_obstacles", {}, on_success=1, timeout_s=0.1),
                MissionNode(1, "patrol", {"waypoints": wps, "loop": True}, on_success=2),
                MissionNode(2, "stop", {}, on_success=3),
            ]
            return MissionGraph("patrol", description, nodes, loop=False, source="stub")

        if "go home" in d or "return home" in d:
            nodes = [
                MissionNode(0, "go_to",  {"x": 0.0, "y": 0.0}, on_success=1, timeout_s=30),
                MissionNode(1, "stop",   {}, on_success=2),
                MissionNode(2, "buzzer_pattern", {"pattern": "double"}, on_success=3),
            ]
            return MissionGraph("go_home", description, nodes, source="stub")

        if "forward" in d and "backward" in d:
            nodes = [
                MissionNode(0, "move_forward",  {"speed": 0.5, "duration_s": 2.0}, on_success=1),
                MissionNode(1, "stop",           {}, on_success=2),
                MissionNode(2, "move_backward", {"speed": 0.5, "duration_s": 2.0}, on_success=3),
                MissionNode(3, "stop",           {}, on_success=4),
            ]
            return MissionGraph("forward_backward", description, nodes, source="stub")

        # Default: simple forward-stop
        nodes = [
            MissionNode(0, "move_forward", {"speed": 0.4, "duration_s": 3.0}, on_success=1),
            MissionNode(1, "stop", {}, on_success=2),
        ]
        return MissionGraph("default_mission", description, nodes, source="stub")

    @staticmethod
    def _check_condition(condition: str, robot: "Robot") -> bool:
        """
        Evaluate a simple condition string against robot state.
        Format: "sensor_name.field op value"
        e.g. "battery.soc_pct < 20", "obstacle.distance_m < 0.5"
        
        Reads from the bus metrics / latest published data to resolve values.
        """
        try:
            # Parse condition: "key.field op value"
            import operator
            ops = {
                "<":  operator.lt,  "<=": operator.le,
                ">":  operator.gt,  ">=": operator.ge,
                "==": operator.eq,  "!=": operator.ne,
            }

            # Find the operator
            op_str = None
            op_fn = None
            for op_candidate in ("<=", ">=", "!=", "==", "<", ">"):
                if op_candidate in condition:
                    op_str = op_candidate
                    op_fn = ops[op_candidate]
                    break

            if not op_fn or not op_str:
                logger.warning("[PLANNER] Cannot parse condition operator: '%s'", condition)
                return True  # Unknown format — don't block

            left_str, right_str = condition.split(op_str, 1)
            left_str = left_str.strip()
            right_str = right_str.strip()

            # Parse the target value
            try:
                target_value = float(right_str)
            except ValueError:
                target_value = right_str.strip("'\"")

            # Resolve the left side from bus data
            # Format: "topic_fragment.field" e.g. "battery.soc_pct"
            parts = left_str.split(".", 1)
            if len(parts) != 2:
                logger.warning("[PLANNER] Condition key needs 'topic.field' format: '%s'", left_str)
                return True

            topic_hint, field_name = parts

            # Search bus metrics for a topic containing the hint
            actual_value = None
            try:
                bus = robot._bus
                for topic_name in bus.topic_list():
                    if topic_hint in topic_name:
                        # Find matching subscriber stats or last message
                        for sub in bus._subs:
                            if sub.pattern == "#" or topic_hint in sub.pattern:
                                continue
                        # Check inspector stats if available
                        break
            except Exception:
                pass

            # Try to read from latest bus message via inspector-style cache
            if actual_value is None:
                try:
                    bus = robot._bus
                    for sub in bus._subs:
                        if hasattr(sub, 'received') and sub.received > 0:
                            pass
                except Exception:
                    pass

            # If we still can't resolve, default to True (don't block mission)
            if actual_value is None:
                logger.debug("[PLANNER] Could not resolve '%s' — condition passes by default", left_str)
                return True

            result = op_fn(float(actual_value), target_value)
            logger.info("[PLANNER] Condition '%s': %s %s %s = %s",
                        condition, actual_value, op_str, target_value, result)
            return bool(result)

        except Exception as e:
            logger.warning("[PLANNER] Condition eval error for '%s': %s", condition, e)
            return True  # Fail-open: don't block mission on eval errors
