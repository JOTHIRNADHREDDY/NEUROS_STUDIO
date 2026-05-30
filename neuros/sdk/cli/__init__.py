"""
NEUROS CLI

Usage:
    neuros init my-robot
    neuros doctor
    neuros status
    neuros monitor
    neuros version
    neuros run
"""

from __future__ import annotations

import argparse
import sys
import json
import logging


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="neuros",
        description="NEUROS — AI Middleware for Robotics",
    )
    subparsers = parser.add_subparsers(dest="command")

    # neuros version
    subparsers.add_parser("version", help="Show NEUROS version")

    # neuros doctor
    subparsers.add_parser("doctor", help="Check system health")

    # neuros init
    init_parser = subparsers.add_parser("init", help="Create a new robot project")
    init_parser.add_argument("name", help="Project name")
    init_parser.add_argument("--type", default="rover", choices=["rover", "arm", "drone", "humanoid"])

    # neuros status
    subparsers.add_parser("status", help="Show runtime status")

    # neuros monitor
    subparsers.add_parser("monitor", help="Display live hardware telemetry and mission status")

    args = parser.parse_args()

    if args.command == "version":
        from neuros import __version__
        print(f"NEUROS v{__version__}")

    elif args.command == "doctor":
        _run_doctor()

    elif args.command == "init":
        _init_project(args.name, args.type)

    elif args.command == "status":
        print("NEUROS Runtime: not running")
        print("Use 'neuros run' to start the runtime daemon.")

    elif args.command == "monitor":
        _run_monitor()

    else:
        parser.print_help()


def _run_doctor() -> None:
    """Check system health and dependencies."""
    import platform
    print("NEUROS Doctor")
    print("=" * 40)
    print(f"Platform:      {platform.system()} {platform.machine()}")
    print(f"Python:        {platform.python_version()}")

    checks = {
        "pyserial": "Serial (Arduino/ESP32)",
        "fastapi": "Runtime Server",
        "pyyaml": "Config System",
        "openai": "AI Integration",
    }

    for pkg, label in checks.items():
        try:
            __import__(pkg)
            print(f"  ✅ {label} ({pkg})")
        except ImportError:
            print(f"  ❌ {label} ({pkg}) — pip install {pkg}")

    print()
    print("Run 'pip install neuros[all]' for full functionality.")


def _init_project(name: str, robot_type: str) -> None:
    """Create a new robot project."""
    import os

    os.makedirs(name, exist_ok=True)

    # Create robot.py
    robot_code = f'''"""NEUROS Robot: {name}"""
from neuros import Robot

robot = Robot(name="{name}", board="simulator", robot_type="{robot_type}")
robot.start()

# High-level commands
robot.move_forward(speed=0.5, duration_s=2.0)
robot.system_check()
robot.stop()

print("Robot '{name}' finished.")
'''
    with open(os.path.join(name, "robot.py"), "w") as f:
        f.write(robot_code)

    # Create config
    os.makedirs(os.path.join(name, "config"), exist_ok=True)
    config = f"""robot:
  id: "{name}"
  name: "{name}"
  type: "{robot_type}"

hardware:
  board: "simulator"
"""
    with open(os.path.join(name, "config", "robot.yaml"), "w") as f:
        f.write(config)

    print(f"✅ Created NEUROS project: {name}/")
    print(f"   Type: {robot_type}")
    print(f"   Run:  cd {name} && python robot.py")


def _run_monitor() -> None:
    """Display real-time telemetry from the robot (mocked for MVP)."""
    import time
    
    print("NEUROS Telemetry Monitor")
    print("Press Ctrl+C to exit")
    print("-" * 30)
    
    try:
        while True:
            # Clear terminal lines (simple approach)
            print("\r\033[K", end="")
            
            # Mock telemetry
            print(f"Battery: 12.1V")
            print(f"CPU: 14%")
            print(f"Temperature: 42C")
            print(f"Mission: Navigate")
            print(f"Status: Active")
            
            time.sleep(1.0)
            
            # Move cursor up 5 lines for next iteration
            sys.stdout.write("\033[5A")
            sys.stdout.flush()
    except KeyboardInterrupt:
        sys.stdout.write("\033[5B") # Move cursor down past the output
        print("\nMonitor stopped.")


if __name__ == "__main__":
    main()
