"""
NEUROS Short-Term Memory

In-memory, volatile store for the current task context.
Gets cleared after each mission/conversation.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any

logger = logging.getLogger("neuros.memory.short_term")


class ShortTermMemory:
    """
    Fast, in-memory context for the current task.

    Usage:
        stm = ShortTermMemory(max_entries=100)
        stm.add("user_goal", "Find the red bottle")
        stm.add("current_skill", "navigate_to")
        goal = stm.get("user_goal")
        stm.clear()
    """

    def __init__(self, max_entries: int = 200) -> None:
        self._store: dict[str, Any] = {}
        self._history: deque[dict[str, Any]] = deque(maxlen=max_entries)
        self._max_entries = max_entries
        logger.info("ShortTermMemory initialized (max=%d)", max_entries)

    def add(self, key: str, value: Any) -> None:
        """Store a key-value pair."""
        self._store[key] = value
        self._history.append({
            "action": "add",
            "key": key,
            "timestamp": time.time(),
        })

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value by key."""
        return self._store.get(key, default)

    def remove(self, key: str) -> None:
        """Remove a key."""
        self._store.pop(key, None)

    def has(self, key: str) -> bool:
        return key in self._store

    def get_all(self) -> dict[str, Any]:
        """Return all current context."""
        return dict(self._store)

    def get_context_summary(self) -> str:
        """Return a formatted summary for agent context injection."""
        lines = []
        for k, v in self._store.items():
            lines.append(f"- {k}: {v}")
        return "\n".join(lines) if lines else "(empty context)"

    def clear(self) -> None:
        """Clear all short-term memory."""
        self._store.clear()
        logger.info("ShortTermMemory cleared.")

    def size(self) -> int:
        return len(self._store)
