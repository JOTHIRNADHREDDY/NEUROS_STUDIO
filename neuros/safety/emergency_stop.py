"""
NEUROS Emergency Stop

Highest-priority safety system. Bypasses ALL layers:
- Agents
- Planner
- Execution Manager
- Queue
- Skill Engine

Directly commands HAL to stop all actuators.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger("neuros.safety.emergency_stop")


class EStopState(Enum):
    """Emergency stop system state."""
    ARMED = "armed"
    TRIGGERED = "triggered"
    RELEASED = "released"
    DISABLED = "disabled"


@dataclass
class EStopEvent:
    """Record of an emergency stop event."""
    timestamp: float
    reason: str
    source: str
    state: EStopState


class EmergencyStop:
    """
    Emergency stop controller.

    When triggered, this immediately:
    1. Sets all motors to zero
    2. Disengages all actuators
    3. Publishes an E-Stop event on the bus
    4. Blocks all further commands until released

    Usage:
        estop = EmergencyStop()
        estop.register_stop_handler(my_hal.stop_all)
        estop.trigger("obstacle detected", source="lidar_node")
    """

    def __init__(self) -> None:
        self._state = EStopState.ARMED
        self._stop_handlers: list[Callable[[], None]] = []
        self._bus_publish: Callable[[str, dict], None] | None = None
        self._history: list[EStopEvent] = []
        self._blocked_commands: int = 0
        logger.info("EmergencyStop system initialized and ARMED.")

    @property
    def state(self) -> EStopState:
        return self._state

    @property
    def is_triggered(self) -> bool:
        return self._state == EStopState.TRIGGERED

    @property
    def is_armed(self) -> bool:
        return self._state == EStopState.ARMED

    @property
    def history(self) -> list[EStopEvent]:
        return list(self._history)

    @property
    def blocked_commands_count(self) -> int:
        return self._blocked_commands

    def register_hal(self, hal: Any) -> None:
        """Register the HAL instance to call when E-Stop triggers."""
        # Using Any to avoid circular import, but expects BaseHAL
        self._stop_handlers.append(lambda: __import__('asyncio').create_task(hal.emergency_stop()) if __import__('asyncio').iscoroutinefunction(hal.emergency_stop) else hal.emergency_stop())
        logger.debug("Registered E-Stop HAL handler")

    def register_bus(self, publish_fn: Callable[[str, dict], None]) -> None:
        """Register the bus publish function for broadcasting E-Stop events."""
        self._bus_publish = publish_fn

    def trigger(self, reason: str, source: str = "unknown") -> None:
        """
        TRIGGER EMERGENCY STOP.

        This is the most critical function in NEUROS.
        It bypasses every layer and directly stops all hardware.
        """
        if self._state == EStopState.TRIGGERED:
            logger.warning("E-Stop already triggered. Ignoring duplicate.")
            return

        self._state = EStopState.TRIGGERED
        event = EStopEvent(
            timestamp=time.time(),
            reason=reason,
            source=source,
            state=EStopState.TRIGGERED,
        )
        self._history.append(event)

        logger.critical(
            "🚨 EMERGENCY STOP TRIGGERED — Reason: %s, Source: %s", reason, source
        )

        # Execute ALL stop handlers immediately
        for handler in self._stop_handlers:
            try:
                handler()
            except Exception as exc:
                logger.error(
                    "E-Stop handler '%s' failed: %s", handler.__name__, exc
                )

        # Broadcast on bus
        if self._bus_publish:
            try:
                self._bus_publish(
                    "/robot/safety/emergency_stop",
                    {
                        "triggered": True,
                        "reason": reason,
                        "source": source,
                        "timestamp": event.timestamp,
                    },
                )
            except Exception as exc:
                logger.error("Failed to publish E-Stop event: %s", exc)

    def release(self, authorized_by: str = "operator") -> bool:
        """
        Release the emergency stop. Only possible when triggered.
        Requires explicit authorization.
        """
        if self._state != EStopState.TRIGGERED:
            logger.warning("Cannot release E-Stop — current state: %s", self._state)
            return False

        self._state = EStopState.ARMED
        event = EStopEvent(
            timestamp=time.time(),
            reason=f"Released by {authorized_by}",
            source=authorized_by,
            state=EStopState.ARMED,
        )
        self._history.append(event)

        logger.info("E-Stop RELEASED by %s. System re-armed.", authorized_by)

        if self._bus_publish:
            try:
                self._bus_publish(
                    "/robot/safety/emergency_stop",
                    {
                        "triggered": False,
                        "released_by": authorized_by,
                        "timestamp": event.timestamp,
                    },
                )
            except Exception:
                pass

        return True

    def check_allowed(self) -> bool:
        """
        Check if commands are allowed to proceed.
        Call this before any command execution.
        Returns False if E-Stop is active (blocking all commands).
        """
        if self._state == EStopState.TRIGGERED:
            self._blocked_commands += 1
            return False
        return True

    def status(self) -> dict[str, Any]:
        """Get full E-Stop system status."""
        return {
            "state": self._state.value,
            "is_triggered": self.is_triggered,
            "is_armed": self.is_armed,
            "blocked_commands": self._blocked_commands,
            "total_triggers": sum(
                1 for e in self._history if e.state == EStopState.TRIGGERED
            ),
            "handlers_registered": len(self._stop_handlers),
        }
