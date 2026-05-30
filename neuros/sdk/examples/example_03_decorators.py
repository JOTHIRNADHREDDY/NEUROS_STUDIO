"""
NEUROS Example 03: Event Decorators
=====================================

Demonstrates how to use SDK decorators to respond to events
and run periodic tasks.
"""

import time
from neuros import Robot
from neuros.sdk.decorators import on_event, every, on_start, on_shutdown

robot = Robot(name="event_rover", board="simulator", robot_type="rover")

@on_start
def my_startup_hook():
    print("Robot started! Initializing custom payload...")

@on_event("/robot/sensor/battery")
def handle_battery(msg):
    voltage = msg.get("voltage", 0.0)
    print(f"[EVENT] Battery voltage: {voltage}V")
    if voltage < 10.5:
        robot.stop_moving()
        print("Battery critical! Stopping.")

@every(hz=1.0)
def health_ping():
    print("[PERIODIC] Health ping OK.")

@on_shutdown
def cleanup_hook():
    print("Robot stopping. Cleaning up resources...")

if __name__ == "__main__":
    robot.start()
    
    # Simulate runtime for a few seconds
    print("Running for 3 seconds...")
    time.sleep(3)
    
    robot.stop()
