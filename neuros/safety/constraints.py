"""
NEUROS Safety Constraints

Defines all safety limit dataclasses that the Validator uses
to check commands before they reach hardware.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("neuros.safety.constraints")


@dataclass
class MotorConstraints:
    """Limits for motor actuators."""
    max_pwm: int = 200
    max_speed_ms: float = 1.5
    min_speed_ms: float = 0.0
    max_acceleration: float = 2.0
    max_current_amps: float = 10.0

    def check_pwm(self, pwm: int) -> bool:
        return 0 <= pwm <= self.max_pwm

    def check_speed(self, speed: float) -> bool:
        return self.min_speed_ms <= abs(speed) <= self.max_speed_ms


@dataclass
class ServoConstraints:
    """Limits for servo actuators."""
    min_angle: float = 0.0
    max_angle: float = 180.0
    max_speed_dps: float = 300.0  # degrees per second

    def check_angle(self, angle: float) -> bool:
        return self.min_angle <= angle <= self.max_angle


@dataclass
class BatteryConstraints:
    """Limits for battery monitoring."""
    min_voltage: float = 10.5
    critical_voltage: float = 9.5
    max_voltage: float = 14.8
    max_current_amps: float = 20.0

    def is_safe(self, voltage: float) -> bool:
        return voltage >= self.min_voltage

    def is_critical(self, voltage: float) -> bool:
        return voltage <= self.critical_voltage


@dataclass
class TemperatureConstraints:
    """Limits for thermal monitoring."""
    max_celsius: float = 75.0
    warning_celsius: float = 65.0
    min_celsius: float = -10.0

    def is_safe(self, temp: float) -> bool:
        return self.min_celsius <= temp <= self.max_celsius

    def is_warning(self, temp: float) -> bool:
        return temp >= self.warning_celsius


@dataclass
class WorkspaceConstraints:
    """Physical workspace boundaries (meters)."""
    max_x: float = 10.0
    min_x: float = -10.0
    max_y: float = 10.0
    min_y: float = -10.0
    max_z: float = 5.0
    min_z: float = 0.0

    def is_within_bounds(self, x: float, y: float, z: float = 0.0) -> bool:
        return (
            self.min_x <= x <= self.max_x
            and self.min_y <= y <= self.max_y
            and self.min_z <= z <= self.max_z
        )


@dataclass
class JointConstraints:
    """Limits for robotic arm joints."""
    joint_limits: dict[str, tuple[float, float]] = field(default_factory=dict)
    max_velocity_rads: float = 3.14
    max_torque_nm: float = 50.0

    def check_joint(self, joint_name: str, angle: float) -> bool:
        if joint_name not in self.joint_limits:
            logger.warning("No limits defined for joint '%s', rejecting.", joint_name)
            return False
        min_a, max_a = self.joint_limits[joint_name]
        return min_a <= angle <= max_a


@dataclass
class SafetyConstraints:
    """Aggregates all safety constraints into a single object."""
    motor: MotorConstraints = field(default_factory=MotorConstraints)
    servo: ServoConstraints = field(default_factory=ServoConstraints)
    battery: BatteryConstraints = field(default_factory=BatteryConstraints)
    temperature: TemperatureConstraints = field(default_factory=TemperatureConstraints)
    workspace: WorkspaceConstraints = field(default_factory=WorkspaceConstraints)
    joints: JointConstraints = field(default_factory=JointConstraints)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SafetyConstraints:
        """Load constraints from a config dictionary (e.g., parsed from safety.yaml)."""
        limits = data.get("limits", {})
        return cls(
            motor=MotorConstraints(**limits.get("motor", {})),
            servo=ServoConstraints(**limits.get("servo", {})),
            battery=BatteryConstraints(**limits.get("battery", {})),
            temperature=TemperatureConstraints(**limits.get("temperature", {})),
            workspace=WorkspaceConstraints(**limits.get("workspace", {})),
            joints=JointConstraints(**limits.get("joints", {})),
        )
