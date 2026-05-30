"""NEUROS V3 — Mock ESP32 Driver.

Simulates an ESP32 rover for end-to-end CI Testing.
Complies with the strict Driver interface from neuros.drivers.base.
"""

from neuros.drivers.base import Driver
import logging
import time

logger = logging.getLogger(__name__)

class MockESP32(Driver):
    """Mock driver simulating an ESP32 robot."""

    def __init__(self, robot_id: str) -> None:
        self.robot_id = robot_id
        self._connected = False
        self._moving = False

    def connect(self) -> bool:
        logger.info("MockESP32 [%s]: Connecting...", self.robot_id)
        self._connected = True
        return True

    def disconnect(self) -> None:
        logger.info("MockESP32 [%s]: Disconnecting...", self.robot_id)
        self._connected = False
        self._moving = False

    def is_connected(self) -> bool:
        return self._connected

    def heartbeat(self) -> bool:
        """Respond to ping from HeartbeatMonitor."""
        return self._connected

    def emergency_stop(self) -> None:
        """Dead man switch triggered."""
        logger.warning("MockESP32 [%s]: EMERGENCY STOP ACTIVATED!", self.robot_id)
        self._moving = False

    def execute(self, command: str, **kwargs) -> dict:
        """Execute mock commands."""
        if not self._connected:
            raise RuntimeError(f"MockESP32 [{self.robot_id}] not connected.")

        if command == "move":
            self._moving = True
            logger.info("MockESP32 [%s]: Moving %r", self.robot_id, kwargs)
            # Simulate slight delay
            time.sleep(0.1)
            self._moving = False
            return {"status": "success", "action": "move", "params": kwargs}
            
        elif command == "stop":
            self._moving = False
            logger.info("MockESP32 [%s]: Stopped", self.robot_id)
            return {"status": "success", "action": "stop"}

        return {"status": "error", "message": f"Unknown command {command}"}

    def get_health(self) -> dict:
        return {
            "battery": 85.0,
            "status": "online" if self._connected else "offline"
        }

    def get_capabilities(self) -> list:
        return ["move", "stop"]
        
    def get_telemetry(self) -> dict:
        return {
            "battery": 85.0,
            "moving": self._moving,
            "latency": 5.0
        }
