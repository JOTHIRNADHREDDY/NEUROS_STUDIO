"""
neuros.nodes.navigation.obstacle_avoidance
===========================================
Reactive obstacle avoidance — Vector Field Histogram (VFH) lite.

Reads LiDAR sector summary and sonar distance data, computes a
safe velocity command, and publishes it to /robot/cmd/velocity.

Algorithm (Phase 2 — VFH lite)
--------------------------------
  1. Build binary obstacle histogram from sector data
  2. Find widest valley (clear sectors) ahead of robot
  3. Steer toward centre of valley at reduced speed
  4. If no valley → stop and rotate to find clear direction

Published topics
----------------
  /robot/cmd/velocity           {"linear": m/s, "angular": rad/s}
  /robot/nav/obstacle/status    {"state": str, "closest_m": float, "steer_deg": float}

Subscribed topics
-----------------
  /robot/sensor/lidar/<name>/sectors    8-sector LiDAR summary
  /robot/sensor/ultrasonic/*/          sonar distance (optional additional guard)

States
------
  "clear"     → drive at full cruise speed
  "caution"   → reduce speed (obstacle 1–2m ahead)
  "avoid"     → turn to clear direction
  "stop"      → obstacle too close in all directions
"""
from __future__ import annotations
import logging, math
from typing import Dict, Optional
from neuros.nodes.base import Node, NodePriority

logger = logging.getLogger("neuros.nodes.nav.obstacle")

# Sector order matches LiDAR node (N, NE, E, SE, S, SW, W, NW)
_SECTORS   = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
_SECT_DEGS = {s: i * 45.0 for i, s in enumerate(_SECTORS)}

_STATE_CLEAR   = "clear"
_STATE_CAUTION = "caution"
_STATE_AVOID   = "avoid"
_STATE_STOP    = "stop"


class ObstacleAvoidanceNode(Node):
    """
    Reactive obstacle avoidance using LiDAR sector data.

    Parameters
    ----------
    name            : node identifier
    lidar_name      : name of the LiDAR node to subscribe to
    cruise_speed    : linear speed when clear (m/s, default 0.4)
    caution_dist_m  : start slowing below this distance (default 1.5m)
    stop_dist_m     : emergency stop below this distance (default 0.3m)
    turn_speed      : angular speed when avoiding (rad/s, default 0.8)
    hz              : control rate (default 20 Hz)
    """

    def __init__(
        self,
        name:           str   = "obstacle_avoidance",
        *,
        lidar_name:     str   = "lidar",
        cruise_speed:   float = 0.4,
        caution_dist_m: float = 1.5,
        stop_dist_m:    float = 0.3,
        turn_speed:     float = 0.8,
        hz:             float = 20.0,
        priority:       NodePriority = NodePriority.HIGH,
    ) -> None:
        super().__init__(name, hz=hz, priority=priority)
        self._lidar_name    = lidar_name
        self._cruise        = cruise_speed
        self._caution_d     = caution_dist_m
        self._stop_d        = stop_dist_m
        self._turn_speed    = turn_speed

        self._sectors: Dict[str, float] = {s: 99.0 for s in _SECTORS}
        self._state:   str              = _STATE_CLEAR
        self._sonar_d: float            = 99.0

    def configure(self) -> None:
        logger.info("[AVOID] '%s' cruise=%.2fm/s stop=%.2fm caution=%.2fm",
                    self.name, self._cruise, self._stop_d, self._caution_d)

    def on_activate(self) -> None:
        self.subscribe(
            f"/robot/sensor/lidar/{self._lidar_name}/sectors",
            self._on_sectors,
        )
        self.subscribe("/robot/sensor/ultrasonic/*", self._on_sonar)

    def _on_sectors(self, msg) -> None:
        self._sectors.update(msg.data.get("sectors", {}))

    def _on_sonar(self, msg) -> None:
        d = msg.data.get("distance_m")
        if d is not None:
            self._sonar_d = float(d)

    def tick(self) -> None:
        forward_dist = min(
            self._sectors.get("N",  99.0),
            self._sectors.get("NE", 99.0),
            self._sectors.get("NW", 99.0),
        )
        # Sonar overrides if closer
        forward_dist = min(forward_dist, self._sonar_d)

        linear  = 0.0
        angular = 0.0

        if forward_dist <= self._stop_d:
            self._state = _STATE_STOP
            linear  = 0.0
            angular = self._turn_speed   # spin to find clear

        elif forward_dist <= self._caution_d:
            # Find best clear direction
            best_dir, best_dist = self._best_direction()
            self._state = _STATE_AVOID if forward_dist < self._caution_d * 0.6 \
                          else _STATE_CAUTION

            speed_factor = (forward_dist - self._stop_d) / (self._caution_d - self._stop_d)
            linear       = self._cruise * speed_factor * 0.5
            # Steer toward best direction
            steer_deg    = _SECT_DEGS.get(best_dir, 0.0)
            if steer_deg > 180:
                steer_deg -= 360
            angular = -math.radians(steer_deg) * 0.5

        else:
            self._state = _STATE_CLEAR
            linear      = self._cruise
            angular     = 0.0

        self.publish("/robot/cmd/velocity", {
            "linear":  round(linear,  3),
            "angular": round(angular, 3),
        })
        self.publish("/robot/nav/obstacle/status", {
            "state":      self._state,
            "closest_m":  round(forward_dist, 3),
            "steer_ang":  round(angular, 3),
        })

    def _best_direction(self):
        """Find the sector with most clearance."""
        return max(self._sectors.items(), key=lambda kv: kv[1])
