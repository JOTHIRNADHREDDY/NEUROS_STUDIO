"""NEUROS V3 — Hardware Contracts.

Defines the mandatory interface that all device plugins must implement.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

class Driver(ABC):
    """Base class for all Neuros hardware drivers.
    
    Any plugin managing a physical or simulated robot must implement
    these core methods to integrate into the Neuros platform.
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish a connection to the hardware device."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Safely sever the connection to the hardware device."""
        pass

    @abstractmethod
    def execute(self, tool_name: str, **kwargs: Any) -> Any:
        """Execute a specific capability/tool on the hardware."""
        pass

    @abstractmethod
    def heartbeat(self) -> bool:
        """Ping the device to ensure it is still responsive.
        
        Returns:
            True if the device is alive, False otherwise.
        """
        pass

    @abstractmethod
    def emergency_stop(self) -> None:
        """Immediately halt all physical motion and disable actuators."""
        pass

    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """Return the list of capabilities supported by this driver.
        
        Example: ["move", "stop", "camera"]
        """
        pass

    @abstractmethod
    def get_health(self) -> Dict[str, Any]:
        """Return a dictionary of health metrics.
        
        Example: {"voltage": 11.5, "temperature": 45.0, "latency": 15}
        """
        pass
