import logging
from typing import Dict, Any

logger = logging.getLogger("neuros.state")

class GlobalState:
    """
    Live state engine holding global status for synchronizing frontend and backend.
    """
    def __init__(self):
        self.ros_state: Dict[str, Any] = {
            "active_nodes": 0,
            "core_running": False
        }
        self.ide_state: Dict[str, Any] = {
            "is_compiling": False,
            "last_build": None
        }
        self.device_state: Dict[str, Any] = {
            "connected_devices": []
        }
    
    def update_ros(self, key: str, value: Any):
        self.ros_state[key] = value
        
    def update_ide(self, key: str, value: Any):
        self.ide_state[key] = value

    def get_full_state(self) -> Dict[str, Any]:
        return {
            "ros": self.ros_state,
            "ide": self.ide_state,
            "devices": self.device_state
        }
