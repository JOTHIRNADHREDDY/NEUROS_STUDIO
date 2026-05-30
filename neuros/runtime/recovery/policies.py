"""
NEUROS Recovery Policies

Defines how the system responds to different failure scenarios.
"""

from enum import Enum

class RecoveryAction(Enum):
    STOP_ROBOT = "stop_robot"
    SAVE_AND_SHUTDOWN = "save_and_shutdown"
    PAUSE_MISSION = "pause_mission"
    RESUME_MISSION = "resume_mission"
    NOTIFY_OPERATOR = "notify_operator"
    IGNORE = "ignore"

# Example policies as defined in the plan
DEFAULT_POLICIES = {
    "network_loss": RecoveryAction.STOP_ROBOT,
    "power_loss": RecoveryAction.SAVE_AND_SHUTDOWN,
    "llm_disconnect": RecoveryAction.PAUSE_MISSION,
    "crash_recovered": RecoveryAction.PAUSE_MISSION,
}
