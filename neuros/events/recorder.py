"""NEUROS V3.1 — Event Recorder.

Hooks for recording COMMAND, MISSION, ERROR, DEVICE, PLUGIN, SKILL, and SAFETY events.
"""

import logging
from typing import Dict, Any
from .store import EventStore

logger = logging.getLogger(__name__)

class EventRecorder:
    """Records events into the EventStore."""

    def __init__(self, store: EventStore):
        self.store = store

    def record_command(self, robot_id: str, command: str, result: Dict[str, Any]) -> None:
        self.store.append("COMMAND", robot_id, {"command": command, "result": result})
        logger.debug("Recorded COMMAND event for %s", robot_id)

    def record_mission(self, robot_id: str, mission_id: str, status: str) -> None:
        self.store.append("MISSION", robot_id, {"mission_id": mission_id, "status": status})
        logger.debug("Recorded MISSION event for %s", robot_id)

    def record_error(self, robot_id: str, error_msg: str, context: str) -> None:
        self.store.append("ERROR", robot_id, {"error": error_msg, "context": context})
        logger.error("Recorded ERROR event for %s: %s", robot_id, error_msg)

    def record_safety(self, robot_id: str, trigger: str, details: Dict[str, Any]) -> None:
        self.store.append("SAFETY", robot_id, {"trigger": trigger, "details": details})
        logger.warning("Recorded SAFETY event for %s: %s", robot_id, trigger)
