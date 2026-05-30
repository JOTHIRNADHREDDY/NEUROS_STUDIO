"""
neuros.ai.llm.context
======================
RobotContext — serialises the full robot state into an LLM-ready string.

The LLM needs to know:
  • What hardware is attached (HAL board info)
  • What nodes are running (name, state, hz, tick count)
  • What topics exist on the Neural Bus (recent messages)
  • Current sensor readings (IMU, LiDAR, battery, odometry)
  • Recent anomalies or faults
  • Mission history

ContextBuilder assembles this from a live Robot instance and formats
it as a structured system-prompt block that fits inside the LLM context.

Context window budget
---------------------
  Target: ≤ 2000 tokens for context (leaves room for conversation history)
  Strategy: sensor snapshots (not raw arrays), top-N topics by activity,
            last 5 faults, last 3 mission events.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from neuros.api.robot import Robot


@dataclass
class RobotContext:
    """Snapshot of robot state suitable for inclusion in an LLM prompt."""
    robot_name:     str
    domain:         str
    uptime_s:       float
    kernel_state:   str
    board_info:     dict
    nodes:          List[dict]
    active_topics:  List[dict]
    sensor_snapshot: dict
    recent_faults:  List[dict]
    mission_state:  dict
    timestamp:      float = field(default_factory=time.monotonic)

    def to_prompt_block(self, *, max_tokens: int = 2000) -> str:
        """Render as a structured text block for inclusion in LLM system prompt."""
        lines = [
            f"=== NEUROS ROBOT CONTEXT ===",
            f"Robot:        {self.robot_name}",
            f"Domain:       {self.domain}",
            f"Uptime:       {self.uptime_s:.1f}s",
            f"Kernel:       {self.kernel_state}",
            f"Board:        {self.board_info.get('board', 'unknown')}",
            "",
            "NODES RUNNING:",
        ]
        for n in self.nodes[:15]:
            alive = "✓" if n.get("alive") else "✗"
            lines.append(
                f"  {alive} {n['name']:<24} hz={n.get('hz','?'):<6} "
                f"ticks={n.get('ticks',0):<8} state={n.get('state','?')}"
            )

        lines += ["", "ACTIVE TOPICS (top 10 by traffic):"]
        for t in self.active_topics[:10]:
            lines.append(f"  {t['topic']:<45} msgs={t['count']}")

        lines += ["", "SENSOR SNAPSHOT:"]
        for k, v in self.sensor_snapshot.items():
            lines.append(f"  {k}: {v}")

        if self.recent_faults:
            lines += ["", "RECENT FAULTS:"]
            for f in self.recent_faults[-5:]:
                lines.append(f"  [{f.get('code','?')}] {f.get('detail','')}")

        if self.mission_state:
            lines += ["", "MISSION STATE:"]
            for k, v in self.mission_state.items():
                lines.append(f"  {k}: {v}")

        lines.append("=== END CONTEXT ===")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "robot_name":     self.robot_name,
            "domain":         self.domain,
            "uptime_s":       self.uptime_s,
            "kernel_state":   self.kernel_state,
            "board_info":     self.board_info,
            "nodes":          self.nodes,
            "active_topics":  self.active_topics,
            "sensor_snapshot": self.sensor_snapshot,
            "recent_faults":  self.recent_faults,
            "mission_state":  self.mission_state,
        }


class ContextBuilder:
    """
    Builds a RobotContext snapshot from a live Robot instance.

    Usage
    -----
        builder = ContextBuilder(robot)
        ctx = builder.build()
        print(ctx.to_prompt_block())
    """

    def __init__(self, robot: "Robot") -> None:
        self._robot = robot
        self._sensor_cache: Dict[str, Any] = {}

        # Subscribe to key sensor topics to maintain a live snapshot
        if robot._bus:
            robot._bus.subscribe("/robot/sensor/#",         self._on_sensor)
            robot._bus.subscribe("/robot/nav/odom/pose",    self._on_sensor)
            robot._bus.subscribe("/robot/sensor/battery",   self._on_sensor)
            robot._bus.subscribe("/robot/system/fault",     self._on_fault)

        self._faults: List[dict] = []
        self._mission: dict = {}

    def _on_sensor(self, msg) -> None:
        # Store last value per topic (condensed)
        key = msg.topic.split("/")[-1]
        val = msg.data
        # Compress large payloads (e.g. LiDAR ranges list)
        if isinstance(val, dict):
            compressed = {k: round(v, 3) if isinstance(v, float) else v
                          for k, v in list(val.items())[:6]}
            self._sensor_cache[key] = compressed
        else:
            self._sensor_cache[key] = val

    def _on_fault(self, msg) -> None:
        self._faults.append(msg.data)
        if len(self._faults) > 20:
            self._faults.pop(0)

    def build(self) -> RobotContext:
        robot = self._robot
        kernel_status = robot._kernel.status() if robot._kernel else {}
        bus_metrics   = robot._bus.metrics()   if robot._bus   else {}

        # Node list
        nodes = []
        for nid, info in kernel_status.get("nodes", {}).items():
            node_obj = robot._nodes.get(nid)
            nodes.append({
                "name":  info.get("name", "?"),
                "alive": info.get("alive", False),
                "state": info.get("alive") and "active" or "dead",
                "hz":    getattr(node_obj, "hz", "?") if node_obj else "?",
                "ticks": getattr(node_obj, "_tick_count", 0) if node_obj else 0,
            })

        # Active topics (sorted by message count)
        active_topics = sorted(
            [{"topic": t, "count": m.get("published", 0)}
             for t, m in bus_metrics.items()],
            key=lambda x: -x["count"],
        )

        # Board info
        board_info = {}
        if robot._hal:
            try:
                board_info = robot._hal.board_info()
            except Exception:
                pass

        return RobotContext(
            robot_name      = robot.name,
            domain          = kernel_status.get("domain", "A"),
            uptime_s        = kernel_status.get("uptime_s", 0.0),
            kernel_state    = kernel_status.get("state", "UNKNOWN"),
            board_info      = board_info,
            nodes           = nodes,
            active_topics   = active_topics,
            sensor_snapshot = dict(self._sensor_cache),
            recent_faults   = list(self._faults),
            mission_state   = dict(self._mission),
        )
