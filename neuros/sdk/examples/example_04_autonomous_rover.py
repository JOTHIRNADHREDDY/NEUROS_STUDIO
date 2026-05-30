"""
example_04_autonomous_rover.py
================================
NEUROS OS Phase 2 — Autonomous Rover (Domain B)

Full autonomous rover with:
  • Raspberry Pi HAL (or simulator fallback)
  • LiDAR obstacle detection (simulated)
  • Encoder-based odometry
  • Waypoint navigation with pure-pursuit
  • Fleet agent (reports to coordinator)
  • RT Monitor (live terminal dashboard)
  • ROS2 Bridge (no-op if ROS2 not installed)

Hardware (optional — falls back to simulator)
----------------------------------------------
  Raspberry Pi 4B
  RPLiDAR A1 on /dev/ttyUSB0
  L298N motor driver  (left: EN=12,IN1=23,IN2=24  right: EN=13,IN1=25,IN2=8)
  Quadrature encoders (left: A=17,B=27   right: A=22,B=10)
  MPU6050 IMU (I2C 0x68)
  12V 2S LiPo

Run:
    python examples/example_04_autonomous_rover.py
    python examples/example_04_autonomous_rover.py --board rpi
    python examples/example_04_autonomous_rover.py --waypoints "1,0 2,1 0,0"
"""

import argparse
import logging
import sys

# ── Args ────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="NEUROS Phase 2 — Autonomous Rover")
parser.add_argument("--board",     default="simulator",      help="Board type")
parser.add_argument("--port",      default="/dev/ttyUSB0",   help="Serial/LiDAR port")
parser.add_argument("--waypoints", default="1.0,0.0 2.0,1.0 0.0,0.0",
                    help="Waypoints as 'x,y x,y ...'")
parser.add_argument("--monitor",   action="store_true",      help="Enable terminal monitor")
parser.add_argument("--http-port", type=int, default=0,      help="HTTP monitor port")
parser.add_argument("--log",       default="INFO")
args = parser.parse_args()

# ── NEUROS imports ──────────────────────────────────────────────────────────
from neuros import Robot, spin, RTMonitor, FleetAgent
from neuros.safety import SafetySupervisor
from neuros.nodes import (
    IMUNode, EncoderNode, BatteryMonitorNode,
    MotorNode, LEDNode, BuzzerNode,
)
from neuros.nodes.vision      import LiDARNode
from neuros.nodes.navigation  import (
    OdometryNode, ObstacleAvoidanceNode, WaypointNavigatorNode,
)
from neuros.bridge.ros2 import ROS2Bridge

log = logging.getLogger("rover_example")

# ── Parse waypoints ─────────────────────────────────────────────────────────
waypoints = []
for wp_str in args.waypoints.split():
    try:
        x, y = [float(v) for v in wp_str.split(",")]
        waypoints.append((x, y))
    except ValueError:
        pass

# ── Build robot ─────────────────────────────────────────────────────────────
robot = Robot(
    name      = "rover",
    board     = args.board,
    port      = args.port,
    kernel_hz = 1000,
    log_level = getattr(logging, args.log.upper(), logging.INFO),
)

# 1. Safety — always first
robot.add_node(SafetySupervisor(battery_crit_v=6.4))

# 2. Sensors
robot.add_node(IMUNode("imu", hz=100))
robot.add_node(LiDARNode("lidar", port=args.port, mode="simulate", hz=10))
robot.add_node(EncoderNode(
    "enc_left",  pin_a=17, pin_b=27, ticks_per_rev=360, wheel_dia_m=0.065, hz=500,
))
robot.add_node(EncoderNode(
    "enc_right", pin_a=22, pin_b=10, ticks_per_rev=360, wheel_dia_m=0.065, hz=500,
))
robot.add_node(BatteryMonitorNode(
    "battery", pin=26, profile="lipo_2s", divider_ratio=4.0, hz=0.5,
))

# 3. Navigation stack
robot.add_node(OdometryNode(
    "odom", wheel_base_m=0.15,
    enc_left_topic  = "/robot/sensor/encoder/enc_left",
    enc_right_topic = "/robot/sensor/encoder/enc_right",
    imu_topic       = "/robot/sensor/imu/gyro",
    hz=50,
))
robot.add_node(ObstacleAvoidanceNode(
    "obstacle_avoidance",
    lidar_name    = "lidar",
    cruise_speed  = 0.3,
    stop_dist_m   = 0.25,
    caution_dist_m= 1.0,
    hz=20,
))
nav = WaypointNavigatorNode(
    "waypoint_nav",
    max_linear_speed  = 0.4,
    goal_tolerance_m  = 0.12,
    hz=20,
)
robot.add_node(nav)

# 4. Actuators
robot.add_node(MotorNode("motor_left",  pin_en=12, pin_in1=23, pin_in2=24, hz=100))
robot.add_node(MotorNode("motor_right", pin_en=13, pin_in1=25, pin_in2=8,  hz=100))
robot.add_node(LEDNode("status_led", pin=4,  mode="pwm"))
robot.add_node(BuzzerNode("buzzer",   pin=18, passive=False))

# 5. Fleet agent
robot.add_node(FleetAgent(robot, robot_id="rover_01", hz=1))

# ── Differential-drive velocity → motor commands ────────────────────────────
WHEEL_BASE = 0.15

def on_velocity(msg) -> None:
    v = float(msg.data.get("linear",  0.0))
    w = float(msg.data.get("angular", 0.0))
    left_v  = v - (w * WHEEL_BASE / 2.0)
    right_v = v + (w * WHEEL_BASE / 2.0)
    max_v   = max(abs(left_v), abs(right_v), 0.001)
    if max_v > 0.5:
        left_v  /= max_v / 0.5
        right_v /= max_v / 0.5
    robot.publish("cmd/motor/motor_left",  {"speed": left_v  / 0.5})
    robot.publish("cmd/motor/motor_right", {"speed": right_v / 0.5})

robot.subscribe("/robot/cmd/velocity", on_velocity)

# ── Start ────────────────────────────────────────────────────────────────────
robot.start()

# Inject simulated LiDAR obstacles for demo
lidar_node = next(
    (n for n in robot._nodes.values() if n.name == "lidar"), None
)
if lidar_node and hasattr(lidar_node, "inject_obstacle"):
    lidar_node.inject_obstacle(angle_deg=0,   distance_m=2.5)
    lidar_node.inject_obstacle(angle_deg=315, distance_m=1.8)

# ROS2 bridge (no-op if ROS2 not installed)
ros2_bridge = ROS2Bridge(robot)
ros2_bridge.mirror_topic("/cmd_vel", direction="neuros→ros2",
                          neuros_topic="/robot/cmd/velocity")
ros2_bridge.mirror_topic("/scan",    direction="ros2→neuros",
                          neuros_topic="/robot/sensor/lidar/lidar/scan")
ros2_bridge.start()

# Load waypoints into navigator
for x, y in waypoints:
    nav.add_waypoint(x, y)

# Startup effects
robot.publish("cmd/buzzer/buzzer",   {"pattern": "startup"})
robot.publish("cmd/led/status_led",  {"pattern": "pulse", "hz": 2})

# Monitor
if args.monitor or args.http_port > 0:
    mon = RTMonitor(robot, refresh_hz=2, http_port=args.http_port, compact=True)
    mon.start()

print(f"""
╔══════════════════════════════════════════════════════════════╗
║  NEUROS OS Phase 2 — Autonomous Rover                        ║
║  Board    : {args.board:<18}  Domain: B              ║
║  Waypoints: {len(waypoints):<3} loaded                                  ║
║  ROS2     : {'active' if ros2_bridge._available else 'no-op (ROS2 not installed)'}
║  Press Ctrl+C to stop                                       ║
╚══════════════════════════════════════════════════════════════╝
""")

# Status printer
@robot.every(hz=0.5, name="status_print")
def print_status():
    state  = robot._kernel.state.value
    n_node = robot._kernel.node_count
    nav_st = nav.state
    odom_node = next((n for n in robot._nodes.values() if n.name == "odom"), None)
    pose_str  = ""
    if odom_node and hasattr(odom_node, "x"):
        import math
        pose_str = f"  pose=({odom_node.x:.2f},{odom_node.y:.2f},{math.degrees(odom_node.theta):.0f}°)"
    print(f"  {state}  nodes={n_node}  nav={nav_st}  wpts_left={nav.queue_length}{pose_str}")

spin(robot)
