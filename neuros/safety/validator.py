"""
NEUROS Safety Validator

Intercepts ALL commands before they reach the HAL.
No command bypasses the validator. This is the final safety gate.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from neuros.safety.constraints import SafetyConstraints

logger = logging.getLogger("neuros.safety.validator")


class ValidationStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"


@dataclass
class ValidationResult:
    """Result of a safety validation check."""
    status: ValidationStatus
    command_type: str
    checks: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_safe(self) -> bool:
        return self.status != ValidationStatus.FAILED

    def add_check(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append({"name": name, "passed": passed, "detail": detail})
        if not passed:
            self.errors.append(f"[{name}] {detail}")
            self.status = ValidationStatus.FAILED

    def add_warning(self, name: str, detail: str) -> None:
        self.warnings.append(f"[{name}] {detail}")
        if self.status == ValidationStatus.PASSED:
            self.status = ValidationStatus.WARNING


class SafetyValidator:
    """
    Validates all robot commands against safety constraints.

    Usage:
        validator = SafetyValidator(constraints)
        result = validator.validate_motor_command(pwm=255, speed=2.0)
        if result.is_safe:
            # proceed to HAL
        else:
            # reject command
    """

    def __init__(self, constraints: SafetyConstraints | None = None) -> None:
        self._constraints = constraints or SafetyConstraints()
        self._enabled = True
        self._violation_count = 0
        self._total_checks = 0
        logger.info("SafetyValidator initialized with constraints.")

    @property
    def constraints(self) -> SafetyConstraints:
        return self._constraints

    @constraints.setter
    def constraints(self, value: SafetyConstraints) -> None:
        self._constraints = value
        logger.info("Safety constraints updated.")

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True
        logger.info("SafetyValidator ENABLED.")

    def disable(self) -> None:
        self._enabled = False
        logger.warning("SafetyValidator DISABLED — all commands will pass.")

    @property
    def stats(self) -> dict[str, int]:
        return {
            "total_checks": self._total_checks,
            "violations": self._violation_count,
        }

    def validate_motor_command(
        self, pwm: int | None = None, speed: float | None = None
    ) -> ValidationResult:
        """Validate a motor command against motor constraints."""
        self._total_checks += 1
        result = ValidationResult(
            status=ValidationStatus.PASSED, command_type="motor"
        )

        if not self._enabled:
            return result

        mc = self._constraints.motor

        if pwm is not None:
            passed = mc.check_pwm(pwm)
            result.add_check(
                "pwm_limit",
                passed,
                f"PWM {pwm} {'within' if passed else 'exceeds'} max {mc.max_pwm}",
            )

        if speed is not None:
            passed = mc.check_speed(speed)
            result.add_check(
                "speed_limit",
                passed,
                f"Speed {speed} m/s {'within' if passed else 'exceeds'} max {mc.max_speed_ms} m/s",
            )

        if not result.is_safe:
            self._violation_count += 1
            logger.warning("Motor command REJECTED: %s", result.errors)

        return result

    def validate_servo_command(self, angle: float) -> ValidationResult:
        """Validate a servo command against servo constraints."""
        self._total_checks += 1
        result = ValidationResult(
            status=ValidationStatus.PASSED, command_type="servo"
        )

        if not self._enabled:
            return result

        sc = self._constraints.servo
        passed = sc.check_angle(angle)
        result.add_check(
            "angle_limit",
            passed,
            f"Angle {angle}° {'within' if passed else 'outside'} [{sc.min_angle}, {sc.max_angle}]",
        )

        if not result.is_safe:
            self._violation_count += 1
            logger.warning("Servo command REJECTED: %s", result.errors)

        return result

    def validate_battery(self, voltage: float) -> ValidationResult:
        """Check battery voltage against safety thresholds."""
        self._total_checks += 1
        result = ValidationResult(
            status=ValidationStatus.PASSED, command_type="battery"
        )

        if not self._enabled:
            return result

        bc = self._constraints.battery

        if bc.is_critical(voltage):
            result.add_check(
                "critical_voltage",
                False,
                f"Battery voltage {voltage}V is CRITICAL (below {bc.critical_voltage}V)",
            )
            self._violation_count += 1
            logger.critical("Battery CRITICAL: %sV", voltage)
        elif not bc.is_safe(voltage):
            result.add_warning(
                "low_voltage",
                f"Battery voltage {voltage}V below minimum {bc.min_voltage}V",
            )
            logger.warning("Battery LOW: %sV", voltage)

        return result

    def validate_temperature(self, temperature: float) -> ValidationResult:
        """Check temperature against thermal limits."""
        self._total_checks += 1
        result = ValidationResult(
            status=ValidationStatus.PASSED, command_type="temperature"
        )

        if not self._enabled:
            return result

        tc = self._constraints.temperature

        if not tc.is_safe(temperature):
            result.add_check(
                "max_temperature",
                False,
                f"Temperature {temperature}°C exceeds max {tc.max_celsius}°C",
            )
            self._violation_count += 1
            logger.critical("Temperature CRITICAL: %s°C", temperature)
        elif tc.is_warning(temperature):
            result.add_warning(
                "high_temperature",
                f"Temperature {temperature}°C above warning threshold {tc.warning_celsius}°C",
            )

        return result

    def validate_workspace(
        self, x: float, y: float, z: float = 0.0
    ) -> ValidationResult:
        """Check if a target position is within the workspace bounds."""
        self._total_checks += 1
        result = ValidationResult(
            status=ValidationStatus.PASSED, command_type="workspace"
        )

        if not self._enabled:
            return result

        wc = self._constraints.workspace
        passed = wc.is_within_bounds(x, y, z)
        result.add_check(
            "workspace_bounds",
            passed,
            f"Position ({x}, {y}, {z}) {'within' if passed else 'outside'} workspace bounds",
        )

        if not result.is_safe:
            self._violation_count += 1
            logger.warning("Workspace violation: (%s, %s, %s)", x, y, z)

        return result

    def validate_navigation(
        self, goal_x: float, goal_y: float, speed: float | None = None
    ) -> ValidationResult:
        """Validate a navigation goal combining workspace and speed checks."""
        self._total_checks += 1
        result = ValidationResult(
            status=ValidationStatus.PASSED, command_type="navigation"
        )

        if not self._enabled:
            return result

        # Check workspace
        wc = self._constraints.workspace
        in_bounds = wc.is_within_bounds(goal_x, goal_y)
        result.add_check(
            "goal_in_workspace",
            in_bounds,
            f"Goal ({goal_x}, {goal_y}) {'within' if in_bounds else 'outside'} workspace",
        )

        # Check speed if provided
        if speed is not None:
            mc = self._constraints.motor
            speed_ok = mc.check_speed(speed)
            result.add_check(
                "nav_speed_limit",
                speed_ok,
                f"Nav speed {speed} m/s {'within' if speed_ok else 'exceeds'} max {mc.max_speed_ms} m/s",
            )

        if not result.is_safe:
            self._violation_count += 1
            logger.warning("Navigation command REJECTED: %s", result.errors)

        return result

    def validate_joint(self, joint_name: str, angle: float) -> ValidationResult:
        """Validate a joint position for robotic arms."""
        self._total_checks += 1
        result = ValidationResult(
            status=ValidationStatus.PASSED, command_type="joint"
        )

        if not self._enabled:
            return result

        jc = self._constraints.joints
        passed = jc.check_joint(joint_name, angle)
        result.add_check(
            "joint_limit",
            passed,
            f"Joint '{joint_name}' angle {angle} {'within' if passed else 'outside'} limits",
        )

        if not result.is_safe:
            self._violation_count += 1
            logger.warning("Joint command REJECTED: %s", result.errors)

        return result

    def validate_skill_params(
        self, skill_name: str, params: dict[str, Any]
    ) -> ValidationResult:
        """
        Generic validation for skill parameters.
        Dispatches to specific validators based on parameter keys.
        """
        self._total_checks += 1
        result = ValidationResult(
            status=ValidationStatus.PASSED, command_type=f"skill:{skill_name}"
        )

        if not self._enabled:
            return result

        # Check motor-related params
        if "pwm" in params:
            sub = self.validate_motor_command(pwm=params["pwm"])
            result.checks.extend(sub.checks)
            result.errors.extend(sub.errors)
            if not sub.is_safe:
                result.status = ValidationStatus.FAILED

        if "speed" in params:
            sub = self.validate_motor_command(speed=params["speed"])
            result.checks.extend(sub.checks)
            result.errors.extend(sub.errors)
            if not sub.is_safe:
                result.status = ValidationStatus.FAILED

        # Check servo
        if "angle" in params:
            sub = self.validate_servo_command(params["angle"])
            result.checks.extend(sub.checks)
            result.errors.extend(sub.errors)
            if not sub.is_safe:
                result.status = ValidationStatus.FAILED

        # Check workspace
        if "x" in params and "y" in params:
            z = params.get("z", 0.0)
            sub = self.validate_workspace(params["x"], params["y"], z)
            result.checks.extend(sub.checks)
            result.errors.extend(sub.errors)
            if not sub.is_safe:
                result.status = ValidationStatus.FAILED

        if not result.is_safe:
            self._violation_count += 1

        return result
