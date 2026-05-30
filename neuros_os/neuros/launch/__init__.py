"""
neuros.launch
=============
Phase 2 — Simple Launch System.

Replace 80-line ROS2 launch files with 5-line NEUROS config.
Auto-generates the ROS2 launch file underneath. Backwards compatible.

Usage
-----
    # YAML config (neuros_launch.yaml):
    robot:
      name: patrol_bot
      board: simulator
      nodes:
        - type: LiDARNode
          name: lidar
          config:
            mode: simulate
            scan_hz: 10
        - type: MotorNode
          name: motor_l
          config:
            pin_en: 12
            pin_in1: 23
            pin_in2: 24
        - type: OdometryNode
          name: odom
          config:
            wheel_base_m: 0.15
      ros2_bridge:
        topics:
          - topic: /scan
            direction: ros2→neuros
          - topic: /cmd_vel
            direction: neuros→ros2

    # Python API:
    from neuros.launch import LaunchConfig, LaunchRunner
    config = LaunchConfig.from_yaml("neuros_launch.yaml")
    runner = LaunchRunner(config)
    runner.start()
    runner.wait()

    # CLI:
    neuros launch neuros_launch.yaml
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from neuros.api.robot import Robot

logger = logging.getLogger("neuros.launch")


# ── Node Specification ────────────────────────────────────────────────────

@dataclass
class NodeSpec:
    """Specification for a single node in a launch config."""
    type: str
    name: str
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: str = "NORMAL"  # LOW, NORMAL, HIGH, CRITICAL
    hz: Optional[int] = None
    group: str = "default"

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "name": self.name,
            "config": self.config,
            "enabled": self.enabled,
            "priority": self.priority,
            "hz": self.hz,
            "group": self.group,
        }


@dataclass
class BridgeTopicSpec:
    """Specification for a bridged ROS2 topic."""
    topic: str
    direction: str = "ros2→neuros"
    neuros_topic: str = ""
    msg_type: str = "std_msgs/String"


@dataclass
class LaunchConfig:
    """
    Complete launch configuration for a NEUROS robot.

    Can be loaded from YAML, dict, or constructed programmatically.
    """
    name: str = "robot"
    board: str = "simulator"
    nodes: List[NodeSpec] = field(default_factory=list)
    ros2_topics: List[BridgeTopicSpec] = field(default_factory=list)
    monitor: bool = False
    monitor_hz: int = 4
    monitor_port: int = 8765
    fleet_enabled: bool = False
    fleet_name: str = ""
    log_level: str = "INFO"
    rt_enabled: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LaunchConfig":
        """Create a LaunchConfig from a dictionary."""
        robot = data.get("robot", data)

        nodes = []
        for n in robot.get("nodes", []):
            nodes.append(NodeSpec(
                type=n["type"],
                name=n.get("name", n["type"].lower()),
                config=n.get("config", {}),
                enabled=n.get("enabled", True),
                priority=n.get("priority", "NORMAL"),
                hz=n.get("hz"),
                group=n.get("group", "default"),
            ))

        ros2_topics = []
        bridge = robot.get("ros2_bridge", {})
        for t in bridge.get("topics", []):
            ros2_topics.append(BridgeTopicSpec(
                topic=t["topic"],
                direction=t.get("direction", "ros2→neuros"),
                neuros_topic=t.get("neuros_topic", ""),
                msg_type=t.get("msg_type", "std_msgs/String"),
            ))

        return cls(
            name=robot.get("name", "robot"),
            board=robot.get("board", "simulator"),
            nodes=nodes,
            ros2_topics=ros2_topics,
            monitor=robot.get("monitor", False),
            monitor_hz=robot.get("monitor_hz", 4),
            monitor_port=robot.get("monitor_port", 8765),
            fleet_enabled=robot.get("fleet", {}).get("enabled", False),
            fleet_name=robot.get("fleet", {}).get("name", ""),
            log_level=robot.get("log_level", "INFO"),
            rt_enabled=robot.get("rt_enabled", False),
        )

    @classmethod
    def from_yaml(cls, path: str) -> "LaunchConfig":
        """Load config from a YAML file."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Launch config not found: {path}")

        text = p.read_text(encoding="utf-8")

        # Minimal YAML parser (no pyyaml dependency)
        data = _parse_yaml(text)
        return cls.from_dict(data)

    @classmethod
    def from_json(cls, path: str) -> "LaunchConfig":
        """Load config from a JSON file."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Launch config not found: {path}")
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def to_dict(self) -> dict:
        return {
            "robot": {
                "name": self.name,
                "board": self.board,
                "nodes": [n.to_dict() for n in self.nodes],
                "ros2_bridge": {
                    "topics": [
                        {"topic": t.topic, "direction": t.direction,
                         "neuros_topic": t.neuros_topic, "msg_type": t.msg_type}
                        for t in self.ros2_topics
                    ]
                },
                "monitor": self.monitor,
                "monitor_hz": self.monitor_hz,
                "monitor_port": self.monitor_port,
                "fleet": {"enabled": self.fleet_enabled, "name": self.fleet_name},
                "log_level": self.log_level,
                "rt_enabled": self.rt_enabled,
            }
        }

    def add_node(self, node_type: str, name: str, **config) -> "LaunchConfig":
        """Fluent API: add a node spec."""
        self.nodes.append(NodeSpec(type=node_type, name=name, config=config))
        return self

    def add_ros2_topic(self, topic: str, direction: str = "ros2→neuros",
                       **kwargs) -> "LaunchConfig":
        """Fluent API: add a ROS2 bridge topic."""
        self.ros2_topics.append(BridgeTopicSpec(topic=topic, direction=direction, **kwargs))
        return self


# ── Node Registry ─────────────────────────────────────────────────────────

# Maps type name strings to the actual classes. Lazy-loaded.
_NODE_REGISTRY: Dict[str, type] = {}


def _ensure_registry():
    """Populate the node registry from known NEUROS node modules."""
    global _NODE_REGISTRY
    if _NODE_REGISTRY:
        return

    # Import all known node classes
    _registry_map = {}

    try:
        from neuros.nodes.sensor.gpio import GPIOSensorNode
        _registry_map["GPIOSensorNode"] = GPIOSensorNode
    except ImportError:
        pass
    try:
        from neuros.nodes.sensor.imu import IMUNode
        _registry_map["IMUNode"] = IMUNode
    except ImportError:
        pass
    try:
        from neuros.nodes.sensor.ultrasonic import UltrasonicNode
        _registry_map["UltrasonicNode"] = UltrasonicNode
    except ImportError:
        pass
    try:
        from neuros.nodes.sensor.line_follower import LineFollowerNode
        _registry_map["LineFollowerNode"] = LineFollowerNode
    except ImportError:
        pass
    try:
        from neuros.nodes.sensor.temperature import TemperatureNode
        _registry_map["TemperatureNode"] = TemperatureNode
    except ImportError:
        pass
    try:
        from neuros.nodes.sensor.encoder import EncoderNode
        _registry_map["EncoderNode"] = EncoderNode
    except ImportError:
        pass
    try:
        from neuros.nodes.sensor.battery import BatteryMonitorNode
        _registry_map["BatteryMonitorNode"] = BatteryMonitorNode
    except ImportError:
        pass
    try:
        from neuros.nodes.actuator.motor import MotorNode
        _registry_map["MotorNode"] = MotorNode
    except ImportError:
        pass
    try:
        from neuros.nodes.actuator.servo import ServoNode
        _registry_map["ServoNode"] = ServoNode
    except ImportError:
        pass
    try:
        from neuros.nodes.actuator.led import LEDNode
        _registry_map["LEDNode"] = LEDNode
    except ImportError:
        pass
    try:
        from neuros.nodes.actuator.buzzer import BuzzerNode
        _registry_map["BuzzerNode"] = BuzzerNode
    except ImportError:
        pass
    try:
        from neuros.nodes.vision.camera import CameraNode
        _registry_map["CameraNode"] = CameraNode
    except ImportError:
        pass
    try:
        from neuros.nodes.vision.lidar import LiDARNode
        _registry_map["LiDARNode"] = LiDARNode
    except ImportError:
        pass
    try:
        from neuros.nodes.navigation.odometry import OdometryNode
        _registry_map["OdometryNode"] = OdometryNode
    except ImportError:
        pass
    try:
        from neuros.nodes.navigation.obstacle_avoidance import ObstacleAvoidanceNode
        _registry_map["ObstacleAvoidanceNode"] = ObstacleAvoidanceNode
    except ImportError:
        pass
    try:
        from neuros.nodes.navigation.waypoint_nav import WaypointNavigatorNode
        _registry_map["WaypointNavigatorNode"] = WaypointNavigatorNode
    except ImportError:
        pass
    try:
        from neuros.safety import SafetySupervisor
        _registry_map["SafetySupervisor"] = SafetySupervisor
    except ImportError:
        pass

    _NODE_REGISTRY = _registry_map


def get_node_class(type_name: str):
    """Look up a node class by its type string."""
    _ensure_registry()
    cls = _NODE_REGISTRY.get(type_name)
    if cls is None:
        raise ValueError(
            f"Unknown node type: '{type_name}'. "
            f"Available: {', '.join(sorted(_NODE_REGISTRY.keys()))}"
        )
    return cls


# ── Launch Runner ─────────────────────────────────────────────────────────

class LaunchRunner:
    """
    Instantiate and run a full robot stack from a LaunchConfig.

    Example
    -------
        config = LaunchConfig.from_yaml("robot.yaml")
        runner = LaunchRunner(config)
        runner.start()
        runner.wait()
    """

    def __init__(self, config: LaunchConfig) -> None:
        self.config = config
        self._robot: Optional["Robot"] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    @property
    def robot(self) -> Optional["Robot"]:
        return self._robot

    def start(self) -> "LaunchRunner":
        """Build the robot from config and start all nodes."""
        from neuros.api.robot import Robot

        cfg = self.config

        # Set log level
        logging.getLogger("neuros").setLevel(getattr(logging, cfg.log_level, logging.INFO))

        # Create Robot
        self._robot = Robot(cfg.name, board=cfg.board)
        logger.info("[LAUNCH] Creating robot '%s' on board '%s'", cfg.name, cfg.board)

        # Instantiate and add nodes
        for spec in cfg.nodes:
            if not spec.enabled:
                logger.info("[LAUNCH] Skipping disabled node: %s", spec.name)
                continue

            cls = get_node_class(spec.type)

            # Build constructor kwargs
            kwargs = {"name": spec.name}
            kwargs.update(spec.config)
            if spec.hz is not None:
                kwargs["hz"] = spec.hz

            try:
                node = cls(**kwargs)
                self._robot.add_node(node)
                logger.info("[LAUNCH] Added %s('%s')", spec.type, spec.name)
            except Exception as e:
                logger.error("[LAUNCH] Failed to create %s('%s'): %s", spec.type, spec.name, e)

        # ROS2 Bridge
        if cfg.ros2_topics:
            try:
                from neuros.bridge.ros2 import ROS2Bridge
                bridge = ROS2Bridge(self._robot)
                for t in cfg.ros2_topics:
                    bridge.mirror_topic(
                        t.topic,
                        direction=t.direction,
                        neuros_topic=t.neuros_topic,
                        msg_type=t.msg_type,
                    )
                bridge.start()
                logger.info("[LAUNCH] ROS2 bridge started with %d topics", len(cfg.ros2_topics))
            except Exception as e:
                logger.warning("[LAUNCH] ROS2 bridge failed: %s", e)

        # RT Monitor
        if cfg.monitor:
            try:
                from neuros.monitor import RTMonitor
                mon = RTMonitor(self._robot, refresh_hz=cfg.monitor_hz, http_port=cfg.monitor_port)
                mon.start()
                logger.info("[LAUNCH] RT Monitor started on port %d", cfg.monitor_port)
            except Exception as e:
                logger.warning("[LAUNCH] Monitor failed: %s", e)

        # Start the robot
        self._robot.start()
        self._running = True
        logger.info("[LAUNCH] Robot started — %d nodes active", len(cfg.nodes))

        return self

    def wait(self, *, hz: int = 100) -> None:
        """Block and spin the robot until interrupted."""
        if self._robot is None:
            raise RuntimeError("Call start() first")
        try:
            from neuros import spin
            spin(self._robot, hz=hz)
        except KeyboardInterrupt:
            logger.info("[LAUNCH] Interrupted — shutting down")
            self.stop()

    def stop(self) -> None:
        """Stop the robot and clean up."""
        self._running = False
        if self._robot:
            self._robot.stop()
            logger.info("[LAUNCH] Robot stopped")

    def status(self) -> dict:
        """Return launch status summary."""
        return {
            "name": self.config.name,
            "board": self.config.board,
            "running": self._running,
            "nodes": [n.to_dict() for n in self.config.nodes],
            "ros2_topics": len(self.config.ros2_topics),
            "monitor": self.config.monitor,
        }


# ── ROS2 Launch XML Generator ────────────────────────────────────────────

def generate_ros2_launch_xml(config: LaunchConfig) -> str:
    """
    Generate a ROS2-compatible launch.xml from NEUROS config.
    This allows backwards-compatible use with standard ROS2 tooling.
    """
    lines = [
        '<?xml version="1.0"?>',
        '<launch>',
        f'  <!-- Auto-generated by NEUROS OS from config: {config.name} -->',
        f'  <!-- Board: {config.board} | Nodes: {len(config.nodes)} -->',
        '',
    ]

    for spec in config.nodes:
        if not spec.enabled:
            continue
        lines.append(f'  <!-- NEUROS Node: {spec.type} "{spec.name}" -->')
        lines.append(f'  <node pkg="neuros" exec="neuros_node" name="{spec.name}">')
        lines.append(f'    <param name="node_type" value="{spec.type}"/>')
        for k, v in spec.config.items():
            lines.append(f'    <param name="{k}" value="{v}"/>')
        if spec.hz:
            lines.append(f'    <param name="hz" value="{spec.hz}"/>')
        lines.append(f'  </node>')
        lines.append('')

    lines.append('</launch>')
    return '\n'.join(lines)


# ── Simple YAML Parser (no pyyaml dependency) ────────────────────────────

def _parse_yaml(text: str) -> dict:
    """Parse YAML text — uses PyYAML if available, else falls back to simple parser."""
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        logger.debug("[LAUNCH] PyYAML not installed — using built-in parser")
        return _parse_simple_yaml(text)
    except Exception as e:
        logger.warning("[LAUNCH] PyYAML parse failed (%s) — falling back to built-in", e)
        return _parse_simple_yaml(text)


def _parse_simple_yaml(text: str) -> dict:
    """
    Minimal YAML-like parser for NEUROS launch configs.
    Handles: scalars, nested dicts (indent-based), lists (- prefix).
    Not a full YAML spec — just enough for our configs.
    """
    result: Dict[str, Any] = {}
    stack: list = [(result, -1)]  # (current_dict, indent_level)

    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip()
        i += 1

        # Skip empty/comment
        if not stripped or stripped.lstrip().startswith('#'):
            continue

        indent = len(line) - len(line.lstrip())
        content = stripped.lstrip()

        # Pop stack to correct level
        while len(stack) > 1 and stack[-1][1] >= indent:
            stack.pop()

        current = stack[-1][0]

        if content.startswith('- '):
            # List item
            item_content = content[2:].strip()

            # Find parent key — the current dict should have a list as value
            if isinstance(current, dict):
                # We need to find the parent list
                # This happens when "- " appears under a key with no value
                pass

            if ':' in item_content:
                # Dict item in a list
                item_dict: Dict[str, Any] = {}
                key, _, val = item_content.partition(':')
                key = key.strip()
                val = val.strip()
                if val:
                    item_dict[key] = _parse_value(val)
                else:
                    item_dict[key] = {}

                # Read continuation lines at deeper indent
                while i < len(lines):
                    next_line = lines[i]
                    next_stripped = next_line.rstrip()
                    if not next_stripped or next_stripped.lstrip().startswith('#'):
                        i += 1
                        continue
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent <= indent:
                        break
                    nc = next_stripped.lstrip()
                    if ':' in nc:
                        nk, _, nv = nc.partition(':')
                        nk = nk.strip()
                        nv = nv.strip()
                        if nv:
                            item_dict[nk] = _parse_value(nv)
                        else:
                            item_dict[nk] = {}
                    i += 1

                # Add to parent list
                if isinstance(current, list):
                    current.append(item_dict)
                elif isinstance(current, dict):
                    # Find the last key that has a list value
                    for k in reversed(list(current.keys())):
                        if isinstance(current[k], list):
                            current[k].append(item_dict)
                            break
            else:
                val = _parse_value(item_content)
                if isinstance(current, list):
                    current.append(val)
        elif ':' in content:
            key, _, val = content.partition(':')
            key = key.strip()
            val = val.strip()

            if val:
                current[key] = _parse_value(val)
            else:
                # Check if next line is a list or nested dict
                if i < len(lines):
                    next_line = lines[i]
                    next_stripped = next_line.rstrip().lstrip()
                    if next_stripped.startswith('- '):
                        # Value is a list
                        current[key] = []
                        stack.append((current[key], indent))
                    else:
                        # Value is a nested dict
                        current[key] = {}
                        stack.append((current[key], indent))
                else:
                    current[key] = {}

    return result


def _parse_value(s: str) -> Any:
    """Parse a YAML scalar value."""
    if s.lower() in ('true', 'yes'):
        return True
    if s.lower() in ('false', 'no'):
        return False
    if s.lower() in ('null', '~', 'none'):
        return None
    # Remove quotes
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


__all__ = [
    "LaunchConfig",
    "LaunchRunner",
    "NodeSpec",
    "BridgeTopicSpec",
    "generate_ros2_launch_xml",
    "get_node_class",
]
