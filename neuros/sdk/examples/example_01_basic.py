"""
NEUROS Example 01: Basic Robot Control
=======================================

Demonstrates the simplest NEUROS usage:
- Create a robot
- Start it
- Send movement commands
- Stop it

This works with the simulator (no hardware needed).
"""

from neuros import Robot

# Create a rover robot using the simulator
robot = Robot(name="my_rover", board="simulator", robot_type="rover")
robot.start()

# Check capabilities
print(f"Robot: {robot.name}")
print(f"Capabilities: {robot.status()['capabilities']}")
print(f"Has mobility: {robot.has_capability('mobility')}")
print(f"Has manipulation: {robot.has_capability('manipulation')}")

# Basic movement
robot.move_forward(speed=0.5, duration_s=2.0)
robot.turn(angle_deg=90, speed=0.3)
robot.move_forward(speed=0.3, duration_s=1.0)
robot.stop_moving()

# System check
robot.system_check()

# Stop the robot
robot.stop()

print("Done!")
