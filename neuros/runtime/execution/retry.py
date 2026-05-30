"""
NEUROS Retry Logic

Handles exponential backoff and retry evaluation.
"""

from neuros.runtime.execution.state import TaskEntry, TaskStatus
import logging

logger = logging.getLogger("neuros.runtime.execution.retry")

class RetryPolicy:
    """Evaluates if a task should be retried."""

    @staticmethod
    def should_retry(entry: TaskEntry) -> bool:
        """Determines if the task should be retried."""
        return entry.retries < entry.max_retries

    @staticmethod
    def prepare_retry(entry: TaskEntry) -> None:
        """Updates task state for retry."""
        entry.retries += 1
        entry.status = TaskStatus.RETRYING
        logger.warning(
            "Task %s marked for retry (%d/%d)",
            entry.task_id, entry.retries, entry.max_retries,
        )
