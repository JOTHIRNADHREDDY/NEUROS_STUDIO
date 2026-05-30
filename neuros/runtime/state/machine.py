"""
NEUROS Runtime State Machine

Enforces strict states across the entire middleware.
Every robot must always be in exactly one of these states.
"""

from __future__ import annotations

import logging
from enum import Enum
import time

logger = logging.getLogger("neuros.runtime.state")


class RuntimeState(Enum):
    BOOTING = "booting"
    IDLE = "idle"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    EMERGENCY_STOP = "emergency_stop"
    SHUTDOWN = "shutdown"


class StateMachine:
    """
    Manages the global runtime state of the robot.
    Emits state change events on the Neural Bus.
    """

    def __init__(self) -> None:
        self._state = RuntimeState.BOOTING
        self._bus_publish = None
        self._last_transition = time.time()
        logger.info("StateMachine initialized in state: %s", self._state.value)

    def register_bus(self, publish_fn) -> None:
        self._bus_publish = publish_fn

    @property
    def current_state(self) -> RuntimeState:
        return self._state

    def transition_to(self, new_state: RuntimeState, reason: str = "") -> bool:
        """Attempt to transition to a new state."""
        if self._state == RuntimeState.EMERGENCY_STOP and new_state != RuntimeState.IDLE:
            logger.error("Cannot transition from EMERGENCY_STOP to %s. Must reset to IDLE.", new_state.name)
            return False

        old_state = self._state
        self._state = new_state
        self._last_transition = time.time()

        logger.info("Transitioned %s -> %s (Reason: %s)", old_state.name, new_state.name, reason)

        if self._bus_publish:
            try:
                self._bus_publish(
                    "/robot/system/state",
                    {
                        "old_state": old_state.value,
                        "new_state": new_state.value,
                        "reason": reason,
                        "timestamp": self._last_transition
                    }
                )
            except Exception as e:
                logger.error("Failed to publish state transition: %s", e)

        return True

    def is_operational(self) -> bool:
        """Returns True if the robot can actively accept and execute missions."""
        return self._state in (RuntimeState.IDLE, RuntimeState.ACTIVE)
