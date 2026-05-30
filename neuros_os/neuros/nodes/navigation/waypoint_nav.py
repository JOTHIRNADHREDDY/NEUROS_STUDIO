"""
neuros.nodes.navigation.waypoint_nav
=====================================
Waypoint Navigator — goal-seeking with pure-pursuit controller.
"""
from __future__ import annotations
import logging, math
from collections import deque
from typing import Deque, Optional, Tuple
from neuros.nodes.base import Node, NodePriority

logger = logging.getLogger("neuros.nodes.nav.waypoint")
Waypoint = Tuple[float, float]


class WaypointNavigatorNode(Node):
    """Pure-pursuit waypoint navigator."""

    def __init__(
        self,
        name:               str   = "waypoint_nav",
        *,
        max_linear_speed:   float = 0.5,
        max_angular_speed:  float = 1.5,
        goal_tolerance_m:   float = 0.1,
        lookahead_m:        float = 0.4,
        hz:                 float = 20.0,
        priority:           NodePriority = NodePriority.HIGH,
    ) -> None:
        super().__init__(name, hz=hz, priority=priority)
        self._max_lin  = max_linear_speed
        self._max_ang  = max_angular_speed
        self._tol      = goal_tolerance_m
        self._look     = lookahead_m
        self._queue: Deque[Waypoint] = deque()
        self._nav_state: str = "idle"    # "idle","navigating","arrived","cancelled"
        self._x: float = 0.0
        self._y: float = 0.0
        self._theta: float = 0.0

    def configure(self) -> None:
        logger.info("[WAYNAV] '%s' tol=%.2fm look=%.2fm max_v=%.2fm/s",
                    self.name, self._tol, self._look, self._max_lin)

    def on_activate(self) -> None:
        self.subscribe("/robot/nav/odom/pose",        self._on_pose)
        self.subscribe("/robot/nav/waypoint/goal",    self._on_goal)
        self.subscribe("/robot/nav/waypoint/mission", self._on_mission)
        self.subscribe("/robot/nav/waypoint/cancel",  self._on_cancel)

    def _on_pose(self, msg) -> None:
        self._x     = float(msg.data.get("x",     0.0))
        self._y     = float(msg.data.get("y",     0.0))
        self._theta = float(msg.data.get("theta", 0.0))

    def _on_goal(self, msg) -> None:
        x, y = float(msg.data.get("x", 0)), float(msg.data.get("y", 0))
        self._queue.append((x, y))
        self._nav_state = "navigating"
        logger.info("[WAYNAV] goal added (%.2f, %.2f) queue=%d", x, y, len(self._queue))

    def _on_mission(self, msg) -> None:
        for wp in msg.data.get("waypoints", []):
            self._queue.append((float(wp["x"]), float(wp["y"])))
        if self._queue:
            self._nav_state = "navigating"

    def _on_cancel(self, msg) -> None:
        self._queue.clear()
        self._nav_state = "cancelled"
        self.publish("/robot/cmd/velocity", {"linear": 0.0, "angular": 0.0})

    def tick(self) -> None:
        if not self._queue:
            if self._nav_state == "navigating":
                self._nav_state = "arrived"
                self.publish("/robot/cmd/velocity", {"linear": 0.0, "angular": 0.0})
            self._publish_status(0.0)
            return

        gx, gy = self._queue[0]
        dx, dy  = gx - self._x, gy - self._y
        dist    = math.hypot(dx, dy)

        if dist < self._tol:
            self._queue.popleft()
            if not self._queue:
                self._nav_state = "arrived"
                self.publish("/robot/cmd/velocity", {"linear": 0.0, "angular": 0.0})
            self._publish_status(0.0)
            return

        goal_heading = math.atan2(dy, dx)
        alpha        = _wrap(goal_heading - self._theta)
        curvature    = 2.0 * math.sin(alpha) / max(self._look, 0.01)
        linear       = min(self._max_lin, dist * 0.8)
        angular      = max(-self._max_ang, min(self._max_ang, curvature * linear))

        self.publish("/robot/cmd/velocity", {
            "linear":  round(linear,  3),
            "angular": round(angular, 3),
        })
        self._publish_status(dist)

    def _publish_status(self, dist: float) -> None:
        goal = self._queue[0] if self._queue else None
        self.publish("/robot/nav/waypoint/status", {
            "state":        self._nav_state,
            "distance_m":   round(dist, 3),
            "queue_length": len(self._queue),
            "current_goal": {"x": goal[0], "y": goal[1]} if goal else None,
        })

    def add_waypoint(self, x: float, y: float) -> None:
        self._queue.append((x, y))
        self._nav_state = "navigating"

    def cancel(self) -> None:
        self._queue.clear()
        self._nav_state = "cancelled"

    @property
    def state(self) -> str:
        return self._nav_state

    @property
    def queue_length(self) -> int:
        return len(self._queue)


def _wrap(a: float) -> float:
    while a >  math.pi: a -= 2 * math.pi
    while a < -math.pi: a += 2 * math.pi
    return a
