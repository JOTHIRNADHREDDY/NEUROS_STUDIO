"""NEUROS V3.1 — Skill Validator.

Validates that a target robot has the capabilities required to run a specific skill.
"""

import logging
from typing import List, Dict, Any
from neuros.core.capability_registry import CapabilityRegistry

logger = logging.getLogger(__name__)

class SkillValidator:
    """Validates skills against robot capabilities."""

    def __init__(self, capability_registry: CapabilityRegistry):
        self.capability_registry = capability_registry

    def validate(self, robot_id: str, skill: Dict[str, Any]) -> bool:
        """Check if a robot can execute this skill."""
        required_caps = skill.get("required_capabilities", [])
        robot_caps = self.capability_registry.get_capabilities(robot_id)
        
        missing = [cap for cap in required_caps if cap not in robot_caps]
        
        if missing:
            logger.error("Validation failed: Robot %r missing capabilities %s for skill %r", 
                         robot_id, missing, skill.get("name"))
            return False
            
        logger.info("Validation passed: Robot %r can run skill %r", robot_id, skill.get("name"))
        return True
