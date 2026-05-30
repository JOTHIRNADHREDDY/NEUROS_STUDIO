"""NEUROS V3 — Capability Registry.

Centralized registry for tracking what each connected robot is capable of doing.
"""

from typing import List, Dict
from pydantic import BaseModel
import logging
import threading

logger = logging.getLogger(__name__)

class RobotCapabilities(BaseModel):
    """Schema representing a robot and its available capabilities."""
    robot_id: str
    capabilities: List[str]

class CapabilityRegistry:
    """Thread-safe registry mapping robots to their supported capabilities."""

    def __init__(self) -> None:
        self._registry: Dict[str, RobotCapabilities] = {}
        self._lock = threading.RLock()

    def register(self, robot_id: str, capabilities: List[str]) -> None:
        """Register or update a robot's capabilities."""
        with self._lock:
            self._registry[robot_id] = RobotCapabilities(
                robot_id=robot_id,
                capabilities=capabilities
            )
            logger.info("Registered capabilities for %r: %s", robot_id, capabilities)

    def unregister(self, robot_id: str) -> None:
        """Remove a robot's capabilities from the registry."""
        with self._lock:
            if robot_id in self._registry:
                del self._registry[robot_id]
                logger.info("Unregistered capabilities for %r", robot_id)

    def get_capabilities(self, robot_id: str) -> List[str]:
        """Retrieve the list of capabilities for a given robot."""
        with self._lock:
            cap_record = self._registry.get(robot_id)
            return cap_record.capabilities if cap_record else []

    def has_capability(self, robot_id: str, capability: str) -> bool:
        """Check if a specific robot has a specific capability."""
        return capability in self.get_capabilities(robot_id)

    def get_all_robots(self) -> List[str]:
        """Return a list of all robots that have reported capabilities."""
        with self._lock:
            return list(self._registry.keys())

    def get_robots_with_capability(self, capability: str) -> List[str]:
        """Find all robots that support a specific capability."""
        with self._lock:
            return [
                rob_id for rob_id, caps in self._registry.items()
                if capability in caps.capabilities
            ]
