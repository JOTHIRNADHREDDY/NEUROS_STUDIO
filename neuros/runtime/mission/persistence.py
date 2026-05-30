"""
NEUROS Mission Persistence

Handles saving and loading missions for recovery.
"""

import json
import logging
import os
from pathlib import Path

from neuros.runtime.mission.models import Mission, MissionStep, MissionStatus

logger = logging.getLogger("neuros.runtime.mission.persistence")


class MissionPersistence:
    def __init__(self, storage_dir: str = ".neuros/missions"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, mission: Mission) -> None:
        """Save a mission to disk."""
        path = self.storage_dir / f"{mission.mission_id}.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(mission.to_dict(), f, indent=2)
            logger.debug("Saved mission %s to disk", mission.mission_id)
        except Exception as e:
            logger.error("Failed to save mission %s: %s", mission.mission_id, e)

    def load_active_mission(self) -> Mission | None:
        """Load the most recent active/pending mission, if any."""
        # For MVP, just scan the directory. In a real system, use SQLite.
        try:
            for file_path in self.storage_dir.glob("*.json"):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("status") in (MissionStatus.RUNNING.value, MissionStatus.PAUSED.value):
                        return self._deserialize(data)
        except Exception as e:
            logger.error("Failed to load active mission: %s", e)
        return None
        
    def _deserialize(self, data: dict) -> Mission:
        mission = Mission(
            goal=data["goal"],
            mission_id=data["mission_id"],
            status=MissionStatus(data["status"]),
            created_at=data["created_at"],
            started_at=data["started_at"],
            completed_at=data["completed_at"]
        )
        for s_data in data.get("steps", []):
            step = MissionStep(
                skill_name=s_data["skill_name"],
                params={}, # Parameters are omitted in the simple serialization for now
                status=MissionStatus(s_data["status"]),
                task_id=s_data.get("task_id")
            )
            mission.steps.append(step)
        return mission
