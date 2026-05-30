import logging
from typing import List

logger = logging.getLogger("neuros.security")

class CommandGuard:
    """
    Sandboxes terminal execution. Prevents destructive commands like 'rm -rf /'
    from being executed by the frontend or AI orchestrator.
    """
    ALLOWED_PREFIXES = ["ros", "catkin", "colcon", "echo", "ls", "pwd", "arduino-cli"]
    BLOCKED_COMMANDS = ["rm", "mv", "chmod", "chown", "reboot", "shutdown"]

    @classmethod
    def is_safe(cls, command: str) -> bool:
        parts = command.strip().split()
        if not parts:
            return False
            
        base_cmd = parts[0]
        if base_cmd in cls.BLOCKED_COMMANDS:
            logger.warning(f"BLOCKED: Attempt to execute forbidden command '{base_cmd}'")
            return False
            
        return True
