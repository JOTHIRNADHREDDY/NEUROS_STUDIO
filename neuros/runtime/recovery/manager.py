"""
NEUROS Recovery Manager

Listens for system-level failure events and orchestrates recovery actions.
"""

import logging
from typing import Any

from neuros.runtime.recovery.policies import DEFAULT_POLICIES, RecoveryAction

logger = logging.getLogger("neuros.runtime.recovery")

class RecoveryManager:
    def __init__(
        self,
        mission_manager: Any,
        execution_manager: Any,
        emergency_stop: Any,
        policies: dict[str, RecoveryAction] | None = None
    ):
        self._mission = mission_manager
        self._execution = execution_manager
        self._estop = emergency_stop
        self._policies = policies or DEFAULT_POLICIES

    def handle_event(self, event_type: str, details: dict[str, Any]) -> None:
        """Handle a critical failure event."""
        action = self._policies.get(event_type, RecoveryAction.IGNORE)
        logger.warning("Recovery Event: %s -> Action: %s (Details: %s)", event_type, action.name, details)
        
        self._execute_action(action, event_type)

    def _execute_action(self, action: RecoveryAction, event_type: str) -> None:
        if action == RecoveryAction.STOP_ROBOT:
            logger.critical("Recovery initiating STOP_ROBOT due to %s", event_type)
            # We don't trigger E-Stop directly unless it's a safety violation,
            # but we cancel all active tasks.
            import asyncio
            asyncio.create_task(self._execution.cancel_all())
            
        elif action == RecoveryAction.PAUSE_MISSION:
            logger.info("Recovery pausing mission due to %s", event_type)
            if self._mission.active_mission:
                self._mission.active_mission.status = "paused" # Ideally via a MissionManager method
                import asyncio
                asyncio.create_task(self._execution.cancel_all())

        elif action == RecoveryAction.SAVE_AND_SHUTDOWN:
            logger.critical("Recovery initiating SAVE_AND_SHUTDOWN due to %s", event_type)
            if self._mission.active_mission:
                self._mission.active_mission.status = "paused"
            # In a real system, this sends a shutdown signal to the daemon
            import signal
            import os
            try:
                os.kill(os.getpid(), signal.SIGINT)
            except Exception:
                pass
