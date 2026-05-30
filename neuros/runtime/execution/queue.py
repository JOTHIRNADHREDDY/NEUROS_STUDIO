"""
NEUROS Execution Queue

Provides priority-based task queuing.
"""

import asyncio
from neuros.runtime.execution.state import TaskEntry, TaskStatus


class ExecutionQueue:
    def __init__(self) -> None:
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._tasks: dict[str, TaskEntry] = {}

    def add(self, entry: TaskEntry) -> None:
        self._tasks[entry.task_id] = entry
        # Priority queue sorts by (priority_value, creation_time, task_id)
        self._queue.put_nowait((entry.priority.value, entry.created_at, entry.task_id))

    async def get(self, timeout: float = 1.0) -> TaskEntry | None:
        """Wait for and return the next task from the queue."""
        try:
            _, _, task_id = await asyncio.wait_for(self._queue.get(), timeout=timeout)
            return self._tasks.get(task_id)
        except asyncio.TimeoutError:
            return None

    def age_tasks(self, amount: int = 1) -> None:
        """Increase the priority of waiting tasks by decreasing their priority value.
        Called periodically to prevent queue starvation of background tasks."""
        if self._queue.empty():
            return

        items = []
        while not self._queue.empty():
            try:
                items.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
                
        for prio, c_time, t_id in items:
            # Ensure background tasks don't overtake HIGH/EMERGENCY tasks (priority < 20)
            new_prio = max(20, prio - amount)
            self._queue.put_nowait((new_prio, c_time, t_id))

    def get_task(self, task_id: str) -> TaskEntry | None:
        return self._tasks.get(task_id)

    def size(self) -> int:
        return self._queue.qsize()

    def all_tasks(self) -> list[TaskEntry]:
        return list(self._tasks.values())
