"""
example_05_fleet.py
====================
NEUROS OS Phase 2 — Fleet Coordination

Demonstrates coordinating two robots from a FleetManager:
  • Robot A (rover_a) patrols zone 1
  • Robot B (rover_b) patrols zone 2
  • Coordinator assigns tasks, monitors health, can E-stop all

Each robot runs in a separate thread (simulating separate processes/machines).
In production, each robot would be on its own hardware connected via Zenoh.

Run:
    python examples/example_05_fleet.py
"""

import logging
import threading
import time

from neuros import Robot, FleetManager, FleetAgent, NeuralBus, spin
from neuros.nodes.navigation import WaypointNavigatorNode, OdometryNode
from neuros.nodes import LEDNode, MotorNode, EncoderNode
from neuros.safety import SafetySupervisor

log = logging.getLogger("fleet_example")
logging.basicConfig(level=logging.WARNING,
                    format="%(asctime)s  %(name)s  %(message)s",
                    datefmt="%H:%M:%S")

# ── Shared bus (in production this would be Zenoh across machines) ──────────
shared_bus = NeuralBus()


def build_robot(robot_id: str, zone_waypoints: list) -> Robot:
    """Factory: build a rover robot with navigation and fleet agent."""
    robot = Robot(name=robot_id, board="simulator", kernel_hz=200)

    # Internals: share the bus so FleetManager sees all robots
    # In real multi-machine deployment each robot has its own bus + Zenoh bridge
    robot._bus = shared_bus

    robot.add_node(SafetySupervisor(battery_crit_v=3.0))

    enc_l = EncoderNode("enc_left",  pin_a=17, pin_b=27,
                        ticks_per_rev=360, wheel_dia_m=0.065, hz=200)
    enc_r = EncoderNode("enc_right", pin_a=22, pin_b=10,
                        ticks_per_rev=360, wheel_dia_m=0.065, hz=200)
    robot.add_node(enc_l)
    robot.add_node(enc_r)

    robot.add_node(OdometryNode(
        "odom", wheel_base_m=0.15,
        enc_left_topic  = f"/robot/sensor/encoder/enc_left",
        enc_right_topic = f"/robot/sensor/encoder/enc_right",
        hz=50,
    ))

    nav = WaypointNavigatorNode("nav", max_linear_speed=0.3, hz=10)
    robot.add_node(nav)

    robot.add_node(MotorNode("motor_l", pin_en=5,  pin_in1=6,  pin_in2=7))
    robot.add_node(MotorNode("motor_r", pin_en=10, pin_in1=11, pin_in2=12))
    robot.add_node(LEDNode("led", pin=13, mode="digital"))

    # Fleet agent
    agent = FleetAgent(robot, robot_id=robot_id, hz=1)
    robot.add_node(agent)

    # Handle tasks from coordinator
    def on_task(task: dict) -> None:
        mission = task.get("mission", "")
        log.warning("[%s] received task: %s", robot_id, mission)
        if mission == "goto_home":
            nav.add_waypoint(0.0, 0.0)
        elif mission.startswith("waypoint:"):
            parts = mission.split(":")[1].split(",")
            nav.add_waypoint(float(parts[0]), float(parts[1]))
        robot._bus.publish(
            __import__("neuros.bus.message", fromlist=["Message"]).Message(
                topic=f"/fleet/{robot_id}/status",
                data={"robot_id": robot_id, "mission": mission, "state": "executing"},
            )
        )

    agent.on_task_received(on_task)

    robot.start()

    # Pre-load patrol waypoints
    for x, y in zone_waypoints:
        nav.add_waypoint(x, y)

    return robot


# ── Build two robots ─────────────────────────────────────────────────────────
ZONE_A = [(1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0)]   # square patrol
ZONE_B = [(2.0, 0.0), (3.0, 0.0), (3.0, 1.0), (2.0, 0.0)]   # triangle patrol

robot_a = build_robot("rover_a", ZONE_A)
robot_b = build_robot("rover_b", ZONE_B)

# ── Fleet coordinator ────────────────────────────────────────────────────────
fleet = FleetManager(shared_bus, heartbeat_timeout=3.0)
fleet.start()

print("""
╔════════════════════════════════════════════════════════╗
║  NEUROS OS Phase 2 — Fleet Coordination Demo          ║
║  Robots: rover_a (Zone A patrol) + rover_b (Zone B)   ║
║  Coordinator monitors + assigns tasks                 ║
║  Press Ctrl+C to stop                                 ║
╚════════════════════════════════════════════════════════╝
""")

# Wait for robots to register
time.sleep(2.0)

def coordinator_loop():
    """Demo: print fleet summary and send tasks periodically."""
    cycle = 0
    while True:
        time.sleep(5)
        cycle += 1
        summary = fleet.summary()
        print(f"\n  [FLEET] summary cycle={cycle} "
              f"online={summary['online']}/{summary['total']}")
        for r in summary["robots"]:
            print(f"    {r['robot_id']:12} online={r['online']}  "
                  f"tasks={r['tasks_assigned']}")

        # Occasionally send a task
        if cycle % 3 == 0:
            fleet.assign_task("rover_a", {"mission": "goto_home"})
            print("  [FLEET] sent rover_a → goto_home")

        # Demo E-stop at cycle 10
        if cycle == 10:
            print("\n  [FLEET] *** DEMO: Fleet-wide E-stop ***")
            fleet.emergency_stop_all("demo e-stop")
            time.sleep(2)
            break

# Run coordinator demo in background
coord_thread = threading.Thread(target=coordinator_loop, daemon=True)
coord_thread.start()

# Spin both robots (blocking in main thread on robot_a)
thread_b = threading.Thread(target=lambda: spin(robot_b), daemon=True)
thread_b.start()
spin(robot_a)
