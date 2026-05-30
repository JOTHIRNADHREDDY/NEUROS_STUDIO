"""NEUROS V3.1 — Workflow Conditions.

Conditions that must be met for a workflow to proceed.
"""

import logging

logger = logging.getLogger(__name__)

class Condition:
    """Base class for workflow conditions."""
    def evaluate(self, context: dict) -> bool:
        raise NotImplementedError

class RobotOnline(Condition):
    def evaluate(self, context: dict) -> bool:
        robot_status = context.get("robot_status", "offline")
        return robot_status == "online"
