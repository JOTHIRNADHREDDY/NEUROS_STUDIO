"""NEUROS V3 — Studio API.

Backend endpoints supporting the Next.js Studio IDE frontend.
Handles the Global Robot Selector, Command Palette executions,
and multi-file AI context forwarding.
"""

from typing import Any, Dict, List
import logging

logger = logging.getLogger(__name__)

class StudioAPI:
    """Provides backend data to the Studio IDE."""

    def __init__(self) -> None:
        self.active_robot: str | None = None

    def get_robot_selector_options(self) -> List[str]:
        """Return the list for the Global Robot Selector."""
        return ["ESP32 Rover", "Simulator", "ROS Workspace", "Jetson"]

    def set_active_robot(self, robot_id: str) -> None:
        """Change the global context for the IDE."""
        self.active_robot = robot_id
        logger.info("Studio active robot set to: %s", robot_id)

    def execute_command_palette(self, command: str) -> str:
        """Handle execution from the Ctrl+K Command Palette."""
        logger.info("Command Palette execution: %s", command)
        if command.startswith("Deploy "):
            return "Triggered deployment..."
        elif command.startswith("Open ROS"):
            return "Opening ROS graph viewer..."
        return "Command executed successfully."

    def build_and_deploy(self) -> str:
        """Trigger the One Click Deploy pipeline."""
        logger.info("Starting One-Click Deploy...")
        return "Build -> Flash -> Verify -> Monitor Pipeline Initiated"
