"""
NEUROS Execution Manager

High-level API for queuing, tracking, and cancelling skill executions.
Delegates to Queue and Dispatcher.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from neuros.runtime.execution.state import TaskEntry, TaskStatus, TaskPriority
from neuros.runtime.execution.queue import ExecutionQueue
from neuros.runtime.execution.dispatcher import TaskDispatcher

logger = logging.getLogger("neuros.runtime.execution")


class ExecutionManager:
    """
    Manages the execution queue for all skills.

    Usage:
        em = ExecutionManager(skill_engine, safety_validator, sandbox, emergency_stop)
        task_id = await em.submit("navigate_to", {"x": 1.0, "y": 2.0})
        status = em.get_task(task_id)
        await em.cancel(task_id)
    """

    def __init__(
        self,
        skill_engine: Any = None,
        safety_validator: Any = None,
        sandbox: Any = None,
        emergency_stop: Any = None,
        max_concurrent: int = 3,
    ) -> None:
        self._queue = ExecutionQueue()
        self._dispatcher = TaskDispatcher(
            queue=self._queue,
            skill_engine=skill_engine,
            safety_validator=safety_validator,
            sandbox=sandbox,
            emergency_stop=emergency_stop,
            max_concurrent=max_concurrent,
        )

        self._stats = {
            "total_submitted": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_cancelled": 0,
            "total_timed_out": 0,
        }

        self._dispatcher.register_on_complete(self._handle_task_completion)
        logger.info("ExecutionManager initialized (max_concurrent=%d)", max_concurrent)

    # ── Submit ────────────────────────────────────────────────────────────

    async def submit(
        self,
        skill_name: str,
        params: dict[str, Any],
        version: str = "v1",
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout_s: float = 30.0,
        max_retries: int = 2,
        source: str = "user",
    ) -> str:
        """Submit a skill for execution. Returns a task_id."""
        entry = TaskEntry(
            skill_name=skill_name,
            params=params,
            skill_version=version,
            priority=priority,
            timeout_s=timeout_s,
            max_retries=max_retries,
            source=source,
        )

        self._stats["total_submitted"] += 1
        self._queue.add(entry)

        logger.info(
            "Task %s submitted: %s@%s (priority=%s)",
            entry.task_id, skill_name, version, priority.name,
        )

        return entry.task_id

    # ── Cancel ────────────────────────────────────────────────────────────

    async def cancel(self, task_id: str) -> bool:
        """Cancel a queued or running task."""
        entry = self._queue.get_task(task_id)
        if not entry:
            return False

        if entry.status == TaskStatus.RUNNING:
            self._dispatcher.cancel_task(task_id)

        entry.status = TaskStatus.CANCELLED
        self._stats["total_cancelled"] += 1

        logger.info("Task %s cancelled.", task_id)
        return True

    async def cancel_all(self) -> int:
        """Cancel all tasks."""
        count = 0
        for entry in self._queue.all_tasks():
            if entry.status in (TaskStatus.QUEUED, TaskStatus.RUNNING):
                await self.cancel(entry.task_id)
                count += 1
        return count

    # ── Query ─────────────────────────────────────────────────────────────

    def get_task(self, task_id: str) -> TaskEntry | None:
        return self._queue.get_task(task_id)

    def list_tasks(self, status: TaskStatus | None = None) -> list[TaskEntry]:
        tasks = self._queue.all_tasks()
        if status:
            return [t for t in tasks if t.status == status]
        return tasks

    def queue_size(self) -> int:
        return self._queue.size()

    def active_count(self) -> int:
        return self._dispatcher.active_count()

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def start(self) -> None:
        self._dispatcher.start()

    async def stop(self) -> None:
        await self._dispatcher.stop()

    def on_complete(self, handler: Callable[[TaskEntry], None]) -> None:
        self._dispatcher.register_on_complete(handler)

    def _handle_task_completion(self, entry: TaskEntry) -> None:
        if entry.status == TaskStatus.COMPLETED:
            self._stats["total_completed"] += 1
        elif entry.status == TaskStatus.FAILED:
            self._stats["total_failed"] += 1
        elif entry.status == TaskStatus.TIMED_OUT:
            self._stats["total_timed_out"] += 1

    def stats(self) -> dict[str, Any]:
        return {
            **self._stats,
            "queue_size": self.queue_size(),
            "active_tasks": self.active_count(),
            "total_tasks": len(self._queue.all_tasks()),
        }
