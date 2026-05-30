"""
NEUROS Robot State Memory

Live, in-memory snapshot of the robot's current physical state.
Updated by sensor feeds and the HAL. Read by agents and skills.
"""

from __future__ import annotations

import logging
import time
import threading
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("neuros.memory.robot_state")


@dataclass
class Pose:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0


@dataclass
class BatteryState:
    voltage: float = 0.0
    current: float = 0.0
    percentage: float = 100.0
    is_charging: bool = False


@dataclass
class SystemHealth:
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    temperature_c: float = 0.0
    disk_percent: float = 0.0


class RobotStateMemory:
    """
    Thread-safe snapshot of the robot's current state.

    Usage:
        rsm = RobotStateMemory()
        rsm.update_pose(x=1.0, y=2.0, yaw=0.5)
        rsm.update_battery(voltage=12.1, percentage=85)
        snapshot = rsm.snapshot()
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pose = Pose()
        self._battery = BatteryState()
        self._health = SystemHealth()
        self._velocities: dict[str, float] = {"linear": 0.0, "angular": 0.0}
        self._sensors: dict[str, Any] = {}
        self._last_updated: dict[str, float] = {}
        logger.info("RobotStateMemory initialized.")

    def update_pose(self, **kwargs: float) -> None:
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self._pose, k):
                    setattr(self._pose, k, v)
            self._last_updated["pose"] = time.time()

    def update_battery(self, **kwargs: Any) -> None:
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self._battery, k):
                    setattr(self._battery, k, v)
            self._last_updated["battery"] = time.time()

    def update_health(self, **kwargs: float) -> None:
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self._health, k):
                    setattr(self._health, k, v)
            self._last_updated["health"] = time.time()

    def update_velocity(self, linear: float = 0.0, angular: float = 0.0) -> None:
        with self._lock:
            self._velocities["linear"] = linear
            self._velocities["angular"] = angular
            self._last_updated["velocity"] = time.time()

    def update_sensor(self, sensor_id: str, data: Any) -> None:
        with self._lock:
            self._sensors[sensor_id] = data
            self._last_updated[f"sensor:{sensor_id}"] = time.time()

    def get_pose(self) -> Pose:
        with self._lock:
            return Pose(
                x=self._pose.x, y=self._pose.y, z=self._pose.z,
                roll=self._pose.roll, pitch=self._pose.pitch, yaw=self._pose.yaw,
            )

    def get_battery(self) -> BatteryState:
        with self._lock:
            return BatteryState(
                voltage=self._battery.voltage,
                current=self._battery.current,
                percentage=self._battery.percentage,
                is_charging=self._battery.is_charging,
            )

    def get_sensor(self, sensor_id: str) -> Any:
        with self._lock:
            return self._sensors.get(sensor_id)

    def snapshot(self) -> dict[str, Any]:
        """Return a full snapshot of the robot state."""
        with self._lock:
            return {
                "pose": {
                    "x": self._pose.x, "y": self._pose.y, "z": self._pose.z,
                    "roll": self._pose.roll, "pitch": self._pose.pitch, "yaw": self._pose.yaw,
                },
                "battery": {
                    "voltage": self._battery.voltage,
                    "current": self._battery.current,
                    "percentage": self._battery.percentage,
                    "is_charging": self._battery.is_charging,
                },
                "health": {
                    "cpu_percent": self._health.cpu_percent,
                    "memory_percent": self._health.memory_percent,
                    "temperature_c": self._health.temperature_c,
                },
                "velocity": dict(self._velocities),
                "sensors": dict(self._sensors),
                "last_updated": dict(self._last_updated),
            }
