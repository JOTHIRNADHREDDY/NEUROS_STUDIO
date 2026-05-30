"""NEUROS Memory Agent — Context storage and retrieval for other agents."""

from __future__ import annotations

import logging
from typing import Any

from neuros.agents.base import BaseAgent, AgentResponse

logger = logging.getLogger("neuros.agents.memory")


class MemoryAgent(BaseAgent):
    """Manages context storage/retrieval. Other agents query this for remembered info."""

    def __init__(self, long_term_memory: Any = None, episodic_memory: Any = None) -> None:
        super().__init__(name="memory", role="Context storage and retrieval")
        self._ltm = long_term_memory
        self._episodic = episodic_memory

    async def process(
        self, message: str, context: dict[str, Any] | None = None
    ) -> AgentResponse:
        context = context or {}
        message_lower = message.lower()

        if any(w in message_lower for w in ["remember", "store", "save"]):
            key = context.get("key", "")
            value = context.get("value", "")
            if self._ltm and key:
                self._ltm.store(key, value)
            return AgentResponse(
                agent_name=self.name,
                intent="store",
                message=f"Stored: {key}",
                confidence=0.9,
            )

        elif any(w in message_lower for w in ["recall", "what", "where", "retrieve"]):
            key = context.get("key", message)
            result = None
            if self._ltm:
                result = self._ltm.recall(key)
                if result is None:
                    results = self._ltm.search(key)
                    result = results[0] if results else None
            return AgentResponse(
                agent_name=self.name,
                intent="recall",
                actions=[{"recalled": result}] if result else [],
                message=f"Recalled: {result}" if result else "No memory found.",
                confidence=0.8 if result else 0.3,
            )

        elif any(w in message_lower for w in ["history", "mission", "episode"]):
            episodes = []
            if self._episodic:
                episodes = self._episodic.recent_episodes(limit=5)
            return AgentResponse(
                agent_name=self.name,
                intent="history",
                actions=[{"episodes": episodes}],
                message=f"Found {len(episodes)} recent episodes.",
                confidence=0.85,
            )

        return AgentResponse(
            agent_name=self.name,
            intent="unknown_memory",
            message="Could not determine memory operation.",
            confidence=0.2,
        )
