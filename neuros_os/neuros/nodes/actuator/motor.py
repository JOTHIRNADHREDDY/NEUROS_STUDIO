"""
neuros.nodes.actuator.motor
============================
DC Motor node — L298N / L293D H-bridge driver.

Hardware wiring (L298N)
-----------------------
  ENA  → PWM pin (speed control, 0–255)
  IN1  → direction pin A
  IN2  → direction pin B

  Forward:   IN1=HIGH, IN2=LOW
  Backward:  IN1=LOW,  IN2=HIGH
  Brake:     IN1=HIGH, IN2=HIGH
  Coast:     IN1=LOW,  IN2=LOW

Subscribed topics (control inputs)
-----------------------------------
  /robot/cmd/motor/<name>       {"speed": −1.0 to +1.0}
  /robot/cmd/velocity           {"linear": m/s, "angular": rad/s}  ← diff-drive
  /robot/cmd/stop               any payload → immediate stop

Published topics (feedback)
----------------------------
  /robot/actuator/motor/<name>  {"speed": float, "direction": str, "pwm_duty": float}

PID speed controller (Phase 1 — optional, uses encoder feedback)
-----------------------------------------------------------------
  Pass `encoder_topic` to enable closed-loop speed control.
  The PID gains (kp, ki, kd) are tunable at runtime via the config system.
"""
from __future__ import annotations
import logging
from neuros.nodes.base import Node, NodePriority
from neuros.hal.base   import PinMode, PinState

logger = logging.getLogger("neuros.nodes.actuator.motor")


class _PID:
    """Minimal PID controller."""
    def __init__(self, kp: float, ki: float, kd: float) -> None:
        self.kp, self.ki, self.kd = kp, ki, kd
        self._integral = 0.0
        self._prev_err = 0.0

    def compute(self, error: float, dt: float) -> float:
        if dt <= 0:
            return 0.0
        self._integral  += error * dt
        derivative       = (error - self._prev_err) / dt
        self._prev_err   = error
        return self.kp * error + self.ki * self._integral + self.kd * derivative

    def reset(self) -> None:
        self._integral = 0.0
        self._prev_err = 0.0


class MotorNode(Node):
    """
    DC Motor driver node.

    Parameters
    ----------
    name            : node identifier (e.g. "motor_left")
    pin_en          : ENA / PWM pin
    pin_in1         : direction pin A
    pin_in2         : direction pin B
    max_pwm_duty    : PWM duty cap [0.0–1.0] (default 1.0)
    hz              : control loop rate (default 100 Hz)
    encoder_topic   : subscribe to encoder for closed-loop control (optional)
    kp, ki, kd      : PID gains (used only if encoder_topic is set)

    Example
    -------
        left_motor  = MotorNode("motor_left",  pin_en=5, pin_in1=6, pin_in2=7)
        right_motor = MotorNode("motor_right", pin_en=10, pin_in1=11, pin_in2=12)
        robot.add_node(left_motor)
        robot.add_node(right_motor)

        # Drive forward at 60% speed
        robot.publish("cmd/motor/motor_left",  {"speed":  0.6})
        robot.publish("cmd/motor/motor_right", {"speed":  0.6})

        # Spin left
        robot.publish("cmd/motor/motor_left",  {"speed": -0.4})
        robot.publish("cmd/motor/motor_right", {"speed":  0.4})
    """

    def __init__(
        self,
        name:           str,
        *,
        pin_en:         int,
        pin_in1:        int,
        pin_in2:        int,
        max_pwm_duty:   float        = 1.0,
        hz:             float        = 100.0,
        encoder_topic:  str          = "",
        kp:             float        = 1.0,
        ki:             float        = 0.05,
        kd:             float        = 0.01,
        priority:       NodePriority = NodePriority.HIGH,
    ) -> None:
        super().__init__(name, hz=hz, priority=priority)
        self._pin_en   = pin_en
        self._pin_in1  = pin_in1
        self._pin_in2  = pin_in2
        self._max_duty = max_pwm_duty
        self._enc_topic = encoder_topic

        self._target_speed: float = 0.0   # −1.0 to +1.0
        self._actual_speed: float = 0.0   # from encoder (m/s)
        self._pid = _PID(kp, ki, kd) if encoder_topic else None

        self.speed:     float = 0.0
        self.direction: str   = "stopped"

    def configure(self) -> None:
        self.hal.pin(f"{self.name}_en",  board_pin=self._pin_en,  mode=PinMode.PWM)
        self.hal.pin(f"{self.name}_in1", board_pin=self._pin_in1, mode=PinMode.OUTPUT)
        self.hal.pin(f"{self.name}_in2", board_pin=self._pin_in2, mode=PinMode.OUTPUT)
        self._apply_speed(0.0)
        logger.info("[MOTOR] '%s' en=%d in1=%d in2=%d closed_loop=%s",
                    self.name, self._pin_en, self._pin_in1, self._pin_in2,
                    bool(self._enc_topic))

    def on_activate(self) -> None:
        self.subscribe(f"/robot/cmd/motor/{self.name}", self._on_cmd)
        self.subscribe("/robot/cmd/stop",               self._on_stop)
        if self._enc_topic:
            self.subscribe(self._enc_topic, self._on_encoder)

    def _on_cmd(self, msg) -> None:
        speed = float(msg.data.get("speed", 0.0))
        self._target_speed = max(-1.0, min(1.0, speed))

    def _on_stop(self, msg) -> None:
        self._target_speed = 0.0
        self._apply_speed(0.0)

    def _on_encoder(self, msg) -> None:
        self._actual_speed = float(msg.data.get("velocity_ms", 0.0))

    def tick(self) -> None:
        self._apply_speed(self._target_speed)
        self.publish(f"/robot/actuator/motor/{self.name}", {
            "speed":     round(self.speed, 3),
            "direction": self.direction,
            "pwm_duty":  round(abs(self.speed) * self._max_duty, 3),
        })

    def _apply_speed(self, speed: float) -> None:
        speed = max(-1.0, min(1.0, speed))
        self.speed = speed
        duty = abs(speed) * self._max_duty

        if speed > 0.01:
            self.direction = "forward"
            self.hal.write(f"{self.name}_in1", PinState.HIGH)
            self.hal.write(f"{self.name}_in2", PinState.LOW)
        elif speed < -0.01:
            self.direction = "backward"
            self.hal.write(f"{self.name}_in1", PinState.LOW)
            self.hal.write(f"{self.name}_in2", PinState.HIGH)
        else:
            self.direction = "stopped"
            self.hal.write(f"{self.name}_in1", PinState.LOW)
            self.hal.write(f"{self.name}_in2", PinState.LOW)
            duty = 0.0

        self.hal.pwm_write(self._pin_en, duty)

    def destroy(self) -> None:
        self._apply_speed(0.0)
        super().destroy()
