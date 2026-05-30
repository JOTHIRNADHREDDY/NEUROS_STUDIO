"""
neuros.nodes.sensor.line_follower
==================================
IR reflectance array node for line-following robots.

Reads N IR sensor pins (digital or analog), computes a weighted centroid
error signal, and publishes it for a PID controller to consume.

Hardware
--------
  Digital mode  : TCRT5000, QRE1113 digital output
  Analog mode   : QTR-8A, Pololu reflectance sensors (analog, 0–1023 ADC)

Published topics
----------------
  /robot/sensor/line/raw          list of raw sensor values (0.0–1.0)
  /robot/sensor/line/error        weighted centroid error (−1.0 = far left, +1.0 = far right)
  /robot/sensor/line/detected     bool — is a line currently visible?

Error convention
----------------
  error = 0.0   → line centred under the robot
  error = −1.0  → line is fully to the left
  error = +1.0  → line is fully to the right
  error = None  → no line detected (all sensors see white / all see black)
"""

from __future__ import annotations

import logging
from typing import List, Optional

from neuros.nodes.base import Node, NodePriority
from neuros.hal.base   import PinMode

logger = logging.getLogger("neuros.nodes.sensor.line_follower")


class LineFollowerNode(Node):
    """
    IR line-following sensor array node.

    Parameters
    ----------
    name        : node identifier
    pins        : list of board pin numbers (left → right)
    analog      : True if sensors output analog values (default: False = digital)
    invert      : True if LOW = line detected (default: True for most TCRT5000 boards)
    hz          : polling rate (default 100 Hz for responsive line following)
    topic_prefix: override base topic (default: /robot/sensor/line)

    Example (5-sensor array)
    -------------------------
        lf = LineFollowerNode(
            "line",
            pins=[A0, A1, A2, A3, A4],
            analog=True,
            hz=100,
        )
        robot.add_node(lf)
    """

    def __init__(
        self,
        name:          str,
        *,
        pins:          List[int],
        analog:        bool         = False,
        invert:        bool         = True,
        hz:            float        = 100.0,
        topic_prefix:  str          = "",
        priority:      NodePriority = NodePriority.HIGH,
    ) -> None:
        super().__init__(name, hz=hz, priority=priority)
        self._pins     = pins
        self._analog   = analog
        self._invert   = invert
        self._prefix   = topic_prefix or f"/robot/sensor/line"
        self._n        = len(pins)

        # Pin names: line_0, line_1, ...
        self._pin_names = [f"{name}_{i}" for i in range(self._n)]

        # Accessible directly
        self.raw_values: List[float] = [0.0] * self._n
        self.error:      Optional[float] = None
        self.detected:   bool           = False

    def configure(self) -> None:
        mode = PinMode.ANALOG_IN if self._analog else PinMode.INPUT
        for pname, bpin in zip(self._pin_names, self._pins):
            self.hal.pin(pname, board_pin=bpin, mode=mode)
        logger.info(
            "[LINE] '%s' pins=%s analog=%s invert=%s hz=%.0f",
            self.name, self._pins, self._analog, self._invert, self.hz,
        )

    def tick(self) -> None:
        # Read all sensors
        raw: List[float] = []
        for pname in self._pin_names:
            val = self.hal.read(pname)
            if hasattr(val, "value"):
                val = float(val.value)
            else:
                val = float(val)
            raw.append(val)

        # Normalise: if digital, 0 or 1; if analog, already 0.0–1.0
        # Apply inversion: invert=True means LOW=line=1.0 in our convention
        norm: List[float] = []
        for v in raw:
            if self._analog:
                # analog: high value = dark = line
                n = v if not self._invert else (1.0 - v)
            else:
                # digital: 0 = line (TCRT5000 pulls LOW on reflection)
                n = (1.0 - v) if self._invert else v
            norm.append(n)

        self.raw_values = norm

        # Weighted centroid error
        total  = sum(norm)
        if total < 0.1:
            # No sensors activated — line lost
            self.detected = False
            self.error    = None
        else:
            # Weights: −1.0 (leftmost) to +1.0 (rightmost)
            weights = [2.0 * i / (self._n - 1) - 1.0 for i in range(self._n)] if self._n > 1 else [0.0]
            weighted_sum = sum(w * v for w, v in zip(weights, norm))
            self.error    = weighted_sum / total
            self.detected = True

        # Publish
        self.publish(f"{self._prefix}/raw",      {"values": self.raw_values, "n": self._n})
        self.publish(f"{self._prefix}/error",    {"error": self.error, "detected": self.detected})
        self.publish(f"{self._prefix}/detected", {"detected": self.detected})
