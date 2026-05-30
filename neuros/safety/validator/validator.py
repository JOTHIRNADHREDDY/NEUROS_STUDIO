"""NEUROS V3 — Safety Validator.

Validates speed, torque, distance, power, and motion limits
offline before any command is executed by the drivers.
"""

from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)

class SafetyLimits:
    """Pre-defined safety limits for offline validation."""
    max_speed: float = 1.0       # m/s
    max_torque: float = 10.0     # Nm
    max_distance: float = 5.0    # m
    min_battery: float = 15.0    # percentage

class SafetyValidator:
    """Validates commands against hard-coded safety constraints."""

    def __init__(self) -> None:
        self.limits = SafetyLimits()

    def validate_command(self, tool_name: str, kwargs: Dict[str, Any], current_battery: float) -> bool:
        """Run safety checks before execution.
        
        Returns:
            True if the command is safe, False otherwise.
        """
        logger.debug("Validating command %r with args %s", tool_name, kwargs)

        if current_battery < self.limits.min_battery:
            logger.error("Safety Violation: Battery too low (%.1f%%)", current_battery)
            return False

        if tool_name == "move":
            speed = kwargs.get("speed", 0.0)
            distance = kwargs.get("distance", 0.0)
            
            if abs(speed) > self.limits.max_speed:
                logger.error("Safety Violation: Speed %.2f exceeds max %.2f", speed, self.limits.max_speed)
                return False
                
            if abs(distance) > self.limits.max_distance:
                logger.error("Safety Violation: Distance %.2f exceeds max %.2f", distance, self.limits.max_distance)
                return False

        if tool_name == "apply_torque":
            torque = kwargs.get("torque", 0.0)
            if abs(torque) > self.limits.max_torque:
                logger.error("Safety Violation: Torque %.2f exceeds max %.2f", torque, self.limits.max_torque)
                return False

        return True
