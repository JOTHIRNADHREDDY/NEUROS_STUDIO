"""NEUROS V3.1 — Event Replay.

Produces historical event streams for missions and execution debugging.
"""

import logging
from typing import Dict, Any, List
from .store import EventStore

logger = logging.getLogger(__name__)

class ReplayEngine:
    """Replays events from the Event Store."""

    def __init__(self, store: EventStore):
        self.store = store

    def replay_mission(self, mission_id: str) -> List[Dict[str, Any]]:
        """Fetch all events related to a specific mission."""
        logger.info("Replaying mission %r", mission_id)
        # In a real implementation we would filter strictly by mission_id,
        # but for now we fetch recent missions.
        events = self.store.get_events(event_type="MISSION", limit=100)
        return [e for e in events if e["payload"].get("mission_id") == mission_id]

    def replay_robot_history(self, robot_id: str) -> List[Dict[str, Any]]:
        """Fetch chronological history of a robot's actions."""
        logger.info("Replaying history for robot %r", robot_id)
        return self.store.get_events(robot_id=robot_id, limit=500)
