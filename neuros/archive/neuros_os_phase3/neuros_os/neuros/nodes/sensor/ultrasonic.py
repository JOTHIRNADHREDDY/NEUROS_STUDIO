"""
neuros.nodes.sensor.ultrasonic
================================
HC-SR04 (and compatible) ultrasonic distance sensor node.

Hardware
--------
  Trigger pin → GPIO output pulse (10µs)
  Echo pin    → GPIO input, measures pulse width → distance

Physics: distance_cm = pulse_duration_µs / 58.0

Published topic: /robot/sensor/ultrasonic/<name>
Payload: {"distance_cm": <float>, "distance_m": <float>, "valid": <bool>}

Constraints
-----------
  Range:      2 cm – 400 cm
  Dead zone:  < 2 cm reads as 0 / invalid
  Max range:  > 400 cm reads as inf / invalid
  Beam angle: ~15° cone

Phase 1 (Simulator): injects a configurable distance profile.
Phase 1 (Arduino):   trigger/echo via ArduinoHAL. The Arduino firmware
                      measures echo pulse width in µs and returns it via NSP.

Phase 2 will add: LIDAR-Lite, VL53L1X (I2C ToF), TFMini-Plus (UART).
"""

from __future__ import annotations

import logging
import math
from neuros.nodes.base import Node, NodePriority
from neuros.hal.base   import PinMode, PinState

logger = logging.getLogger("neuros.nodes.sensor.ultrasonic")

_RANGE_MIN_CM = 2.0
_RANGE_MAX_CM = 400.0


class UltrasonicNode(Node):
    """
    HC-SR04 ultrasonic distance sensor.

    Parameters
    ----------
    name        : node identifier
    trig_pin    : board pin number for TRIG output
    echo_pin    : board pin number for ECHO input
    hz          : polling rate (default 10 Hz — HC-SR04 needs ≥50ms between reads)
    max_retries : number of consecutive invalid reads before publishing 'invalid'
    topic       : override publish topic

    Example
    -------
        sonar = UltrasonicNode("front_sonar", trig_pin=4, echo_pin=5, hz=10)
        robot.add_node(sonar)
    """

    def __init__(
        self,
        name:       str,
        *,
        trig_pin:   int,
        echo_pin:   int,
        hz:         float        = 10.0,
        max_retries: int         = 3,
        topic:      str          = "",
        priority:   NodePriority = NodePriority.NORMAL,
    ) -> None:
        super().__init__(name, hz=hz, priority=priority)
        self._trig   = trig_pin
        self._echo   = echo_pin
        self._topic  = topic or f"/robot/sensor/ultrasonic/{name}"
        self._max_retries = max_retries
        self._bad_count   = 0

        # Accessible directly
        self.distance_cm: float = 0.0
        self.valid: bool        = False

    def configure(self) -> None:
        self.hal.pin(f"{self.name}_trig", board_pin=self._trig, mode=PinMode.OUTPUT)
        self.hal.pin(f"{self.name}_echo", board_pin=self._echo, mode=PinMode.INPUT)
        self.hal.write(f"{self.name}_trig", PinState.LOW)
        logger.info(
            "[SONAR] '%s' trig=%d echo=%d hz=%.1f",
            self.name, self._trig, self._echo, self.hz,
        )

    def tick(self) -> None:
        cm = self._measure_cm()

        if cm is None or cm < _RANGE_MIN_CM or cm > _RANGE_MAX_CM:
            self._bad_count += 1
            self.valid = False
            if self._bad_count >= self._max_retries:
                self.publish(self._topic, {
                    "distance_cm": None,
                    "distance_m":  None,
                    "valid":       False,
                    "node":        self.name,
                })
        else:
            self._bad_count  = 0
            self.distance_cm = cm
            self.valid       = True
            self.publish(self._topic, {
                "distance_cm": round(cm, 1),
                "distance_m":  round(cm / 100.0, 3),
                "valid":       True,
                "node":        self.name,
            })

    def _measure_cm(self):
        """
        Trigger a measurement and return distance in cm.

        On Arduino: the firmware handles the timing and returns µs pulse
        width via analog read channel.
        On Simulator: reads injected sensor value.
        """
        # Simulator path
        try:
            val = self.hal.read_sensor(f"{self.name}_distance_cm")
            if val:
                return float(val)
        except Exception:
            pass

        # Hardware path (Arduino NSP)
        # Send trigger: firmware measures echo and returns µs in next analog read
        try:
            self.hal.write(f"{self.name}_trig", PinState.HIGH)
            self.hal.write(f"{self.name}_trig", PinState.LOW)
            # Firmware returns pulse width in µs via analog channel (0-1023 maps to 0-23200 µs)
            raw = self.hal.read(f"{self.name}_echo")  # returns 0.0–1.0
            if isinstance(raw, float):
                pulse_us = raw * 23_200.0
                return pulse_us / 58.0
        except Exception:
            pass

        return None
