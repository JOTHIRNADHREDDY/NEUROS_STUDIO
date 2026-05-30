"""NEUROS SDK Common Types."""

from __future__ import annotations

from enum import Enum


class RobotType(Enum):
    ROVER = "rover"
    ARM = "arm"
    DRONE = "drone"
    HUMANOID = "humanoid"
    CUSTOM = "custom"
