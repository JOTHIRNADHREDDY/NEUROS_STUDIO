"""
NEUROS Async HAL Adapter

Wraps the physical Hardware Abstraction Layer (HAL) with timeout protection
to prevent hardware-level stalls from blocking the orchestrator or background tasks.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger("neuros.runtime.adapters.async_hal")

class AsyncHALAdapter:
    """
    Wraps an underlying HAL instance. Automatically applies an asyncio.wait_for
    timeout to all asynchronous method calls to prevent the runtime from hanging.
    """
    def __init__(self, hal: Any, default_timeout: float = 0.2):
        self._hal = hal
        self._default_timeout = default_timeout

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._hal, name)
        
        # If the attribute is a coroutine function, wrap it
        if asyncio.iscoroutinefunction(attr):
            async def wrapper(*args, **kwargs):
                try:
                    return await asyncio.wait_for(
                        attr(*args, **kwargs),
                        timeout=self._default_timeout
                    )
                except asyncio.TimeoutError:
                    logger.error(f"HAL operation '{name}' timed out after {self._default_timeout}s")
                    raise RuntimeError(f"HAL operation '{name}' timed out.")
            return wrapper
        
        # Otherwise just return the attribute directly
        return attr

    async def get_state(self) -> dict:
        """Explicitly wrapped common method for IDE autocomplete support."""
        try:
            return await asyncio.wait_for(
                self._hal.get_state(),
                timeout=self._default_timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"HAL operation 'get_state' timed out after {self._default_timeout}s")
            raise RuntimeError("HAL operation 'get_state' timed out.")
