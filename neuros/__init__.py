"""
NEUROS — AI Middleware for Robotics
===================================

The easiest way to build AI-powered robots.

    from neuros import Robot

    robot = Robot(name="rover", board="simulator")
    robot.start()
    robot.move_forward(speed=0.5)
    robot.navigate_to("kitchen")
    robot.stop()

NEUROS sits above Linux/ROS2/Zephyr and provides:
- AI Orchestration
- Robot Abstraction
- Unified APIs
- Skill Execution
- Safety Validation
- Great Developer Experience

Architecture:
    User -> Studio -> LLM -> Planner Agent -> Skill Engine
    -> Execution Manager -> Safety Layer -> HAL
    -> ROS2 / ESP32 / Arduino / Pi / Jetson
"""

__version__ = "2.0.0-alpha"
__author__ = "NEUROS Team"

from neuros.sdk.client.robot import Robot
from neuros.sdk.types.common import RobotType

__all__ = [
    "Robot",
    "RobotType",
    "__version__",
]
