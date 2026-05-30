"""
example_07_rl_training.py
==========================
NEUROS OS Phase 3 — Reinforcement Learning Sim-to-Real Pipeline

Demonstrates:
  1. Build a SimulatorHAL robot with full navigation stack
  2. Define a custom reward function
  3. Train a PPO policy (stub if stable-baselines3 not installed)
  4. Deploy trained policy back to the same (or real) robot
  5. Watch the policy run live via RTMonitor

Run:
    python examples/example_07_rl_training.py
    python examples/example_07_rl_training.py --steps 50000 --algo ppo
"""

import argparse, logging, time

parser = argparse.ArgumentParser(description="NEUROS Phase 3 — RL Training")
parser.add_argument("--steps",   type=int,   default=10_000)
parser.add_argument("--algo",    default="stub", choices=["stub","ppo","sac"])
parser.add_argument("--monitor", action="store_true")
parser.add_argument("--log",     default="INFO")
args = parser.parse_args()

logging.basicConfig(level=getattr(logging, args.log.upper(), logging.INFO),
                    format="%(asctime)s %(name)s %(message)s", datefmt="%H:%M:%S")

from neuros import Robot, spin, RTMonitor, RLEngine, RLPolicy
from neuros.safety import SafetySupervisor
from neuros.nodes  import EncoderNode, MotorNode, LEDNode
from neuros.nodes.vision     import LiDARNode
from neuros.nodes.navigation import OdometryNode

# ── Build simulation robot ────────────────────────────────────────────────────
print("  [1/5] Building simulation robot...")
sim_robot = Robot(name="rl_sim", board="simulator", kernel_hz=200)

sim_robot.add_node(SafetySupervisor(battery_crit_v=0.0))  # disable battery kill in sim
sim_robot.add_node(LiDARNode("lidar", mode="simulate", hz=10))
sim_robot.add_node(EncoderNode("enc_left",  pin_a=17, pin_b=27, hz=200))
sim_robot.add_node(EncoderNode("enc_right", pin_a=22, pin_b=10, hz=200))
sim_robot.add_node(OdometryNode("odom", wheel_base_m=0.15, hz=50))
sim_robot.add_node(MotorNode("motor_left",  pin_en=12, pin_in1=23, pin_in2=24))
sim_robot.add_node(MotorNode("motor_right", pin_en=13, pin_in1=25, pin_in2=8))
sim_robot.add_node(LEDNode("status_led", pin=4, mode="digital"))

sim_robot.start()

# Inject a few obstacles into the sim world
lidar = next((n for n in sim_robot._nodes.values() if n.name == "lidar"), None)
if lidar:
    lidar.inject_obstacle(angle_deg=0,   distance_m=3.0)
    lidar.inject_obstacle(angle_deg=45,  distance_m=2.0)
    lidar.inject_obstacle(angle_deg=315, distance_m=2.5)

# Velocity bridge
def on_vel(msg):
    v, w = float(msg.data.get("linear",0)), float(msg.data.get("angular",0))
    WB = 0.15
    l, r = v - w*WB/2, v + w*WB/2
    m = max(abs(l), abs(r), 0.001)
    if m > 0.5: l, r = l/m*0.5, r/m*0.5
    sim_robot.publish("cmd/motor/motor_left",  {"speed": l/0.5})
    sim_robot.publish("cmd/motor/motor_right", {"speed": r/0.5})
sim_robot.subscribe("/robot/cmd/velocity", on_vel)

print("  [2/5] Simulation robot ready")

# ── Custom reward function ────────────────────────────────────────────────────
def navigation_reward(obs_before, action, obs_after):
    """
    Reward:
      +  Forward speed (encourage movement)
      -  Proximity to obstacles (avoid collisions)
      -  Spinning in place (penalise excessive rotation)
    """
    linear  = float(action[0]) if len(action) > 0 else 0.0
    angular = abs(float(action[1])) if len(action) > 1 else 0.0

    reward = linear * 1.0          # forward progress
    reward -= angular * 0.1        # slight penalty for turning

    # Obstacle proximity penalty (LiDAR sectors are indices 8–15)
    lidar_start = 8
    for i in range(lidar_start, min(lidar_start + 8, len(obs_after))):
        d = obs_after[i]
        if d < 0.5:
            reward -= (0.5 - d) * 8.0
        elif d < 1.0:
            reward -= (1.0 - d) * 1.0

    return float(reward)

# ── RL Engine ─────────────────────────────────────────────────────────────────
print(f"  [3/5] Initialising RL Engine (algo={args.algo}, steps={args.steps})...")
engine = RLEngine(sim_robot, algorithm=args.algo,
                  policy_name="navigation_v1",
                  reward_fn=navigation_reward)

# ── Training ──────────────────────────────────────────────────────────────────
print(f"  [4/5] Training for {args.steps} steps...")
t0     = time.monotonic()
policy = engine.train(total_steps=args.steps, save_path="")
elapsed = time.monotonic() - t0
print(f"  [4/5] Training complete in {elapsed:.1f}s")
print(f"        Policy: {policy.name} | algo={policy.algorithm} | "
      f"infer_count={policy.infer_count}")

# ── Deploy ────────────────────────────────────────────────────────────────────
print("  [5/5] Deploying policy to robot...")
engine.deploy(sim_robot)

if args.monitor:
    RTMonitor(sim_robot, refresh_hz=2, compact=True).start()

print(f"""
╔══════════════════════════════════════════════════════╗
║  NEUROS Phase 3 — RL Policy Deployed                 ║
║  Algorithm : {policy.algorithm:<10}  Steps: {args.steps}           ║
║  Policy node is now controlling the robot            ║
║  Press Ctrl+C to stop                               ║
╚══════════════════════════════════════════════════════╝
""")

spin(sim_robot)
