"""
neuros.nodes.actuator.led
==========================
LED actuator node — single LED, multi-LED, and RGB LED.

Modes
-----
  "digital"   : on/off only (GPIO HIGH/LOW)
  "pwm"       : brightness 0.0–1.0 (PWM)
  "rgb"       : three pins for R, G, B channels (PWM)

Patterns (subscribed via /robot/cmd/led/<name>)
------------------------------------------------
  {"state": "on"}
  {"state": "off"}
  {"state": "toggle"}
  {"brightness": 0.0–1.0}           # PWM mode only
  {"pattern": "blink", "hz": 2}
  {"pattern": "pulse", "hz": 0.5}   # smooth breathing
  {"pattern": "sos"}
  {"rgb": [255, 128, 0]}             # RGB mode only

Published topic: /robot/actuator/led/<name>
  {"state": bool, "brightness": float, "pattern": str}
"""
from __future__ import annotations
import logging, math, time
from neuros.nodes.base import Node, NodePriority
from neuros.hal.base   import PinMode, PinState

logger = logging.getLogger("neuros.nodes.actuator.led")

# SOS pattern: . . .  - - -  . . .   (True=on, False=off, float=duration)
_SOS = ([True, False]*3 + [None]*1 +
        [(True, 0.3), False]*3 + [None]*1 +
        [True, False]*3)


class LEDNode(Node):
    """
    LED actuator with pattern support.

    Parameters
    ----------
    name        : node identifier
    pin         : board pin (or pin_r for RGB)
    mode        : "digital" | "pwm" | "rgb"
    pin_r/g/b   : RGB channel pins (mode="rgb" only)
    hz          : update rate (default 100 Hz for smooth PWM)
    invert      : True if LOW turns the LED on (active-low wiring)

    Example
    -------
        status_led = LEDNode("status", pin=13, mode="pwm")
        rgb_led    = LEDNode("rgb",    mode="rgb", pin_r=9, pin_g=10, pin_b=11)
        robot.add_node(status_led)
        robot.add_node(rgb_led)

        # Blink at 2 Hz
        robot.publish("cmd/led/status", {"pattern": "blink", "hz": 2})

        # Set RGB to orange
        robot.publish("cmd/led/rgb", {"rgb": [255, 128, 0]})
    """

    def __init__(
        self,
        name:     str,
        *,
        pin:      int          = -1,
        mode:     str          = "digital",
        pin_r:    int          = -1,
        pin_g:    int          = -1,
        pin_b:    int          = -1,
        hz:       float        = 100.0,
        invert:   bool         = False,
        priority: NodePriority = NodePriority.LOW,
    ) -> None:
        super().__init__(name, hz=hz, priority=priority)
        self._pin    = pin
        self._mode   = mode
        self._pin_r, self._pin_g, self._pin_b = pin_r, pin_g, pin_b
        self._invert = invert

        self._state:      bool    = False
        self._brightness: float   = 0.0
        self._pattern:    str     = "none"
        self._pattern_hz: float   = 1.0
        self._rgb:        list    = [0, 0, 0]
        self._phase:      float   = 0.0

    def configure(self) -> None:
        hw_mode = PinMode.OUTPUT if self._mode == "digital" else PinMode.PWM
        if self._mode == "rgb":
            for ch, p in [("r", self._pin_r), ("g", self._pin_g), ("b", self._pin_b)]:
                if p >= 0:
                    self.hal.pin(f"{self.name}_{ch}", board_pin=p, mode=PinMode.PWM)
        elif self._pin >= 0:
            self.hal.pin(self.name, board_pin=self._pin, mode=hw_mode)
        logger.info("[LED] '%s' mode=%s pin=%d invert=%s", self.name, self._mode, self._pin, self._invert)

    def on_activate(self) -> None:
        self.subscribe(f"/robot/cmd/led/{self.name}", self._on_cmd)

    def _on_cmd(self, msg) -> None:
        d = msg.data
        if "state" in d:
            s = d["state"]
            if s == "on":      self._state = True;  self._pattern = "none"
            elif s == "off":   self._state = False; self._pattern = "none"
            elif s == "toggle":self._state = not self._state; self._pattern = "none"
        if "brightness" in d:
            self._brightness = float(d["brightness"])
            self._pattern = "none"
        if "pattern" in d:
            self._pattern    = d["pattern"]
            self._pattern_hz = float(d.get("hz", 1.0))
            self._phase      = 0.0
        if "rgb" in d and self._mode == "rgb":
            self._rgb = d["rgb"][:3]

    def tick(self) -> None:
        dt = 1.0 / self.hz
        self._phase += dt

        if self._mode == "rgb":
            r, g, b = [v / 255.0 for v in self._rgb]
            self._write_rgb(r, g, b)
        elif self._pattern == "blink":
            on = (self._phase * self._pattern_hz % 1.0) < 0.5
            self._write_digital(on)
        elif self._pattern == "pulse":
            # Sinusoidal breathing
            bright = (math.sin(self._phase * self._pattern_hz * 2 * math.pi) + 1) / 2
            self._write_pwm(bright)
        elif self._pattern == "sos":
            # Simple SOS approximation using phase
            t = self._phase % 3.0
            on = t < 0.5 or (1.0 < t < 1.5) or (2.0 < t < 2.5)
            self._write_digital(on)
        elif self._mode == "pwm":
            self._write_pwm(self._brightness if self._state else 0.0)
        else:
            self._write_digital(self._state)

        self.publish(f"/robot/actuator/led/{self.name}", {
            "state":      self._state,
            "brightness": self._brightness,
            "pattern":    self._pattern,
        })

    def _write_digital(self, on: bool) -> None:
        v = PinState.LOW if (on ^ self._invert) else PinState.HIGH  # invert if needed
        v = PinState.HIGH if on else PinState.LOW
        if self._invert:
            v = PinState.LOW if on else PinState.HIGH
        self.hal.write(self.name, v)

    def _write_pwm(self, duty: float) -> None:
        d = (1.0 - duty) if self._invert else duty
        self.hal.pwm_write(self._pin, max(0.0, min(1.0, d)))

    def _write_rgb(self, r: float, g: float, b: float) -> None:
        for ch, v in [("r", r), ("g", g), ("b", b)]:
            pname = f"{self.name}_{ch}"
            if self._invert:
                v = 1.0 - v
            self.hal.pwm_write(getattr(self, f"_pin_{ch}"), v)

    def destroy(self) -> None:
        # Turn off on shutdown
        if self._mode == "rgb":
            self._write_rgb(0, 0, 0)
        elif self._mode == "pwm":
            self._write_pwm(0.0)
        else:
            self._write_digital(False)
        super().destroy()
