"""
NEUROS Mission Manager

Manages the execution of high-level missions containing multiple skills.
"""

import asyncio
import logging
import time
from typing import Any

from neuros.runtime.mission.models import Mission, MissionStep, MissionStatus
from neuros.runtime.mission.persistence import MissionPersistence

logger = logging.getLogger("neuros.runtime.mission")


class MissionManager:
    def __init__(self, execution_manager: Any, bus_publish: Any = None) -> None:
        self._execution = execution_manager
        self._bus_publish = bus_publish
        self._persistence = MissionPersistence()
        
        self._active_mission: Mission | None = None
        self._mission_task: asyncio.Task | None = None
        
        # Recover active mission if exists
        recovered = self._persistence.load_active_mission()
        if recovered:
            logger.info("Recovered active mission %s", recovered.mission_id)
            self._active_mission = recovered
            # NOTE: Actual resumption is triggered externally by RecoveryManager

    @property
    def active_mission(self) -> Mission | None:
        return self._active_mission

    async def start_mission(self, goal: str, steps: list[dict[str, Any]]) -> str:
        """Start a new mission."""
        if self._active_mission and self._active_mission.status in (MissionStatus.RUNNING, MissionStatus.PAUSED):
            raise RuntimeError("A mission is already active.")

        mission_steps = [MissionStep(skill_name=s["skill_name"], params=s.get("params", {})) for s in steps]
        mission = Mission(goal=goal, steps=mission_steps, started_at=time.time(), status=MissionStatus.RUNNING)
        self._active_mission = mission
        self._persistence.save(mission)

        self._mission_task = asyncio.create_task(self._mission_loop(mission))
        logger.info("Started mission %s: %s", mission.mission_id, goal)
        
        if self._bus_publish:
            self._bus_publish("/robot/mission/started", {"mission_id": mission.mission_id, "goal": goal})
            
        return mission.mission_id

    async def _mission_loop(self, mission: Mission) -> None:
        try:
            for step in mission.steps:
                if step.status == MissionStatus.COMPLETED:
                    continue # Skip recovered completed steps

                step.status = MissionStatus.RUNNING
                step.started_at = time.time()
                self._persistence.save(mission)

                # Submit to Execution Manager
                task_id = await self._execution.submit(
                    skill_name=step.skill_name,
                    params=step.params,
                    source=f"mission_{mission.mission_id}"
                )
                step.task_id = task_id

                # Wait for completion
                while True:
                    await asyncio.sleep(0.5)
                    task_entry = self._execution.get_task(task_id)
                    if not task_entry:
                        break
                    
                    if task_entry.status.value == "completed":
                        step.status = MissionStatus.COMPLETED
                        step.result = task_entry.result
                        break
                    elif task_entry.status.value in ("failed", "cancelled", "timed_out"):
                        step.status = MissionStatus.FAILED
                        step.error = task_entry.error
                        raise RuntimeError(f"Skill {step.skill_name} failed: {task_entry.error}")

                step.completed_at = time.time()
                self._persistence.save(mission)

            mission.status = MissionStatus.COMPLETED
            mission.completed_at = time.time()
            logger.info("Mission %s COMPLETED successfully.", mission.mission_id)
            if self._bus_publish:
                self._bus_publish("/robot/mission/completed", {"mission_id": mission.mission_id})

        except Exception as e:
            logger.error("Mission %s FAILED: %s", mission.mission_id, e)
            mission.status = MissionStatus.FAILED
            mission.error = str(e)
            mission.completed_at = time.time()
            if self._bus_publish:
                self._bus_publish("/robot/mission/failed", {"mission_id": mission.mission_id, "error": str(e)})
        finally:
            self._persistence.save(mission)

    async def cancel_mission(self) -> None:
        """Cancel the currently active mission."""
        if not self._active_mission:
            return

        if self._mission_task:
            self._mission_task.cancel()
            
        self._active_mission.status = MissionStatus.CANCELLED
        self._active_mission.completed_at = time.time()
        self._persistence.save(self._active_mission)
        logger.info("Mission %s CANCELLED.", self._active_mission.mission_id)
