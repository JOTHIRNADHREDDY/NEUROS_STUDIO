"""NEUROS V3 — Tool Registry.

Centralized tool management. Maintains a registry of executable tools
that the Orchestrator can use.
"""

from typing import Any, Callable, Dict, List
import logging
import threading

logger = logging.getLogger(__name__)

class ToolRegistry:
    """Thread-safe registry for AI-executable tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, Callable[..., Any]] = {}
        self._lock = threading.RLock()

    def register_tool(self, name: str, func: Callable[..., Any]) -> None:
        """Register a new executable tool."""
        with self._lock:
            if name in self._tools:
                logger.warning("Tool %r already registered, overwriting", name)
            self._tools[name] = func
            logger.info("Registered tool %r", name)

    def remove_tool(self, name: str) -> None:
        """Remove a tool from the registry."""
        with self._lock:
            if name in self._tools:
                del self._tools[name]
                logger.info("Removed tool %r", name)

    def execute_tool(self, name: str, **kwargs: Any) -> Any:
        """Execute a tool by name with the given arguments."""
        with self._lock:
            if name not in self._tools:
                raise KeyError(f"Tool {name!r} not found in registry")
            func = self._tools[name]
        
        logger.debug("Executing tool %r with args %s", name, kwargs)
        return func(**kwargs)

    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        with self._lock:
            return list(self._tools.keys())
