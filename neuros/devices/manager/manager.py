"""NEUROS V3 — Robot Manager (formerly Device Manager).

Central manager for connected robots, providing dashboard views
and tracking registered hardware connections.
"""

from typing import Any, Dict, List
import logging
import threading

logger = logging.getLogger(__name__)

class RobotManager:
    """Manages connected robots and provides dashboard telemetry."""

    def __init__(self) -> None:
        # Maps robot_id to its state dictionary
        self.robots: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def register_robot(self, robot_id: str, robot_type: str) -> None:
        """Register a newly discovered robot."""
        with self._lock:
            if robot_id in self.robots:
                logger.warning("Robot %r already registered", robot_id)
                return
            
            self.robots[robot_id] = {
                "robot_id": robot_id,
                "type": robot_type,
                "status": "online",
                "battery": None,
                "signal": None,
                "latency": None,
                "temperature": None,
                "cpu": None,
                "memory": None
            }
            logger.info("Registered robot %r of type %r", robot_id, robot_type)

    def unregister_robot(self, robot_id: str) -> None:
        """Remove a robot from the manager."""
        with self._lock:
            if robot_id in self.robots:
                del self.robots[robot_id]
                logger.info("Unregistered robot %r", robot_id)

    def update_telemetry(self, robot_id: str, telemetry: Dict[str, Any]) -> None:
        """Update the dashboard telemetry for a robot."""
        with self._lock:
            if robot_id not in self.robots:
                logger.warning("Attempted to update telemetry for unknown robot %r", robot_id)
                return
            
            self.robots[robot_id].update(telemetry)
            logger.debug("Updated telemetry for %r: %s", robot_id, telemetry)

    def get_dashboard(self) -> List[Dict[str, Any]]:
        """Return the current dashboard state for all robots."""
        with self._lock:
            return list(self.robots.values())
