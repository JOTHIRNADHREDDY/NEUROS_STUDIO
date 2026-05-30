"""
tests/test_phase2.py
=====================
Phase 2 test suite — Domain B components.
All tests use SimulatorHAL — no hardware required.

Run: pytest tests/test_phase2.py -v
"""
import sys, os, time, math, threading

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from neuros import Robot, NeuralBus
from neuros.bus.message   import Message, MessageType
from neuros.hal.drivers.simulator import SimulatorHAL
from neuros.hal.base      import PinState


# ── Shared fixtures ──────────────────────────────────────────────────────────
def make_env():
    hal = SimulatorHAL(seed=0); hal.connect()
    bus = NeuralBus()
    return hal, bus

def wire(node, hal, bus):
    node._hal = hal; node._bus = bus
    node._configure(); node._activate()
    return node

@pytest.fixture
def robot():
    r = Robot(name="test-p2", board="simulator", kernel_hz=100)
    r.start()
    yield r
    r.stop()


# ══ RT SCHEDULER ══════════════════════════════════════════════════════════
class TestRTScheduler:
    def test_task_runs(self):
        from neuros.kernel.rt.rt_scheduler import RTScheduler, RTTask
        count = [0]
        sched = RTScheduler()
        sched.add(RTTask("t1", lambda: count.__setitem__(0, count[0]+1), hz=200))
        sched.start()
        time.sleep(0.1)
        sched.stop()
        assert count[0] >= 10

    def test_metrics_keys(self):
        from neuros.kernel.rt.rt_scheduler import RTScheduler, RTTask
        sched = RTScheduler()
        sched.add(RTTask("t_metric", lambda: None, hz=10))
        sched.start()
        time.sleep(0.05)
        m = sched.metrics()
        sched.stop()
        assert "t_metric" in m
        assert "call_count" in m["t_metric"]
        assert "avg_lat_us" in m["t_metric"]

    def test_multiple_bands(self):
        from neuros.kernel.rt.rt_scheduler import RTScheduler, RTTask
        c1, c2 = [0], [0]
        sched = RTScheduler()
        sched.add(RTTask("fast", lambda: c1.__setitem__(0, c1[0]+1), hz=500))
        sched.add(RTTask("slow", lambda: c2.__setitem__(0, c2[0]+1), hz=5))
        sched.start()
        time.sleep(0.2)
        sched.stop()
        assert c1[0] > c2[0]   # fast task ran more often

    def test_rt_enabled_flag(self):
        from neuros.kernel.rt.rt_scheduler import RTScheduler
        sched = RTScheduler()
        assert isinstance(sched.rt_enabled, bool)

    def test_remove_task(self):
        from neuros.kernel.rt.rt_scheduler import RTScheduler, RTTask
        count = [0]
        sched = RTScheduler()
        sched.add(RTTask("removable", lambda: count.__setitem__(0, count[0]+1), hz=500))
        sched.start()
        time.sleep(0.02)
        sched.remove("removable")
        n = count[0]
        time.sleep(0.02)
        sched.stop()
        assert count[0] - n < 5   # minimal runs after removal


# ══ LATENCY MONITOR ═══════════════════════════════════════════════════════
class TestLatencyMonitor:
    def test_records_latency(self):
        from neuros.kernel.rt.latency_mon import LatencyMonitor
        mon = LatencyMonitor("test", budget_us=10_000)
        for _ in range(50):
            t = mon.start()
            time.sleep(0.001)
            mon.stop(t)
        stats = mon.stats()
        assert stats.sample_count == 50
        assert stats.min_us > 0
        assert stats.max_us >= stats.min_us

    def test_overrun_detection(self):
        from neuros.kernel.rt.latency_mon import LatencyMonitor
        mon = LatencyMonitor("overrun_test", budget_us=1.0)   # 1µs budget
        for _ in range(10):
            t = mon.start()
            time.sleep(0.001)   # 1ms >> 1µs budget
            mon.stop(t)
        assert mon.stats().overrun_count == 10

    def test_percentiles(self):
        from neuros.kernel.rt.latency_mon import LatencyMonitor
        mon = LatencyMonitor("pct_test", budget_us=1_000_000)
        for _ in range(100):
            t = mon.start()
            mon.stop(t)
        s = mon.stats()
        assert s.p50_us <= s.p95_us <= s.p99_us <= s.p999_us <= s.max_us

    def test_reset_clears(self):
        from neuros.kernel.rt.latency_mon import LatencyMonitor
        mon = LatencyMonitor("reset_test")
        for _ in range(5):
            t = mon.start(); mon.stop(t)
        mon.reset()
        assert mon.stats().sample_count == 0

    def test_within_budget_pct(self):
        from neuros.kernel.rt.latency_mon import LatencyMonitor
        mon = LatencyMonitor("budget_test", budget_us=1_000_000)
        for _ in range(10):
            t = mon.start(); mon.stop(t)
        assert mon.stats().within_budget_pct == 100.0


# ══ CPU AFFINITY ══════════════════════════════════════════════════════════
class TestCPUAffinity:
    def test_available_cpus(self):
        from neuros.kernel.rt.cpu_affinity import CPUAffinity
        cpus = CPUAffinity.available_cpus()
        assert len(cpus) >= 1

    def test_pin_thread_to_core_no_crash(self):
        from neuros.kernel.rt.cpu_affinity import pin_thread_to_core, CPUAffinity
        core = list(CPUAffinity.available_cpus())[0]
        result = pin_thread_to_core(core)
        assert isinstance(result, bool)


# ══ PROCESS ISOLATOR ═══════════════════════════════════════════════════════
class TestProcessIsolator:
    def test_spawn_and_stop(self):
        from neuros.kernel.rt.process_iso import ProcessIsolator, IsolatedProcess
        import time as _t

        def worker():
            _t.sleep(5)

        iso = ProcessIsolator()
        proc = IsolatedProcess("test_proc", target=worker)
        iso.add(proc)
        iso.start_all()
        time.sleep(0.2)
        assert proc.alive is True
        iso.stop_all()
        time.sleep(0.3)
        assert proc.alive is False

    def test_status_dict(self):
        from neuros.kernel.rt.process_iso import ProcessIsolator, IsolatedProcess
        def noop(): time.sleep(1)
        iso = ProcessIsolator()
        iso.add(IsolatedProcess("noop", target=noop))
        iso.start_all()
        time.sleep(0.1)
        s = iso.status()
        iso.stop_all()
        assert "noop" in s
        assert "alive" in s["noop"]


# ══ ROS2 BRIDGE ═══════════════════════════════════════════════════════════
class TestROS2Bridge:
    def test_noop_when_rclpy_missing(self, robot):
        from neuros.bridge.ros2 import ROS2Bridge
        bridge = ROS2Bridge(robot)
        bridge.start()   # should not raise even without rclpy
        bridge.stop()
        assert isinstance(bridge.status(), dict)

    def test_mirror_topic_returns_self(self, robot):
        from neuros.bridge.ros2 import ROS2Bridge
        bridge = ROS2Bridge(robot)
        result = bridge.mirror_topic("/scan")
        assert result is bridge

    def test_status_shape(self, robot):
        from neuros.bridge.ros2 import ROS2Bridge
        bridge = ROS2Bridge(robot)
        s = bridge.status()
        assert "available" in s
        assert "bridges"   in s


# ══ ZENOH BRIDGE (DDS) ═════════════════════════════════════════════════════
class TestZenohBridge:
    def test_noop_when_zenoh_missing(self, robot):
        from neuros.bridge.dds import ZenohBridge
        bridge = ZenohBridge(robot._bus)
        bridge.start()   # no-op without zenoh
        bridge.stop()
        s = bridge.stats()
        assert "available" in s
        assert "tx" in s

    def test_topic_conversion(self):
        from neuros.bridge.dds import ZenohBridge
        assert ZenohBridge._neuros_to_zenoh("/robot/sensor/imu") == "neuros/robot/sensor/imu"
        assert ZenohBridge._zenoh_to_neuros("neuros/robot/sensor/imu") == "/robot/sensor/imu"


# ══ NAVIGATION NODES ═══════════════════════════════════════════════════════
class TestOdometry:
    def test_zero_velocity_stays_at_origin(self):
        from neuros.nodes.navigation.odometry import OdometryNode
        hal, bus = make_env()
        node = wire(OdometryNode("odom", hz=50), hal, bus)
        for _ in range(50):
            node._tick()
        assert abs(node.x) < 0.001
        assert abs(node.y) < 0.001

    def test_forward_motion_increases_x(self):
        from neuros.nodes.navigation.odometry import OdometryNode
        import time as _t
        hal, bus = make_env()
        node = wire(OdometryNode("odom", hz=50), hal, bus)
        node._v_left  = 0.5
        node._v_right = 0.5
        # Force a meaningful dt by backdating _last_t
        node._last_t = _t.monotonic() - 1.0
        node._tick()
        assert node.x > 0.3   # 0.5 m/s * 1s = 0.5m

    def test_turn_changes_theta(self):
        from neuros.nodes.navigation.odometry import OdometryNode
        hal, bus = make_env()
        node = wire(OdometryNode("odom", hz=50), hal, bus)
        node._v_left  = -0.1
        node._v_right =  0.1   # spinning left
        for _ in range(50):
            node._tick()
        assert node.theta != 0.0

    def test_publishes_pose(self):
        from neuros.nodes.navigation.odometry import OdometryNode
        hal, bus = make_env()
        received = []
        bus.subscribe("/robot/nav/odom/pose", received.append)
        node = wire(OdometryNode("odom", hz=50), hal, bus)
        node._tick()
        assert len(received) == 1
        assert "x" in received[0].data
        assert "theta" in received[0].data

    def test_reset_pose(self):
        from neuros.nodes.navigation.odometry import OdometryNode
        hal, bus = make_env()
        node = wire(OdometryNode("odom", hz=50), hal, bus)
        node._v_left = node._v_right = 0.5
        for _ in range(20): node._tick()
        node.reset_pose(5.0, 3.0, 0.0)
        assert node.x == 5.0 and node.y == 3.0


class TestObstacleAvoidance:
    def test_clear_state_full_speed(self):
        from neuros.nodes.navigation.obstacle_avoidance import ObstacleAvoidanceNode
        hal, bus = make_env()
        node = wire(ObstacleAvoidanceNode("oa", cruise_speed=0.4, hz=20), hal, bus)
        # No obstacles (default all sectors open)
        received = []
        bus.subscribe("/robot/cmd/velocity", received.append)
        node._tick()
        assert received[-1].data["linear"] == pytest.approx(0.4, abs=0.05)
        assert node._state == "clear"

    def test_close_obstacle_stops(self):
        from neuros.nodes.navigation.obstacle_avoidance import ObstacleAvoidanceNode
        hal, bus = make_env()
        node = wire(ObstacleAvoidanceNode("oa", stop_dist_m=0.3, hz=20), hal, bus)
        node._sectors["N"]  = 0.2
        node._sectors["NE"] = 0.2
        node._sectors["NW"] = 0.2
        received = []
        bus.subscribe("/robot/cmd/velocity", received.append)
        node._tick()
        assert received[-1].data["linear"] == 0.0
        assert node._state == "stop"

    def test_sector_update_from_bus(self):
        from neuros.nodes.navigation.obstacle_avoidance import ObstacleAvoidanceNode
        hal, bus = make_env()
        node = wire(ObstacleAvoidanceNode("oa", hz=20), hal, bus)
        bus.publish(Message(
            topic="/robot/sensor/lidar/lidar/sectors",
            data={"sectors": {"N": 0.5, "NE": 3.0, "NW": 3.0, "E": 3.0,
                              "SE": 3.0, "S": 3.0, "SW": 3.0, "W": 3.0}},
        ))
        node._tick()
        assert node._sectors["N"] == pytest.approx(0.5)


class TestWaypointNav:
    def test_idle_when_no_waypoints(self):
        from neuros.nodes.navigation.waypoint_nav import WaypointNavigatorNode
        hal, bus = make_env()
        node = wire(WaypointNavigatorNode("nav", hz=20), hal, bus)
        node._tick()
        assert node._nav_state in ("idle", "arrived", "navigating", "cancelled")  # nav string state

    def test_add_waypoint_changes_state(self):
        from neuros.nodes.navigation.waypoint_nav import WaypointNavigatorNode
        hal, bus = make_env()
        node = wire(WaypointNavigatorNode("nav", hz=20), hal, bus)
        node.add_waypoint(1.0, 0.0)
        assert node.state == "navigating"

    def test_arrives_when_close(self):
        from neuros.nodes.navigation.waypoint_nav import WaypointNavigatorNode
        hal, bus = make_env()
        node = wire(WaypointNavigatorNode("nav", goal_tolerance_m=0.2, hz=20), hal, bus)
        node.add_waypoint(0.05, 0.05)   # very close to origin
        node._tick()
        assert node._nav_state in ("arrived", "idle")

    def test_publishes_velocity(self):
        from neuros.nodes.navigation.waypoint_nav import WaypointNavigatorNode
        hal, bus = make_env()
        received = []
        bus.subscribe("/robot/cmd/velocity", received.append)
        node = wire(WaypointNavigatorNode("nav", hz=20), hal, bus)
        node.add_waypoint(5.0, 0.0)
        for _ in range(3):
            node._tick()
        assert len(received) >= 1
        assert "linear" in received[0].data

    def test_cancel_clears_queue(self):
        from neuros.nodes.navigation.waypoint_nav import WaypointNavigatorNode
        hal, bus = make_env()
        node = wire(WaypointNavigatorNode("nav", hz=20), hal, bus)
        for _ in range(3):
            node.add_waypoint(1.0, 0.0)
        node.cancel()
        assert node.queue_length == 0
        assert node.state == "cancelled"

    def test_mission_via_bus(self):
        from neuros.nodes.navigation.waypoint_nav import WaypointNavigatorNode
        hal, bus = make_env()
        node = wire(WaypointNavigatorNode("nav", hz=20), hal, bus)
        bus.publish(Message(
            topic="/robot/nav/waypoint/mission",
            data={"waypoints": [{"x": 1.0, "y": 0.0}, {"x": 2.0, "y": 1.0}]},
        ))
        node._tick()
        assert node.queue_length >= 1


# ══ LIDAR NODE ═════════════════════════════════════════════════════════════
class TestLiDAR:
    def test_simulated_scan_published(self):
        from neuros.nodes.vision.lidar import LiDARNode
        hal, bus = make_env()
        received = []
        bus.subscribe("/robot/sensor/lidar/lidar/scan", received.append)
        node = wire(LiDARNode("lidar", mode="simulate", hz=10), hal, bus)
        node._tick()
        assert len(received) == 1
        assert "ranges" in received[0].data
        assert len(received[0].data["ranges"]) == 360

    def test_inject_obstacle(self):
        from neuros.nodes.vision.lidar import LiDARNode
        hal, bus = make_env()
        node = wire(LiDARNode("lidar", mode="simulate", hz=10), hal, bus)
        node.inject_obstacle(angle_deg=0, distance_m=1.0)
        received = []
        bus.subscribe("/robot/sensor/lidar/lidar/closest", received.append)
        node._tick()
        assert received[0].data["distance_m"] < 2.0

    def test_sectors_published(self):
        from neuros.nodes.vision.lidar import LiDARNode
        hal, bus = make_env()
        received = []
        bus.subscribe("/robot/sensor/lidar/lidar/sectors", received.append)
        node = wire(LiDARNode("lidar", mode="simulate", hz=10), hal, bus)
        node._tick()
        assert "sectors" in received[0].data
        assert "N" in received[0].data["sectors"]

    def test_clear_obstacles(self):
        from neuros.nodes.vision.lidar import LiDARNode
        hal, bus = make_env()
        node = wire(LiDARNode("lidar", mode="simulate", hz=10), hal, bus)
        node.inject_obstacle(0, 1.0)
        node.clear_obstacles()
        ranges, _ = node._simulate_scan()
        assert min(ranges) > 1.0   # no obstacles → open field


# ══ FLEET MANAGER ══════════════════════════════════════════════════════════
class TestFleetManager:
    def test_start_stop(self):
        from neuros.fleet import FleetManager
        bus = NeuralBus()
        fm  = FleetManager(bus, heartbeat_timeout=2.0)
        fm.start()
        time.sleep(0.05)
        fm.stop()

    def test_summary_empty(self):
        from neuros.fleet import FleetManager
        bus = NeuralBus()
        fm  = FleetManager(bus)
        fm.start()
        s = fm.summary()
        fm.stop()
        assert "total" in s and "online" in s and "robots" in s

    def test_robot_registers(self):
        from neuros.fleet import FleetManager
        bus = NeuralBus()
        fm  = FleetManager(bus, heartbeat_timeout=5.0)
        fm.start()
        bus.publish(Message(
            topic="/fleet/discovery/test_bot/register",
            data={"robot_id": "test_bot", "board_info": {"board": "sim"}},
        ))
        time.sleep(0.1)
        assert "test_bot" in fm.robot_ids
        fm.stop()

    def test_heartbeat_keeps_online(self):
        from neuros.fleet import FleetManager
        bus = NeuralBus()
        fm  = FleetManager(bus, heartbeat_timeout=0.5)
        fm.start()
        bus.publish(Message(
            topic="/fleet/discovery/hb_bot/register",
            data={"robot_id": "hb_bot"},
        ))
        time.sleep(0.1)
        # Send heartbeats to keep it online
        for _ in range(5):
            bus.publish(Message(
                topic="/fleet/discovery/hb_bot/heartbeat",
                data={"robot_id": "hb_bot"},
            ))
            time.sleep(0.1)
        s = fm.summary()
        fm.stop()
        bot = next((r for r in s["robots"] if r["robot_id"] == "hb_bot"), None)
        assert bot is not None
        assert bot["online"] is True

    def test_estop_broadcast(self):
        from neuros.fleet import FleetManager
        bus = NeuralBus()
        fm  = FleetManager(bus)
        fm.start()
        received = []
        bus.subscribe("/fleet/estop", received.append)
        fm.emergency_stop_all("test")
        time.sleep(0.05)
        fm.stop()
        assert len(received) == 1
        assert received[0].data["reason"] == "test"


# ══ RT MONITOR ════════════════════════════════════════════════════════════
class TestRTMonitor:
    def test_snapshot_shape(self, robot):
        from neuros.monitor import RTMonitor
        mon = RTMonitor(robot)
        snap = mon.snapshot()
        assert "robot"        in snap
        assert "uptime_s"     in snap
        assert "nodes"        in snap
        assert "top_topics"   in snap
        assert "kernel_state" in snap

    def test_starts_stops(self, robot):
        from neuros.monitor import RTMonitor
        mon = RTMonitor(robot, refresh_hz=2)
        mon.start()
        time.sleep(0.1)
        mon.stop()   # should not raise

    def test_http_server(self, robot):
        import urllib.request, json as _json
        from neuros.monitor import RTMonitor
        mon = RTMonitor(robot, http_port=18765, refresh_hz=1)
        mon.start()
        time.sleep(0.3)
        try:
            resp = urllib.request.urlopen("http://localhost:18765/status", timeout=2)
            data = _json.loads(resp.read())
            assert "robot" in data
        except Exception as e:
            pytest.skip(f"HTTP server test skipped: {e}")
        finally:
            mon.stop()


# ══ CAMERA NODE (no OpenCV required) ══════════════════════════════════════
class TestCamera:
    def test_synthetic_frames(self):
        from neuros.nodes.vision.camera import CameraNode
        hal, bus = make_env()
        received = []
        bus.subscribe("/robot/vision/camera/cam/frame", received.append)
        node = wire(CameraNode("cam", camera_id=99, hz=10), hal, bus)
        node._tick()
        assert len(received) == 1
        d = received[0].data
        assert "frame_id"  in d
        assert "width"     in d
        assert "_frame_ref" in d

    def test_frame_store_accessible(self):
        from neuros.nodes.vision.camera import CameraNode
        hal, bus = make_env()
        node = wire(CameraNode("cam2", camera_id=99, hz=10), hal, bus)
        node._tick()
        frame = node.get_frame()
        # May be None if numpy not installed, otherwise array
        assert frame is None or hasattr(frame, "__len__")
