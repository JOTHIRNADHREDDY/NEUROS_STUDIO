"""
tests/test_phase1.py
====================
Phase 1 integration test suite.

Tests cover the complete stack:
  Robot → Kernel → Scheduler → NeuralBus → Nodes → SimulatorHAL

Run: pytest tests/ -v
"""

import time
import threading
import pytest

# ── import NEUROS ──────────────────────────────────────────────────────────
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from neuros import Robot, Node, NeuralBus, Kernel, Message
from neuros.kernel.core import Domain, KernelState
from neuros.kernel.watchdog import Watchdog
from neuros.kernel.scheduler import Scheduler
from neuros.bus.message import Topic, MessageType, QoS
from neuros.hal.drivers.simulator import SimulatorHAL
from neuros.hal.base import PinMode, PinState
from neuros.ai import LLMOrchestrator


# ══════════════════════════════════════════════════════════════════════════
#  FIXTURES
# ══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sim_hal():
    hal = SimulatorHAL(seed=42)
    hal.connect()
    yield hal
    hal.disconnect()


@pytest.fixture
def bus():
    return NeuralBus()


@pytest.fixture
def kernel():
    k = Kernel(domain=Domain.A, kernel_hz=100, name="test-kernel")
    k.start()
    yield k
    k.shutdown()


@pytest.fixture
def robot():
    r = Robot(name="test-robot", board="simulator", kernel_hz=100)
    r.start()
    yield r
    r.stop()


# ══════════════════════════════════════════════════════════════════════════
#  1. KERNEL TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestKernel:

    def test_kernel_starts_in_running_state(self, kernel):
        assert kernel.state == KernelState.RUNNING

    def test_kernel_registers_node(self, kernel, bus, sim_hal):
        class DummyNode(Node):
            def tick(self): pass

        node = DummyNode("dummy", hz=10)
        node._bus = bus
        node._hal = sim_hal
        nid = kernel.register(node)
        assert nid is not None
        assert kernel.node_count == 1

    def test_kernel_status_shape(self, kernel):
        status = kernel.status()
        assert "state"      in status
        assert "uptime_s"   in status
        assert "node_count" in status
        assert "nodes"      in status

    def test_kernel_heartbeat(self, kernel, bus, sim_hal):
        class HeartbeatNode(Node):
            def tick(self): pass

        node = HeartbeatNode("hb-node", hz=10)
        node._bus = bus
        node._hal = sim_hal
        nid = kernel.register(node)
        # Heartbeat should be accepted without error
        kernel.heartbeat(nid)

    def test_kernel_emergency_stop(self, kernel):
        fired = []
        kernel.on_emergency(lambda reason: fired.append(reason))
        kernel.emergency_stop("test-reason")
        assert kernel.state == KernelState.EMERGENCY
        assert "test-reason" in fired

    def test_kernel_uptime_increases(self, kernel):
        t0 = kernel.uptime_s
        time.sleep(0.05)
        assert kernel.uptime_s > t0


# ══════════════════════════════════════════════════════════════════════════
#  2. NEURAL BUS TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestNeuralBus:

    def test_publish_subscribe(self, bus):
        received = []
        bus.subscribe("/test/topic", received.append)
        bus.publish(Message(topic="/test/topic", data={"x": 42}))
        assert len(received) == 1
        assert received[0].data["x"] == 42

    def test_wildcard_subscribe(self, bus):
        received = []
        bus.subscribe("/sensor/*", received.append)
        bus.publish(Message(topic="/sensor/imu",   data={"ax": 0.1}))
        bus.publish(Message(topic="/sensor/lidar",  data={"range": 1.5}))
        bus.publish(Message(topic="/actuator/motor", data={"speed": 0.5}))
        assert len(received) == 2

    def test_hash_subscribe_gets_all(self, bus):
        received = []
        bus.subscribe("#", received.append)
        for i in range(5):
            bus.publish(Message(topic=f"/topic/{i}", data=i))
        assert len(received) == 5

    def test_message_sequence_numbers(self, bus):
        seqs = []
        bus.subscribe("/seq/test", lambda m: seqs.append(m.seq))
        for _ in range(3):
            bus.publish(Message(topic="/seq/test", data=None))
        assert seqs == [1, 2, 3]

    def test_unsubscribe(self, bus):
        received = []
        sub = bus.subscribe("/unsub/test", received.append)
        bus.publish(Message(topic="/unsub/test", data=1))
        bus.unsubscribe(sub)
        bus.publish(Message(topic="/unsub/test", data=2))
        assert len(received) == 1

    def test_message_age(self):
        msg = Message(topic="/age/test", data=None)
        time.sleep(0.01)
        assert msg.age_ms() >= 10.0

    def test_topic_list(self, bus):
        bus.publish(Message(topic="/robot/a", data=None))
        bus.publish(Message(topic="/robot/b", data=None))
        topics = bus.topic_list()
        assert "/robot/a" in topics
        assert "/robot/b" in topics

    def test_subscriber_count(self, bus):
        bus.subscribe("/count/test", lambda m: None)
        bus.subscribe("/count/test", lambda m: None)
        assert bus.subscriber_count("/count/test") == 2


# ══════════════════════════════════════════════════════════════════════════
#  3. SIMULATOR HAL TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestSimulatorHAL:

    def test_connect_disconnect(self):
        hal = SimulatorHAL()
        assert not hal.is_connected
        hal.connect()
        assert hal.is_connected
        hal.disconnect()
        assert not hal.is_connected

    def test_pin_configure_write_read(self, sim_hal):
        sim_hal.pin("LED", board_pin=13, mode=PinMode.OUTPUT)
        sim_hal.write("LED", PinState.HIGH)
        assert sim_hal.read("LED") == PinState.HIGH
        sim_hal.write("LED", PinState.LOW)
        assert sim_hal.read("LED") == PinState.LOW

    def test_pin_toggle(self, sim_hal):
        sim_hal.pin("BTN", board_pin=2, mode=PinMode.OUTPUT)
        sim_hal.write("BTN", PinState.LOW)
        sim_hal.toggle("BTN")
        assert sim_hal.read("BTN") == PinState.HIGH
        sim_hal.toggle("BTN")
        assert sim_hal.read("BTN") == PinState.LOW

    def test_inject_pin_read_constant(self, sim_hal):
        A0 = 14
        sim_hal.pin("SENSOR", board_pin=A0, mode=PinMode.ANALOG_IN)
        sim_hal.inject_pin_read(14, 0.75)
        val = sim_hal.read("SENSOR")
        assert abs(val - 0.75) < 0.01

    def test_inject_pin_read_callable(self, sim_hal):
        import random
        sim_hal.pin("NOISE", board_pin=15, mode=PinMode.ANALOG_IN)
        sim_hal.inject_pin_read(15, lambda: 0.5)
        for _ in range(10):
            val = sim_hal.read("NOISE")
            assert 0.4 <= val <= 0.6  # close to 0.5

    def test_write_log(self, sim_hal):
        sim_hal.pin("LOG_PIN", board_pin=10, mode=PinMode.OUTPUT)
        sim_hal.clear_log()
        t0 = time.monotonic()
        sim_hal.write("LOG_PIN", PinState.HIGH)
        sim_hal.write("LOG_PIN", PinState.LOW)
        log = sim_hal.get_write_log(since=t0)
        assert len(log) == 2

    def test_board_info(self, sim_hal):
        info = sim_hal.board_info()
        assert "board" in info
        assert "simulator" in info["board"].lower()

    def test_noise_injection(self):
        hal = SimulatorHAL(noise_level=0.1, seed=99)
        hal.connect()
        hal.pin("NOISY", board_pin=5, mode=PinMode.ANALOG_IN)
        hal.inject_pin_read(5, 0.5)
        readings = [hal.read("NOISY") for _ in range(20)]
        # Values should vary around 0.5 due to noise
        assert any(abs(r - 0.5) > 0.001 for r in readings)
        hal.disconnect()


# ══════════════════════════════════════════════════════════════════════════
#  4. NODE TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestNode:

    def test_node_lifecycle(self, bus, sim_hal):
        from neuros.nodes.base import NodeState

        ticked = []

        class CountNode(Node):
            def configure(self):
                self.counter = 0
            def tick(self):
                self.counter += 1
                ticked.append(self.counter)

        node = CountNode("counter", hz=100)
        node._bus = bus
        node._hal = sim_hal

        assert node.state == NodeState.UNCONFIGURED
        node._configure()
        assert node.state == NodeState.INACTIVE
        node._activate()
        assert node.state == NodeState.ACTIVE

        # Tick 5 times
        for _ in range(5):
            node._tick()

        assert len(ticked) == 5
        assert ticked[-1] == 5

    def test_node_publish_subscribe(self, bus, sim_hal):
        received = []

        class PublisherNode(Node):
            def tick(self):
                self.publish("/test/pub", {"val": 99})

        bus.subscribe("/test/pub", received.append)

        node = PublisherNode("pub-node", hz=10)
        node._bus = bus
        node._hal = sim_hal
        node._configure()
        node._activate()
        node._tick()

        assert len(received) == 1
        assert received[0].data["val"] == 99

    def test_node_emergency_stop(self, bus, sim_hal):
        from neuros.nodes.base import NodeState

        class SafeNode(Node):
            def tick(self): pass

        node = SafeNode("safe-node", hz=10)
        node._bus = bus
        node._hal = sim_hal
        node._configure()
        node._activate()

        node.on_emergency_stop("test")
        assert node.state == NodeState.SUSPENDED


# ══════════════════════════════════════════════════════════════════════════
#  5. ROBOT (FULL STACK) TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestRobot:

    def test_robot_starts_with_simulator(self, robot):
        assert robot._started is True
        assert robot._hal is not None

    def test_robot_pin_write_read(self, robot):
        robot.pin("LED", pin=13, mode="output")
        robot.write("LED", PinState.HIGH)
        val = robot.read("LED")
        assert val == PinState.HIGH

    def test_robot_toggle(self, robot):
        robot.pin("TOG", pin=7, mode="output")
        robot.write("TOG", PinState.LOW)
        robot.toggle("TOG")
        assert robot.read("TOG") == PinState.HIGH

    def test_robot_decorator_api(self, robot):
        count = [0]
        robot.pin("LED", pin=13, mode="output")

        @robot.every(hz=1000, name="fast-blink")
        def blink():
            count[0] += 1

        time.sleep(0.05)   # let the scheduler run ~50 ticks
        assert count[0] > 5

    def test_robot_publish_subscribe(self, robot):
        received = []
        robot.subscribe("sensor/test", received.append)
        robot.publish("sensor/test", {"x": 1.0})
        time.sleep(0.01)
        assert len(received) == 1

    def test_robot_status_shape(self, robot):
        status = robot.status()
        assert "robot"   in status
        assert "started" in status
        assert "state"   in status

    def test_robot_add_node(self, robot):
        class MyNode(Node):
            def tick(self): pass

        node = MyNode("my-node", hz=10)
        robot.add_node(node)
        # Node should appear in kernel status
        status = robot.status()
        assert any("my-node" in v.get("name","") for v in status["nodes"].values())

    def test_robot_stop_idempotent(self, robot):
        robot.stop()
        robot.stop()   # second stop should not raise


# ══════════════════════════════════════════════════════════════════════════
#  6. WATCHDOG TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestWatchdog:

    def test_watchdog_fires_on_timeout(self):
        fired = []
        wd = Watchdog(poll_hz=1000)
        wd.register("test", timeout_s=0.05, callback=lambda n: fired.append(n))
        wd.start()
        time.sleep(0.15)
        wd.stop()
        assert len(fired) > 0
        assert fired[0] == "test"

    def test_watchdog_does_not_fire_when_kicked(self):
        fired = []
        wd = Watchdog(poll_hz=1000)
        wd.register("kicker", timeout_s=0.05, callback=lambda n: fired.append(n))
        wd.start()
        for _ in range(10):
            wd.kick("kicker")
            time.sleep(0.01)
        wd.stop()
        assert len(fired) == 0

    def test_watchdog_disable_enable(self):
        fired = []
        wd = Watchdog(poll_hz=1000)
        wd.register("dis", timeout_s=0.02, callback=lambda n: fired.append(n))
        wd.disable("dis")
        wd.start()
        time.sleep(0.1)
        wd.stop()
        assert len(fired) == 0


# ══════════════════════════════════════════════════════════════════════════
#  7. SCHEDULER TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestScheduler:

    def test_task_runs_at_declared_rate(self):
        count = [0]
        sched = Scheduler(driver_hz=10_000)
        sched.add("counter", lambda: count.__setitem__(0, count[0]+1), hz=100)
        sched.start()
        time.sleep(0.15)   # ~15 ticks at 100 Hz
        sched.stop()
        assert count[0] >= 10, f"Expected ≥10 ticks, got {count[0]}"

    def test_higher_priority_task_runs(self):
        order = []
        sched = Scheduler(driver_hz=10_000)
        sched.add("low",  lambda: order.append("low"),  hz=1000, priority=10)
        sched.add("high", lambda: order.append("high"), hz=1000, priority=90)
        sched.start()
        time.sleep(0.01)
        sched.stop()
        # Both should have run
        assert "high" in order
        assert "low"  in order


# ══════════════════════════════════════════════════════════════════════════
#  8. LLM ORCHESTRATOR TESTS (Phase 1 stub)
# ══════════════════════════════════════════════════════════════════════════

class TestLLMOrchestrator:

    def test_parse_blink_intent(self):
        llm = LLMOrchestrator()
        intent = llm.parse("blink the LED at 2 Hz")
        assert intent is not None
        assert intent.action == "blink"
        assert intent.params.get("hz") == 2.0

    def test_parse_stop_intent(self):
        llm = LLMOrchestrator()
        intent = llm.parse("stop")
        assert intent.action == "stop_all"

    def test_parse_unknown(self):
        llm = LLMOrchestrator()
        intent = llm.parse("make me a sandwich")
        assert intent.action == "unknown"
        assert intent.confidence == 0.0

    def test_parse_move_forward(self):
        llm = LLMOrchestrator()
        intent = llm.parse("move forward please")
        assert intent.action == "motor_forward"

    def test_history_recorded(self):
        llm = LLMOrchestrator()
        llm.parse("blink led")
        llm.parse("stop")
        assert len(llm.history) == 4   # 2 user + 2 assistant


# ══════════════════════════════════════════════════════════════════════════
#  9. MESSAGE / TOPIC TESTS
# ══════════════════════════════════════════════════════════════════════════

class TestMessage:

    def test_topic_must_start_with_slash(self):
        with pytest.raises(ValueError):
            Topic("bad/topic")

    def test_topic_hash(self):
        t1 = Topic("/robot/imu")
        t2 = Topic("/robot/imu")
        assert t1 == t2
        assert hash(t1) == hash(t2)

    def test_message_is_stale(self):
        msg = Message(topic="/stale/test", data=None)
        time.sleep(0.02)
        assert msg.is_stale(max_age_ms=10)
        assert not msg.is_stale(max_age_ms=1000)

    def test_message_type_default(self):
        msg = Message(topic="/type/test", data={})
        assert msg.msg_type == MessageType.DATA

    def test_message_unique_ids(self):
        ids = {Message(topic="/x", data=None).msg_id for _ in range(100)}
        assert len(ids) == 100
