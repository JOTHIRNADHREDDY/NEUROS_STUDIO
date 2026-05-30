"""NEUROS V3.1 — Workflow Executor.

Parses workflow step configs and executes the corresponding logic.
"""

import logging
from typing import Dict, Any
from .actions import ReturnHome, ExecuteSkill

logger = logging.getLogger(__name__)

class WorkflowExecutor:
    """Executes a parsed workflow."""

    def __init__(self, orchestrator: Any):
        self.orchestrator = orchestrator

    def execute_action(self, action_type: str, config: Dict[str, Any], robot_id: str) -> None:
        """Instantiate and execute the action."""
        logger.info("Running workflow action %r on robot %r", action_type, robot_id)
        action = None
        
        if action_type == "ReturnHome":
            action = ReturnHome()
        elif action_type == "ExecuteSkill":
            action = ExecuteSkill(config.get("skill_name", ""))
            
        if action:
            action.execute(robot_id, self.orchestrator)
        else:
            logger.error("Unknown workflow action type: %r", action_type)
