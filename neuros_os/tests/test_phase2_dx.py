"""
test_phase2_dx.py
=================
Tests for NEUROS OS Phase 2 Developer Experience components.

Covers:
  - LaunchConfig / LaunchRunner
  - ParameterManager / ParamGroup
  - BagRecorder / BagPlayer / BagAnalyzer
  - Inspector
"""

import json
import os
import sqlite3
import tempfile
import threading
import time
from pathlib import Path

import pytest


# ═══════════════════════════════════════════════════════════════════════════
#  LAUNCH SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

class TestLaunchConfig:
    def test_from_dict_basic(self):
        from neuros.launch import LaunchConfig
        cfg = LaunchConfig.from_dict({
            "robot": {
                "name": "test_bot",
                "board": "simulator",
                "nodes": [
                    {"type": "LEDNode", "name": "led1", "config": {"pin": 13}},
                ],
            }
        })
        assert cfg.name == "test_bot"
        assert cfg.board == "simulator"
        assert len(cfg.nodes) == 1
        assert cfg.nodes[0].type == "LEDNode"
        assert cfg.nodes[0].name == "led1"
        assert cfg.nodes[0].config == {"pin": 13}

    def test_from_dict_with_ros2_bridge(self):
        from neuros.launch import LaunchConfig
        cfg = LaunchConfig.from_dict({
            "robot": {
                "name": "ros_bot",
                "board": "simulator",
                "nodes": [],
                "ros2_bridge": {
                    "topics": [
                        {"topic": "/scan", "direction": "ros2→neuros"},
                        {"topic": "/cmd_vel", "direction": "neuros→ros2"},
                    ]
                },
            }
        })
        assert len(cfg.ros2_topics) == 2
        assert cfg.ros2_topics[0].topic == "/scan"
        assert cfg.ros2_topics[1].direction == "neuros→ros2"

    def test_fluent_api(self):
        from neuros.launch import LaunchConfig
        cfg = (LaunchConfig(name="fluent_bot", board="simulator")
               .add_node("LEDNode", "led1", pin=13)
               .add_node("MotorNode", "motor1", pin_en=12, pin_in1=23, pin_in2=24)
               .add_ros2_topic("/scan", "ros2→neuros"))
        assert len(cfg.nodes) == 2
        assert len(cfg.ros2_topics) == 1
        assert cfg.nodes[1].config["pin_en"] == 12

    def test_to_dict_roundtrip(self):
        from neuros.launch import LaunchConfig
        cfg = LaunchConfig(name="rt_bot", board="simulator")
        cfg.add_node("LEDNode", "led", pin=5)
        d = cfg.to_dict()
        cfg2 = LaunchConfig.from_dict(d)
        assert cfg2.name == "rt_bot"
        assert len(cfg2.nodes) == 1

    def test_from_json_file(self, tmp_path):
        from neuros.launch import LaunchConfig
        config_data = {
            "robot": {
                "name": "json_bot",
                "board": "simulator",
                "nodes": [{"type": "LEDNode", "name": "led"}],
            }
        }
        p = tmp_path / "config.json"
        p.write_text(json.dumps(config_data))
        cfg = LaunchConfig.from_json(str(p))
        assert cfg.name == "json_bot"

    def test_node_spec_defaults(self):
        from neuros.launch import NodeSpec
        n = NodeSpec(type="LEDNode", name="led")
        assert n.enabled is True
        assert n.priority == "NORMAL"
        assert n.hz is None
        assert n.group == "default"

    def test_generate_ros2_xml(self):
        from neuros.launch import LaunchConfig, generate_ros2_launch_xml
        cfg = LaunchConfig(name="xml_bot", board="simulator")
        cfg.add_node("LEDNode", "led", pin=13)
        xml = generate_ros2_launch_xml(cfg)
        assert "<?xml" in xml
        assert "LEDNode" in xml
        assert "led" in xml


class TestLaunchRunner:
    def test_start_stop(self):
        from neuros.launch import LaunchConfig, LaunchRunner
        cfg = LaunchConfig(name="runner_test", board="simulator")
        runner = LaunchRunner(cfg)
        runner.start()
        assert runner.robot is not None
        assert runner._running is True
        status = runner.status()
        assert status["running"] is True
        assert status["name"] == "runner_test"
        runner.stop()

    def test_runner_with_node(self):
        from neuros.launch import LaunchConfig, LaunchRunner
        cfg = LaunchConfig(name="node_test", board="simulator")
        cfg.add_node("SafetySupervisor", "safety")
        runner = LaunchRunner(cfg)
        runner.start()
        assert runner._running is True
        time.sleep(0.1)
        runner.stop()

    def test_get_node_class(self):
        from neuros.launch import get_node_class
        cls = get_node_class("SafetySupervisor")
        assert cls is not None
        with pytest.raises(ValueError):
            get_node_class("NonExistentNode")


# ═══════════════════════════════════════════════════════════════════════════
#  PARAMETER MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestParamGroup:
    def test_basic_group(self):
        from neuros.params import ParamGroup

        class DriveParams(ParamGroup):
            max_speed: float = 1.0
            turn_rate: float = 0.5
            enabled: bool = True

        p = DriveParams()
        assert p.max_speed == 1.0
        assert p.turn_rate == 0.5
        assert p.enabled is True

    def test_override(self):
        from neuros.params import ParamGroup

        class P(ParamGroup):
            x: int = 10
            y: float = 3.14

        p = P(x=42, y=2.71)
        assert p.x == 42
        assert p.y == 2.71

    def test_to_dict(self):
        from neuros.params import ParamGroup

        class P(ParamGroup):
            a: int = 1
            b: str = "hello"

        d = P().to_dict()
        assert d == {"a": 1, "b": "hello"}

    def test_update(self):
        from neuros.params import ParamGroup

        class P(ParamGroup):
            x: int = 0

        p = P()
        changes = p.update({"x": 99})
        assert len(changes) == 1
        assert changes[0] == ("x", 0, 99)
        assert p.x == 99

    def test_from_dict(self):
        from neuros.params import ParamGroup

        class P(ParamGroup):
            speed: float = 0.0

        p = P.from_dict({"speed": 5.5})
        assert p.speed == 5.5


class TestParameterManager:
    def test_register_and_get(self):
        from neuros.params import ParameterManager, ParamGroup

        class Motor(ParamGroup):
            speed: float = 1.0
            direction: int = 1

        pm = ParameterManager()
        pm.register("motor", Motor)
        assert pm.get("motor.speed") == 1.0
        assert pm.get("motor.direction") == 1

    def test_set_triggers_watcher(self):
        from neuros.params import ParameterManager, ParamGroup

        class P(ParamGroup):
            val: int = 0

        pm = ParameterManager()
        pm.register("test", P)

        changes = []
        pm.watch("test.val", lambda old, new: changes.append((old, new)))
        pm.set("test.val", 42)
        assert len(changes) == 1
        assert changes[0] == (0, 42)

    def test_wildcard_watcher(self):
        from neuros.params import ParameterManager, ParamGroup

        class P(ParamGroup):
            a: int = 0
            b: int = 0

        pm = ParameterManager()
        pm.register("grp", P)
        fired = []
        pm.watch("grp.*", lambda key, old, new: fired.append(key))
        pm.set("grp.a", 1)
        pm.set("grp.b", 2)
        assert fired == ["grp.a", "grp.b"]

    def test_set_many(self):
        from neuros.params import ParameterManager, ParamGroup

        class P(ParamGroup):
            x: int = 0
            y: int = 0

        pm = ParameterManager()
        pm.register("p", P)
        changed = pm.set_many({"p.x": 10, "p.y": 20})
        assert changed == 2
        assert pm.get("p.x") == 10

    def test_list_params(self):
        from neuros.params import ParameterManager, ParamGroup

        class P(ParamGroup):
            a: int = 0
            b: str = ""

        pm = ParameterManager()
        pm.register("g", P)
        params = pm.list_params()
        assert "g.a" in params
        assert "g.b" in params

    def test_save_load_yaml(self, tmp_path):
        from neuros.params import ParameterManager, ParamGroup

        class P(ParamGroup):
            speed: float = 1.0

        pm = ParameterManager()
        pm.register("drive", P)
        pm.set("drive.speed", 5.5)
        path = str(tmp_path / "params.yaml")
        pm.save_yaml(path)
        assert Path(path).exists()

        pm2 = ParameterManager()
        pm2.register("drive", P)
        pm2.load_yaml(path)
        assert pm2.get("drive.speed") == 5.5

    def test_summary(self):
        from neuros.params import ParameterManager, ParamGroup

        class P(ParamGroup):
            v: int = 0

        pm = ParameterManager()
        pm.register("x", P)
        s = pm.summary()
        assert s["groups"] == 1
        assert s["total_params"] == 1

    def test_no_change_returns_false(self):
        from neuros.params import ParameterManager, ParamGroup

        class P(ParamGroup):
            v: int = 5

        pm = ParameterManager()
        pm.register("x", P)
        assert pm.set("x.v", 5) is False  # No change
        assert pm.set("x.v", 10) is True


# ═══════════════════════════════════════════════════════════════════════════
#  BAG FILE MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestBagRecorder:
    def test_record_and_analyze(self, tmp_path):
        from neuros.bus.bus import NeuralBus
        from neuros.bus.message import Message
        from neuros.bags import BagRecorder, BagAnalyzer

        bus = NeuralBus()
        bag_path = str(tmp_path / "test.bag")

        rec = BagRecorder(bus, bag_path)
        rec.add_topic("/test/data")
        rec.start()

        for i in range(10):
            bus.publish(Message(topic="/test/data", data={"value": i}))
            time.sleep(0.01)

        summary = rec.stop()
        assert summary["messages"] == 10
        assert Path(bag_path).exists()

        # Analyze
        analyzer = BagAnalyzer(bag_path)
        info = analyzer.info()
        assert info["total_messages"] == 10
        assert info["topic_count"] == 1
        assert info["topics"][0]["topic"] == "/test/data"

    def test_export_csv(self, tmp_path):
        from neuros.bus.bus import NeuralBus
        from neuros.bus.message import Message
        from neuros.bags import BagRecorder, BagAnalyzer

        bus = NeuralBus()
        bag_path = str(tmp_path / "export.bag")
        csv_path = str(tmp_path / "out.csv")

        rec = BagRecorder(bus, bag_path)
        rec.add_topic("#")
        rec.start()

        for i in range(5):
            bus.publish(Message(topic="/sensor/temp", data={"celsius": 20 + i}))
            time.sleep(0.02)

        time.sleep(0.2)  # Allow flush
        rec.stop()

        analyzer = BagAnalyzer(bag_path)
        count = analyzer.export_csv("/sensor/temp", csv_path)
        assert count == 5
        assert Path(csv_path).exists()

        content = Path(csv_path).read_text()
        assert "celsius" in content
        assert "timestamp" in content

    def test_status(self, tmp_path):
        from neuros.bus.bus import NeuralBus
        from neuros.bags import BagRecorder

        bus = NeuralBus()
        rec = BagRecorder(bus, str(tmp_path / "s.bag"))
        rec.add_topic("#")
        rec.start()
        status = rec.status()
        assert status["recording"] is True
        rec.stop()

    def test_topics_list(self, tmp_path):
        from neuros.bus.bus import NeuralBus
        from neuros.bus.message import Message
        from neuros.bags import BagRecorder, BagAnalyzer

        bus = NeuralBus()
        bag_path = str(tmp_path / "multi.bag")

        rec = BagRecorder(bus, bag_path)
        rec.add_topic("#")
        rec.start()
        bus.publish(Message(topic="/a", data="1"))
        bus.publish(Message(topic="/b", data="2"))
        time.sleep(0.05)
        rec.stop()

        analyzer = BagAnalyzer(bag_path)
        topics = analyzer.topics()
        assert "/a" in topics
        assert "/b" in topics


class TestBagPlayer:
    def test_play_bag(self, tmp_path):
        from neuros.bus.bus import NeuralBus
        from neuros.bus.message import Message
        from neuros.bags import BagRecorder, BagPlayer

        bus = NeuralBus()
        bag_path = str(tmp_path / "play.bag")

        # Record
        rec = BagRecorder(bus, bag_path)
        rec.add_topic("#")
        rec.start()
        for i in range(5):
            bus.publish(Message(topic="/data", data={"i": i}))
            time.sleep(0.01)
        rec.stop()

        # Replay
        received = []
        bus.subscribe("/data", lambda m: received.append(m.data), node_id="player_test")

        player = BagPlayer(bus, bag_path)
        player.play(speed=10.0, blocking=True)

        assert len(received) >= 5
        assert player.progress >= 0.99

    def test_player_status(self, tmp_path):
        from neuros.bus.bus import NeuralBus
        from neuros.bags import BagPlayer

        bus = NeuralBus()
        # Create empty bag
        bag_path = str(tmp_path / "empty.bag")
        db = sqlite3.connect(bag_path)
        db.executescript("""
            CREATE TABLE IF NOT EXISTS bag_meta (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, timestamp REAL, topic TEXT, data TEXT, seq INTEGER DEFAULT 0);
        """)
        db.close()

        player = BagPlayer(bus, bag_path)
        status = player.status()
        assert status["playing"] is False


# ═══════════════════════════════════════════════════════════════════════════
#  INSPECTOR
# ═══════════════════════════════════════════════════════════════════════════

class TestInspector:
    def test_inspector_start_stop(self):
        from neuros.api.robot import Robot
        from neuros.inspector import Inspector

        robot = Robot("inspect_test", board="simulator")
        robot.start()

        inspector = Inspector(robot, port=18899)
        inspector.start()
        time.sleep(0.2)

        status = inspector.get_status()
        assert status["robot"] == "inspect_test"
        assert status["inspector_port"] == 18899

        inspector.stop()
        robot.stop()

    def test_topic_tracking(self):
        from neuros.api.robot import Robot
        from neuros.bus.message import Message
        from neuros.inspector import Inspector

        robot = Robot("track_test", board="simulator")
        robot.start()

        inspector = Inspector(robot, port=18898)
        inspector.start()
        time.sleep(0.1)

        # Publish some messages
        robot._bus.publish(Message(topic="/test/topic", data={"x": 1}))
        robot._bus.publish(Message(topic="/test/topic", data={"x": 2}))
        time.sleep(0.1)

        topics = inspector.get_topics()
        found = [t for t in topics if t["topic"] == "/test/topic"]
        assert len(found) >= 1
        assert found[0]["count"] >= 2

        inspector.stop()
        robot.stop()

    def test_node_listing(self):
        from neuros.api.robot import Robot
        from neuros.safety import SafetySupervisor
        from neuros.inspector import Inspector

        robot = Robot("nodes_test", board="simulator")
        robot.add_node(SafetySupervisor())
        robot.start()

        inspector = Inspector(robot, port=18897)
        inspector.start()
        time.sleep(0.1)

        nodes = inspector.get_nodes()
        assert len(nodes) >= 1
        types = [n["type"] for n in nodes]
        assert "SafetySupervisor" in types

        inspector.stop()
        robot.stop()

    def test_graph_api(self):
        from neuros.api.robot import Robot
        from neuros.inspector import Inspector

        robot = Robot("graph_test", board="simulator")
        robot.start()

        inspector = Inspector(robot, port=18896)
        inspector.start()
        time.sleep(0.1)

        graph = inspector.get_graph()
        assert "nodes" in graph
        assert "links" in graph

        inspector.stop()
        robot.stop()


# ═══════════════════════════════════════════════════════════════════════════
#  INTEGRATION: Launch + Params + Bag together
# ═══════════════════════════════════════════════════════════════════════════

class TestPhase2Integration:
    def test_launch_with_params(self):
        """Launch a robot and manage its parameters."""
        from neuros.launch import LaunchConfig, LaunchRunner
        from neuros.params import ParameterManager, ParamGroup

        class NavParams(ParamGroup):
            max_speed: float = 1.0
            lookahead: float = 0.5

        cfg = LaunchConfig(name="int_test", board="simulator")
        runner = LaunchRunner(cfg)
        runner.start()

        pm = ParameterManager()
        nav = pm.register("nav", NavParams)
        assert nav.max_speed == 1.0

        pm.set("nav.max_speed", 2.0)
        assert nav.max_speed == 2.0

        runner.stop()

    def test_record_during_launch(self, tmp_path):
        """Record bag while robot is running from launch config."""
        from neuros.launch import LaunchConfig, LaunchRunner
        from neuros.bags import BagRecorder, BagAnalyzer
        from neuros.bus.message import Message

        cfg = LaunchConfig(name="rec_test", board="simulator")
        runner = LaunchRunner(cfg)
        runner.start()

        bag_path = str(tmp_path / "session.bag")
        rec = BagRecorder(runner.robot._bus, bag_path)
        rec.add_topic("#")
        rec.start()

        # Publish test data
        for i in range(5):
            runner.robot._bus.publish(
                Message(topic="/test/sensor", data={"val": i}))
            time.sleep(0.01)

        rec.stop()
        runner.stop()

        analyzer = BagAnalyzer(bag_path)
        info = analyzer.info()
        assert info["total_messages"] >= 5
