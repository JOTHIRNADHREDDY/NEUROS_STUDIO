"""
example_01_blinker.py
=====================
NEUROS OS — Example 1: LED Blinker (Beginner Mode)

The absolute minimum NEUROS program.
Works on simulator (no hardware needed).
Works on real Arduino with LED on pin 13.

Run:
    python examples/example_01_blinker.py

To run on real Arduino:
    python examples/example_01_blinker.py --board arduino --port /dev/ttyUSB0
"""

import sys
import argparse

# ── Parse args ──────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="NEUROS Example 1 — LED Blinker")
parser.add_argument("--board", default="simulator", help="Board type: simulator | arduino")
parser.add_argument("--port",  default="/dev/ttyUSB0", help="Serial port for Arduino")
args = parser.parse_args()

# ── NEUROS imports ──────────────────────────────────────────────────────────
from neuros import Robot, spin

# ── Create robot ─────────────────────────────────────────────────────────────
robot = Robot(
    name  = "blinker",
    board = args.board,
    port  = args.port,
)
robot.start()

# ── Configure LED pin ─────────────────────────────────────────────────────────
robot.pin("LED", pin=13, mode="output")

# ── Define behaviour — runs at 1 Hz (every second) ───────────────────────────
@robot.every(hz=1, name="blink_led")
def blink():
    robot.toggle("LED")
    print(f"  ● LED toggled | robot_uptime={robot._kernel.uptime_s:.1f}s")

# ── Subscribe to see all bus messages (optional) ─────────────────────────────
def on_msg(msg):
    pass   # comment out to silence

robot.subscribe("#", on_msg)

# ── Run forever (Ctrl+C to stop) ─────────────────────────────────────────────
print("""
╔══════════════════════════════════════════╗
║  NEUROS OS — Example 1: LED Blinker      ║
║  Board : """ + args.board + """
║  Press Ctrl+C to stop                   ║
╚══════════════════════════════════════════╝
""")

spin(robot)
