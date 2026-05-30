"""
NEUROS Runtime Lifecycle — State Machine

Every robot goes through these states:
BOOTING -> IDLE -> ACTIVE -> PAUSED -> IDLE
                            -> ERROR -> IDLE (after recovery)
                            -> EMERGENCY_STOP -> IDLE (after release)
Any state -> SHUTDOWN
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger("neuros.runtime.lifecycle")


class RobotState(Enum):
    BOOTING = "booting"
    IDLE = "idle"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    EMERGENCY_STOP = "emergency_stop"
    SHUTDOWN = "shutdown"


# Valid state transitions
_TRANSITIONS: dict[RobotState, set[RobotState]] = {
    RobotState.BOOTING: {RobotState.IDLE, RobotState.ERROR, RobotState.SHUTDOWN},
    RobotState.IDLE: {RobotState.ACTIVE, RobotState.SHUTDOWN, RobotState.ERROR, RobotState.EMERGENCY_STOP},
    RobotState.ACTIVE: {RobotState.IDLE, RobotState.PAUSED, RobotState.ERROR, RobotState.EMERGENCY_STOP, RobotState.SHUTDOWN},
    RobotState.PAUSED: {RobotState.ACTIVE, RobotState.IDLE, RobotState.ERROR, RobotState.EMERGENCY_STOP, RobotState.SHUTDOWN},
    RobotState.ERROR: {RobotState.IDLE, RobotState.SHUTDOWN, RobotState.EMERGENCY_STOP},
    RobotState.EMERGENCY_STOP: {RobotState.IDLE, RobotState.SHUTDOWN},
    RobotState.SHUTDOWN: set(),  # terminal state
}


@dataclass
class StateTransition:
    """Record of a state change."""
    from_state: RobotState
    to_state: RobotState
    timestamp: float
    reason: str


class LifecycleManager:
    """
    Manages the robot's lifecycle state machine.

    Usage:
        lm = LifecycleManager()
        lm.on_transition(my_handler)
        lm.transition_to(RobotState.IDLE, reason="Boot complete")
        lm.transition_to(RobotState.ACTIVE, reason="Mission started")
    """

    def __init__(self) -> None:
        self._state = RobotState.BOOTING
        self._history: list[StateTransition] = []
        self._handlers: list[Callable[[StateTransition], None]] = []
        self._state_enter_time = time.time()
        logger.info("LifecycleManager initialized. State: BOOTING")

    @property
    def state(self) -> RobotState:
        return self._state

    @property
    def state_duration_s(self) -> float:
        return time.time() - self._state_enter_time

    @property
    def history(self) -> list[StateTransition]:
        return list(self._history)

    def on_transition(self, handler: Callable[[StateTransition], None]) -> None:
        """Register a callback for state transitions."""
        self._handlers.append(handler)

    def can_transition_to(self, target: RobotState) -> bool:
        """Check if a transition to the target state is valid."""
        return target in _TRANSITIONS.get(self._state, set())

    def transition_to(self, target: RobotState, reason: str = "") -> bool:
        """
        Transition to a new state.
        Returns True if successful, False if the transition is invalid.
        """
        if not self.can_transition_to(target):
            logger.warning(
                "Invalid transition: %s -> %s (reason: %s)",
                self._state.value, target.value, reason,
            )
            return False

        transition = StateTransition(
            from_state=self._state,
            to_state=target,
            timestamp=time.time(),
            reason=reason,
        )

        old_state = self._state
        self._state = target
        self._state_enter_time = time.time()
        self._history.append(transition)

        logger.info(
            "State transition: %s -> %s (%s)",
            old_state.value, target.value, reason,
        )

        for handler in self._handlers:
            try:
                handler(transition)
            except Exception as exc:
                logger.error("Transition handler error: %s", exc)

        return True

    def force_state(self, target: RobotState, reason: str = "forced") -> None:
        """Force a state change, bypassing validation. Use with caution."""
        transition = StateTransition(
            from_state=self._state,
            to_state=target,
            timestamp=time.time(),
            reason=f"FORCED: {reason}",
        )
        self._state = target
        self._state_enter_time = time.time()
        self._history.append(transition)
        logger.warning("FORCED state: %s (%s)", target.value, reason)

    def status(self) -> dict[str, Any]:
        return {
            "state": self._state.value,
            "duration_s": round(self.state_duration_s, 1),
            "transitions": len(self._history),
            "valid_next_states": [s.value for s in _TRANSITIONS.get(self._state, set())],
        }
