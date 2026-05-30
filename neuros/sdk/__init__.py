"""
NEUROS SDK — Developer-Facing Package

`pip install neuros`

The SDK contains ONLY client-facing APIs: Robot class, decorators, CLI, types.
NO execution logic lives here. That's in `runtime/`.
"""

from neuros.sdk.client.robot import Robot
from neuros.sdk.types.common import RobotType

__all__ = ["Robot", "RobotType"]
