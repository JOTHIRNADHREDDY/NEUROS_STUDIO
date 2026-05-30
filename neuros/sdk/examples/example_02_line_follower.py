"""
example_02_line_follower.py
============================
NEUROS OS — Example 2: Line-Following Robot

A complete 2-wheel differential drive robot that follows a black line
using 5 IR sensors and a PID controller.

Hardware needed (real robot)
-----------------------------
  2× DC motors          : L298N H-bridge
  5× IR sensors         : TCRT5000 or QTR-5RC array
  1× Arduino Uno / Mega : main controller

Simulator mode
--------------
  Run without any hardware — the SimulatorHAL provides fake sensor data.
  Inject a line sensor pattern to test the PID:
      # centre sensor sees line → error ≈ 0 → straight
      sim_hal.inject_sensor("line_2_analog", 0.0)   # sensor 2 sees white
      # or inject offset line → robot turns to correct

Architecture
------------
  IMUNode         → /robot/sensor/imu/*
  LineFollowerNode → /robot/sensor/line/*
  EncoderNode (×2) → /robot/sensor/encoder/*
  BatteryMonitorNode → /robot/sensor/battery
  ─────────────────────────────────────────
  PIDControllerNode  → /robot/cmd/motor/*
  ─────────────────────────────────────────
  MotorNode (left)   ← /robot/cmd/motor/motor_left
  MotorNode (right)  ← /robot/cmd/motor/motor_right
  LEDNode (status)   ← /robot/cmd/led/status
  BuzzerNode         ← /robot/cmd/buzzer/buzzer
  SafetySupervisor   ← /robot/sensor/battery, /robot/cmd/estop

Run:
    python examples/example_02_line_follower.py
"""

import sys, argparse, logging

parser = argparse.ArgumentParser()
parser.add_argument("--board",   default="simulator")
parser.add_argument("--port",    default="/dev/ttyUSB0")
parser.add_argument("--log",     default="INFO")
parser.add_argument("--base-speed", type=float, default=0.5,
                    help="Base motor speed (0.0–1.0)")
args = parser.parse_args()

# ── NEUROS imports ──────────────────────────────────────────────────────────
from neuros import Robot, spin
from neuros.nodes import (
    LineFollowerNode, MotorNode, LEDNode, BuzzerNode,
    EncoderNode, BatteryMonitorNode, Node, NodePriority,
)
from neuros.safety import SafetySupervisor

log = logging.getLogger("line_follower_example")


# ── PID Controller Node ─────────────────────────────────────────────────────
class PIDControllerNode(Node):
    """
    Reads line error, applies PID, commands motors.

    Subscribed: /robot/sensor/line/error
    Published:  /robot/cmd/motor/motor_left
                /robot/cmd/motor/motor_right
    """

    def __init__(
        self,
        base_speed: float = 0.5,
        kp: float = 0.4,
        ki: float = 0.002,
        kd: float = 0.05,
    ) -> None:
        super().__init__("pid_controller", hz=100, priority=NodePriority.HIGH)
        self.base_speed = base_speed
        self.kp, self.ki, self.kd = kp, ki, kd
        self._error     = 0.0
        self._integral  = 0.0
        self._prev_err  = 0.0
        self._detected  = False

    def configure(self) -> None:
        log.info("[PID] configured kp=%.2f ki=%.4f kd=%.3f base=%.2f",
                 self.kp, self.ki, self.kd, self.base_speed)

    def on_activate(self) -> None:
        self.subscribe("/robot/sensor/line/error",    self._on_error)
        self.subscribe("/robot/sensor/line/detected", self._on_detected)

    def _on_error(self, msg) -> None:
        err = msg.data.get("error")
        if err is not None:
            self._error    = float(err)
            self._detected = True
        else:
            self._detected = False

    def _on_detected(self, msg) -> None:
        self._detected = bool(msg.data.get("detected", False))

    def tick(self) -> None:
        if not self._detected:
            # Line lost — slow rotate to search
            self.publish("/robot/cmd/motor/motor_left",  {"speed":  0.2})
            self.publish("/robot/cmd/motor/motor_right", {"speed": -0.2})
            return

        # PID
        dt         = 1.0 / self.hz
        self._integral  += self._error * dt
        derivative       = (self._error - self._prev_err) / dt
        correction       = (self.kp * self._error +
                            self.ki * self._integral +
                            self.kd * derivative)
        self._prev_err   = self._error

        left_speed  = max(-1.0, min(1.0, self.base_speed + correction))
        right_speed = max(-1.0, min(1.0, self.base_speed - correction))

        self.publish("/robot/cmd/motor/motor_left",  {"speed": left_speed})
        self.publish("/robot/cmd/motor/motor_right", {"speed": right_speed})

        self.publish("/robot/system/pid_debug", {
            "error":      round(self._error, 4),
            "correction": round(correction,   4),
            "left":       round(left_speed,   3),
            "right":      round(right_speed,  3),
        })


# ── Build the robot ─────────────────────────────────────────────────────────
robot = Robot(
    name  = "line_follower",
    board = args.board,
    port  = args.port,
    log_level = getattr(logging, args.log.upper(), logging.INFO),
)

# Safety first
robot.add_node(SafetySupervisor(battery_crit_v=3.2))

# Sensors
robot.add_node(LineFollowerNode(
    "line",
    pins   = [14, 15, 16, 17, 18],   # analog pins A0–A4
    analog = True,
    invert = True,
    hz     = 100,
))
robot.add_node(EncoderNode(
    "enc_left",  pin_a=2, pin_b=3, ticks_per_rev=360, wheel_dia_m=0.065, hz=500,
))
robot.add_node(EncoderNode(
    "enc_right", pin_a=4, pin_b=5, ticks_per_rev=360, wheel_dia_m=0.065, hz=500,
))
robot.add_node(BatteryMonitorNode(
    "battery", pin=19, profile="lipo_2s", divider_ratio=4.0, hz=0.5,
))

# Control
robot.add_node(PIDControllerNode(base_speed=args.base_speed))

# Actuators
robot.add_node(MotorNode("motor_left",  pin_en=5,  pin_in1=6,  pin_in2=7))
robot.add_node(MotorNode("motor_right", pin_en=10, pin_in1=11, pin_in2=12))
robot.add_node(LEDNode("status",  pin=13, mode="pwm"))
robot.add_node(BuzzerNode("buzzer", pin=8, passive=False))

robot.start()

# Play startup sound
robot.publish("cmd/buzzer/buzzer", {"pattern": "startup"})
robot.publish("cmd/led/status",   {"pattern": "pulse", "hz": 1})

print("""
╔══════════════════════════════════════════════════════╗
║  NEUROS OS — Example 2: Line Follower Robot          ║
║  Nodes : Safety + 5 sensors + PID + 2 motors + LED  ║
║  Press Ctrl+C to stop                               ║
╚══════════════════════════════════════════════════════╝
""")

# Print live status every second
@robot.every(hz=1, name="status_printer")
def print_status():
    status = robot.status()
    n_active = sum(1 for v in status["nodes"].values() if v.get("alive"))
    print(f"  uptime={status['uptime_s']:.1f}s | nodes_alive={n_active}"
          f" | estop={not robot._kernel.state.value == 'RUNNING'}")

spin(robot)
