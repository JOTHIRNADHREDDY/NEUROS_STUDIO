"""
neuros.nodes.sensor.encoder
=============================
Quadrature encoder node — wheel odometry.

Tracks rising edges on channel A (and direction via channel B)
to compute position (ticks), velocity (ticks/s), and distance (m).

Published topics
----------------
  /robot/sensor/encoder/<name>   {"ticks": int, "rpm": float,
                                   "velocity_ms": float, "distance_m": float}

Phase 1: polling-based edge detection (soft-RT, suitable for ≤500 RPM).
Phase 2: interrupt-driven via Linux GPIO events or PREEMPT-RT.
"""
from __future__ import annotations
import logging, time
from neuros.nodes.base import Node, NodePriority
from neuros.hal.base   import PinMode, PinState

logger = logging.getLogger("neuros.nodes.sensor.encoder")


class EncoderNode(Node):
    """
    Quadrature wheel encoder.

    Parameters
    ----------
    name           : node identifier
    pin_a          : channel A board pin
    pin_b          : channel B board pin (direction), optional
    ticks_per_rev  : encoder CPR (counts per revolution)
    wheel_dia_m    : wheel diameter in metres (for distance calculation)
    hz             : polling rate (default 500 Hz)
    topic          : override publish topic

    Example
    -------
        enc_left = EncoderNode("enc_left",  pin_a=18, pin_b=19,
                               ticks_per_rev=360, wheel_dia_m=0.065, hz=500)
        robot.add_node(enc_left)
    """

    def __init__(
        self,
        name:           str,
        *,
        pin_a:          int,
        pin_b:          int          = -1,
        ticks_per_rev:  int          = 360,
        wheel_dia_m:    float        = 0.065,
        hz:             float        = 500.0,
        topic:          str          = "",
        priority:       NodePriority = NodePriority.HIGH,
    ) -> None:
        super().__init__(name, hz=hz, priority=priority)
        self._pin_a         = pin_a
        self._pin_b         = pin_b
        self._ticks_per_rev = ticks_per_rev
        self._wheel_circ    = wheel_dia_m * 3.14159265
        self._topic         = topic or f"/robot/sensor/encoder/{name}"

        self.ticks:      int   = 0
        self.velocity_ms: float = 0.0
        self.distance_m:  float = 0.0
        self.rpm:         float = 0.0

        self._last_a:     int   = 0
        self._last_ticks: int   = 0
        self._last_t:     float = 0.0

    def configure(self) -> None:
        self.hal.pin(f"{self.name}_a", board_pin=self._pin_a, mode=PinMode.INPUT_PULLUP)
        if self._pin_b >= 0:
            self.hal.pin(f"{self.name}_b", board_pin=self._pin_b, mode=PinMode.INPUT_PULLUP)
        self._last_t = time.monotonic()
        logger.info("[ENC] '%s' tpr=%d wheel_circ=%.4fm hz=%.0f",
                    self.name, self._ticks_per_rev, self._wheel_circ, self.hz)

    def tick(self) -> None:
        now = time.monotonic()
        dt  = now - self._last_t

        # Read channel A
        a_raw = self.hal.read(f"{self.name}_a")
        a     = int(a_raw.value) if hasattr(a_raw, "value") else int(a_raw)

        # Rising edge detection
        if a == 1 and self._last_a == 0:
            # Direction from channel B (1 = forward, 0 = backward)
            if self._pin_b >= 0:
                b_raw = self.hal.read(f"{self.name}_b")
                b     = int(b_raw.value) if hasattr(b_raw, "value") else int(b_raw)
                self.ticks += 1 if b == 1 else -1
            else:
                self.ticks += 1

        self._last_a = a

        # Velocity calculation every tick
        if dt > 0:
            delta_ticks   = self.ticks - self._last_ticks
            self.rpm          = (delta_ticks / self._ticks_per_rev) / dt * 60.0
            self.velocity_ms  = (delta_ticks / self._ticks_per_rev) * self._wheel_circ / dt
            self.distance_m   = (self.ticks / self._ticks_per_rev) * self._wheel_circ
            self._last_ticks  = self.ticks
            self._last_t      = now

        self.publish(self._topic, {
            "ticks":       self.ticks,
            "rpm":         round(self.rpm, 2),
            "velocity_ms": round(self.velocity_ms, 4),
            "distance_m":  round(self.distance_m, 4),
        })

    def reset(self) -> None:
        """Reset tick counter and distance (e.g. at waypoint)."""
        self.ticks      = 0
        self.distance_m = 0.0
