"""
neuros.nodes.actuator.servo
============================
Hobby servo node — PWM position control.

Standard hobby servo timing
-----------------------------
  Period:     20 ms (50 Hz)
  Pulse min:  0.5 ms → 0°   (duty = 2.5%)
  Pulse mid:  1.5 ms → 90°  (duty = 7.5%)
  Pulse max:  2.5 ms → 180° (duty = 12.5%)

Subscribed topic: /robot/cmd/servo/<name>
  {"angle_deg": 0–180}  or  {"duty": 0.0–1.0}

Published topic: /robot/actuator/servo/<name>
  {"angle_deg": float, "duty": float}
"""
from __future__ import annotations
import logging
from neuros.nodes.base import Node, NodePriority
from neuros.hal.base   import PinMode

logger = logging.getLogger("neuros.nodes.actuator.servo")

_SERVO_HZ       = 50.0
_DUTY_MIN       = 0.025   # 0.5ms / 20ms
_DUTY_MAX       = 0.125   # 2.5ms / 20ms
_DUTY_MID       = 0.075   # 1.5ms / 20ms


class ServoNode(Node):
    """
    Hobby servo position controller.

    Parameters
    ----------
    name        : node identifier (e.g. "pan", "tilt", "arm_shoulder")
    pin         : PWM output pin
    angle_min   : minimum physical angle (default 0°)
    angle_max   : maximum physical angle (default 180°)
    angle_init  : startup angle (default 90°)
    duty_min    : PWM duty at min angle (override for non-standard servos)
    duty_max    : PWM duty at max angle

    Example
    -------
        pan  = ServoNode("pan",  pin=9,  angle_min=0, angle_max=180, angle_init=90)
        tilt = ServoNode("tilt", pin=10, angle_min=30, angle_max=150)
        robot.add_node(pan)
        robot.add_node(tilt)

        # Rotate pan to 45°
        robot.publish("cmd/servo/pan", {"angle_deg": 45})
    """

    def __init__(
        self,
        name:       str,
        *,
        pin:        int,
        angle_min:  float        = 0.0,
        angle_max:  float        = 180.0,
        angle_init: float        = 90.0,
        duty_min:   float        = _DUTY_MIN,
        duty_max:   float        = _DUTY_MAX,
        hz:         float        = 50.0,
        priority:   NodePriority = NodePriority.NORMAL,
    ) -> None:
        super().__init__(name, hz=hz, priority=priority)
        self._pin        = pin
        self._angle_min  = angle_min
        self._angle_max  = angle_max
        self._duty_min   = duty_min
        self._duty_max   = duty_max
        self._target_deg = max(angle_min, min(angle_max, angle_init))
        self.angle_deg   = self._target_deg

    def configure(self) -> None:
        self.hal.pin(self.name, board_pin=self._pin, mode=PinMode.PWM)
        self._write_angle(self._target_deg)
        logger.info("[SERVO] '%s' pin=%d range=[%.0f°–%.0f°] init=%.0f°",
                    self.name, self._pin, self._angle_min, self._angle_max, self._target_deg)

    def on_activate(self) -> None:
        self.subscribe(f"/robot/cmd/servo/{self.name}", self._on_cmd)

    def _on_cmd(self, msg) -> None:
        if "angle_deg" in msg.data:
            deg = float(msg.data["angle_deg"])
            self._target_deg = max(self._angle_min, min(self._angle_max, deg))
        elif "duty" in msg.data:
            duty = float(msg.data["duty"])
            # Back-convert duty → angle for logging
            self._target_deg = self._duty_to_angle(duty)

    def tick(self) -> None:
        self._write_angle(self._target_deg)
        self.publish(f"/robot/actuator/servo/{self.name}", {
            "angle_deg": round(self.angle_deg, 2),
            "duty":      round(self._angle_to_duty(self.angle_deg), 4),
        })

    def _angle_to_duty(self, deg: float) -> float:
        t = (deg - self._angle_min) / (self._angle_max - self._angle_min)
        return self._duty_min + t * (self._duty_max - self._duty_min)

    def _duty_to_angle(self, duty: float) -> float:
        t = (duty - self._duty_min) / (self._duty_max - self._duty_min)
        return self._angle_min + t * (self._angle_max - self._angle_min)

    def _write_angle(self, deg: float) -> None:
        self.angle_deg = deg
        duty = self._angle_to_duty(deg)
        self.hal.pwm_write(self._pin, duty, freq_hz=_SERVO_HZ)

    def destroy(self) -> None:
        # Return to centre on shutdown
        self._write_angle((self._angle_min + self._angle_max) / 2.0)
        super().destroy()
