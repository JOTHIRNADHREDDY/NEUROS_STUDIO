"""
neuros.nodes.vision.lidar
==========================
LiDAR Node — Phase 2, Domain B.

Supports
--------
  RPLiDAR A1 / A2 / A3 / S1 / S2  (Slamtec, serial USB)
  Simulated LiDAR (synthetic scan for testing and simulation)

Published topics
----------------
  /robot/sensor/lidar/<name>/scan       full 360° scan
  /robot/sensor/lidar/<name>/closest    nearest obstacle point
  /robot/sensor/lidar/<name>/sectors    8-sector summary (N/NE/E/SE/S/SW/W/NW)
  /robot/sensor/lidar/<name>/status     device status / health

Scan payload
------------
  {
    "ranges":    [float…],   # distance in metres, index = angle in degrees
    "angles":    [float…],   # corresponding angles (degrees)
    "min_range": float,
    "max_range": float,
    "n_points":  int,
    "scan_time_ms": float,
  }

Install
-------
  pip install rplidar-roboticia   (for real RPLiDAR hardware)
"""

from __future__ import annotations

import logging
import math
import time
from typing import List, Optional, Tuple

from neuros.nodes.base import Node, NodePriority

logger = logging.getLogger("neuros.nodes.vision.lidar")

_DEG2RAD = math.pi / 180.0
_RAD2DEG = 180.0 / math.pi

# Sectors for obstacle summary
_SECTOR_NAMES = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
_SECTOR_WIDTH = 45.0   # degrees per sector


class LiDARNode(Node):
    """
    LiDAR sensor node.

    Parameters
    ----------
    name        : node identifier
    port        : serial port for RPLiDAR (e.g. "/dev/ttyUSB0")
    baud        : baud rate (default 115200 for A1/A2)
    mode        : "rplidar" | "simulate"
    hz          : scan rate (default 10 Hz = ~10 rotations/s for RPLiDAR A1)
    min_dist_m  : filter out readings below this distance (default 0.15m)
    max_dist_m  : filter out readings above this distance (default 12.0m)

    Simulation mode
    ---------------
        lidar = LiDARNode("lidar", mode="simulate")
        lidar.inject_obstacle(angle_deg=90, distance_m=1.5)   # wall at 90°, 1.5m

    Example (real hardware)
    -----------------------
        lidar = LiDARNode("lidar", port="/dev/ttyUSB0", mode="rplidar", hz=10)
        robot.add_node(lidar)
    """

    def __init__(
        self,
        name:       str           = "lidar",
        *,
        port:       str           = "/dev/ttyUSB0",
        baud:       int           = 115_200,
        mode:       str           = "simulate",
        hz:         float         = 10.0,
        min_dist_m: float         = 0.15,
        max_dist_m: float         = 12.0,
        priority:   NodePriority  = NodePriority.HIGH,
    ) -> None:
        super().__init__(name, hz=hz, priority=priority)
        self._port      = port
        self._baud      = baud
        self._mode      = mode
        self._min_dist  = min_dist_m
        self._max_dist  = max_dist_m
        self._lidar_dev = None

        # Simulation state
        self._sim_obstacles: List[Tuple[float, float]] = []   # (angle_deg, dist_m)
        self._sim_noise     = 0.02   # ±2cm noise

        # Latest scan (accessible without bus)
        self.ranges:  List[float] = []
        self.angles:  List[float] = []

    def configure(self) -> None:
        if self._mode == "rplidar":
            self._init_rplidar()
        logger.info("[LIDAR] '%s' mode=%s port=%s hz=%.1f",
                    self.name, self._mode, self._port, self.hz)

    def _init_rplidar(self) -> None:
        try:
            from rplidar import RPLidar
            self._lidar_dev = RPLidar(self._port, baudrate=self._baud)
            info   = self._lidar_dev.get_info()
            health = self._lidar_dev.get_health()
            logger.info("[LIDAR] RPLidar info=%s health=%s", info, health)
            self._lidar_dev.start_motor()
        except ImportError:
            logger.warning("[LIDAR] rplidar-roboticia not installed — "
                           "falling back to simulation")
            self._mode = "simulate"
        except Exception as e:
            logger.error("[LIDAR] RPLidar init failed: %s — using simulation", e)
            self._mode = "simulate"

    def tick(self) -> None:
        t0 = time.monotonic()

        ranges, angles = self._get_scan()
        if not ranges:
            return

        self.ranges = ranges
        self.angles = angles
        n           = len(ranges)
        valid       = [r for r in ranges if self._min_dist <= r <= self._max_dist]
        scan_ms     = (time.monotonic() - t0) * 1000

        # Full scan
        self.publish(f"/robot/sensor/lidar/{self.name}/scan", {
            "ranges":       ranges,
            "angles":       angles,
            "min_range":    min(valid, default=0.0),
            "max_range":    max(valid, default=0.0),
            "n_points":     n,
            "scan_time_ms": round(scan_ms, 2),
        })

        # Closest obstacle
        if valid:
            min_r  = min(valid)
            min_i  = ranges.index(min_r)
            min_a  = angles[min_i] if angles else 0.0
            self.publish(f"/robot/sensor/lidar/{self.name}/closest", {
                "distance_m": round(min_r,  3),
                "angle_deg":  round(min_a,  1),
            })

        # 8-sector summary
        sectors = self._compute_sectors(ranges, angles)
        self.publish(f"/robot/sensor/lidar/{self.name}/sectors", {
            "sectors": sectors,
        })

    def _get_scan(self) -> Tuple[List[float], List[float]]:
        if self._mode == "rplidar" and self._lidar_dev:
            return self._read_rplidar()
        return self._simulate_scan()

    def _read_rplidar(self) -> Tuple[List[float], List[float]]:
        try:
            scan_data = next(self._lidar_dev.iter_scans())
            angles  = [m[1] for m in scan_data]
            ranges  = [m[2] / 1000.0 for m in scan_data]   # mm → m
            return ranges, angles
        except Exception as e:
            logger.debug("[LIDAR] read error: %s", e)
            return [], []

    def _simulate_scan(self) -> Tuple[List[float], List[float]]:
        import random
        rng    = random.Random()
        angles = list(range(360))
        ranges = [self._max_dist] * 360   # open space default

        # Apply injected obstacles
        for obs_a, obs_d in self._sim_obstacles:
            # Spread obstacle across ±5°
            for delta in range(-5, 6):
                idx = int(obs_a + delta) % 360
                d   = obs_d + rng.gauss(0, self._sim_noise)
                ranges[idx] = max(self._min_dist, min(self._max_dist, d))

        return ranges, [float(a) for a in angles]

    def _compute_sectors(
        self,
        ranges: List[float],
        angles: List[float],
    ) -> dict:
        sectors: dict = {s: self._max_dist for s in _SECTOR_NAMES}
        for r, a in zip(ranges, angles):
            if not (self._min_dist <= r <= self._max_dist):
                continue
            sector_idx = int((a % 360) / _SECTOR_WIDTH) % 8
            s_name     = _SECTOR_NAMES[sector_idx]
            sectors[s_name] = min(sectors[s_name], r)
        return {k: round(v, 3) for k, v in sectors.items()}

    def inject_obstacle(self, angle_deg: float, distance_m: float) -> None:
        """Add a simulated obstacle at `angle_deg` degrees, `distance_m` metres."""
        self._sim_obstacles.append((angle_deg % 360, distance_m))

    def clear_obstacles(self) -> None:
        self._sim_obstacles.clear()

    def destroy(self) -> None:
        if self._lidar_dev:
            try:
                self._lidar_dev.stop()
                self._lidar_dev.stop_motor()
                self._lidar_dev.disconnect()
            except Exception:
                pass
        super().destroy()
