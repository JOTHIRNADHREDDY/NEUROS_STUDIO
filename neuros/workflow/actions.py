"""NEUROS V3.1 — Workflow Actions.

Actions triggered by a workflow, which must pass through the Safety Validator.
"""

import logging
from typing import Any
from neuros.core.orchestrator.agent import Orchestrator

logger = logging.getLogger(__name__)

class Action:
    """Base class for workflow actions."""
    def execute(self, robot_id: str, orchestrator: Orchestrator) -> Any:
        raise NotImplementedError

class ReturnHome(Action):
    def execute(self, robot_id: str, orchestrator: Orchestrator) -> Any:
        logger.info("Executing ReturnHome action for robot %r", robot_id)
        # Execute mission via orchestrator to ensure it passes through safety logic
        return orchestrator.execute_mission("Return to home base", robot_id)

class ExecuteSkill(Action):
    def __init__(self, skill_name: str):
        self.skill_name = skill_name

    def execute(self, robot_id: str, orchestrator: Orchestrator) -> Any:
        logger.info("Executing ExecuteSkill(%r) action for robot %r", self.skill_name, robot_id)
        return orchestrator.execute_mission(f"Execute skill: {self.skill_name}", robot_id)
