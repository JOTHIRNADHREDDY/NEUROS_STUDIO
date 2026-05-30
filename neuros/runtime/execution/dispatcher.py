"""
NEUROS Task Dispatcher

Pulls tasks from the queue and executes them through the Safety layer
and Skill Engine.
"""

import asyncio
import logging
import time
from typing import Any, Callable

from neuros.runtime.execution.state import TaskEntry, TaskStatus
from neuros.runtime.execution.retry import RetryPolicy

logger = logging.getLogger("neuros.runtime.execution.dispatcher")


class TaskDispatcher:
    def __init__(
        self,
        queue: Any,
        skill_engine: Any = None,
        safety_validator: Any = None,
        sandbox: Any = None,
        emergency_stop: Any = None,
        max_concurrent: int = 3,
    ) -> None:
        self._queue = queue
        self._skill_engine = skill_engine
        self._validator = safety_validator
        self._sandbox = sandbox
        self._estop = emergency_stop
        self._max_concurrent = max_concurrent
        
        self._running = False
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._worker_task: asyncio.Task | None = None
        self._aging_task: asyncio.Task | None = None
        self._on_complete_handlers: list[Callable[[TaskEntry], None]] = []

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        self._aging_task = asyncio.create_task(self._aging_loop())
        logger.info("TaskDispatcher STARTED.")

    async def stop(self) -> None:
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
                
        if self._aging_task:
            self._aging_task.cancel()
            try:
                await self._aging_task
            except asyncio.CancelledError:
                pass
        
        for task in self._active_tasks.values():
            task.cancel()
        self._active_tasks.clear()
        logger.info("TaskDispatcher STOPPED.")

    def register_on_complete(self, handler: Callable[[TaskEntry], None]) -> None:
        self._on_complete_handlers.append(handler)

    def cancel_task(self, task_id: str) -> bool:
        active = self._active_tasks.get(task_id)
        if active:
            active.cancel()
            return True
        return False

    def active_count(self) -> int:
        return len(self._active_tasks)

    async def _aging_loop(self) -> None:
        """Periodically age tasks in the queue to prevent starvation."""
        logger.info("TaskDispatcher aging loop started.")
        while self._running:
            await asyncio.sleep(60.0)  # Age tasks every minute
            try:
                if hasattr(self._queue, "age_tasks"):
                    self._queue.age_tasks(amount=1)
            except Exception as exc:
                logger.error("Error in aging loop: %s", exc)

    async def _worker_loop(self) -> None:
        logger.info("TaskDispatcher worker loop started.")
        while self._running:
            if self._estop and self._estop.is_triggered:
                await asyncio.sleep(0.5)
                continue

            if len(self._active_tasks) >= self._max_concurrent:
                await asyncio.sleep(0.1)
                continue

            entry = await self._queue.get(timeout=1.0)
            if not entry:
                continue
                
            if entry.status == TaskStatus.CANCELLED:
                continue

            active_task = asyncio.create_task(self._execute_task(entry))
            self._active_tasks[entry.task_id] = active_task

    async def _execute_task(self, entry: TaskEntry) -> None:
        task_id = entry.task_id
        entry.status = TaskStatus.RUNNING
        entry.started_at = time.time()

        logger.info("Task %s STARTED: %s@%s", task_id, entry.skill_name, entry.skill_version)

        try:
            # 1. Sandbox Check
            if self._sandbox:
                sandbox_result = self._sandbox.validate_params(entry.params)
                if not sandbox_result.is_safe:
                    raise ValueError(f"Sandbox rejected: {sandbox_result.errors}")

            # 2. Safety Validation
            if self._validator:
                validation = self._validator.validate_skill_params(entry.skill_name, entry.params)
                if not validation.is_safe:
                    raise ValueError(f"Safety rejected: {validation.errors}")

            # 3. E-Stop Check
            if self._estop and not self._estop.check_allowed():
                raise RuntimeError("Emergency stop is active.")

            # 4. Skill Execution
            if self._skill_engine:
                from neuros.skills.base import SkillContext
                context = SkillContext(
                    robot_id="default",
                    device_registry=None,
                    capability_registry=None,
                    bus=None,
                    hal=None,
                    config={},
                )
                
                result = await asyncio.wait_for(
                    self._skill_engine.execute_skill(
                        entry.skill_name,
                        entry.params,
                        context,
                        entry.skill_version,
                    ),
                    timeout=entry.timeout_s,
                )

                if result.success:
                    entry.status = TaskStatus.COMPLETED
                    entry.result = result
                    logger.info("Task %s COMPLETED in %.1fms", task_id, entry.elapsed_ms)
                else:
                    raise RuntimeError(result.error or "Skill execution failed")
            else:
                entry.status = TaskStatus.COMPLETED

        except asyncio.TimeoutError:
            entry.status = TaskStatus.TIMED_OUT
            entry.error = f"Timed out after {entry.timeout_s}s"
            logger.warning("Task %s TIMED OUT.", task_id)

        except Exception as exc:
            entry.error = str(exc)
            logger.error("Task %s FAILED: %s", task_id, exc)

            if RetryPolicy.should_retry(entry):
                RetryPolicy.prepare_retry(entry)
                self._queue.add(entry)
            else:
                entry.status = TaskStatus.FAILED

        finally:
            entry.completed_at = time.time()
            self._active_tasks.pop(task_id, None)

            for handler in self._on_complete_handlers:
                try:
                    handler(entry)
                except Exception as exc:
                    logger.error("Completion handler error: %s", exc)
