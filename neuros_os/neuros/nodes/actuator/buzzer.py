"""
neuros.nodes.actuator.buzzer
=============================
Buzzer actuator node — active and passive buzzer.

Active buzzer  : just needs HIGH/LOW to beep at fixed frequency
Passive buzzer : needs PWM at specific frequency for tones

Subscribed topic: /robot/cmd/buzzer/<name>
  {"state": "on"}
  {"state": "off"}
  {"tone": 440}            # Hz — passive only
  {"pattern": "beep"}      # single short beep
  {"pattern": "double"}    # double beep (e.g. confirmation)
  {"pattern": "alarm"}     # continuous alarm
  {"pattern": "startup"}   # startup jingle
  {"pattern": "error"}     # error alert

Published topic: /robot/actuator/buzzer/<name>
  {"active": bool, "frequency_hz": float, "pattern": str}
"""
from __future__ import annotations
import logging, math
from neuros.nodes.base import Node, NodePriority
from neuros.hal.base   import PinMode, PinState

logger = logging.getLogger("neuros.nodes.actuator.buzzer")

# Note frequencies (Hz) for passive buzzer melodies
NOTES = {
    "C4": 261.6, "D4": 293.7, "E4": 329.6, "F4": 349.2,
    "G4": 392.0, "A4": 440.0, "B4": 493.9,
    "C5": 523.3, "G5": 784.0, "REST": 0.0,
}

# Pattern sequences: list of (note_or_hz, duration_ticks)
_PATTERNS = {
    "beep":    [(NOTES["C5"], 10), (NOTES["REST"], 5)],
    "double":  [(NOTES["C5"], 8), (NOTES["REST"], 4), (NOTES["C5"], 8), (NOTES["REST"], 10)],
    "alarm":   [(NOTES["A4"], 15), (NOTES["G4"], 15)] * 4,
    "startup": [(NOTES["C4"], 6), (NOTES["E4"], 6), (NOTES["G4"], 6), (NOTES["C5"], 10)],
    "error":   [(NOTES["A4"], 20), (NOTES["REST"], 5), (NOTES["A4"], 20)],
}


class BuzzerNode(Node):
    """
    Buzzer actuator with pattern support.

    Parameters
    ----------
    name    : node identifier
    pin     : board pin
    passive : True = passive (PWM tones), False = active (digital on/off)
    hz      : update rate (default 100 Hz)

    Example
    -------
        buzzer = BuzzerNode("buzzer", pin=8, passive=False)
        robot.add_node(buzzer)

        # Play startup jingle
        robot.publish("cmd/buzzer/buzzer", {"pattern": "startup"})
    """

    def __init__(
        self,
        name:     str,
        *,
        pin:      int,
        passive:  bool         = False,
        hz:       float        = 100.0,
        priority: NodePriority = NodePriority.LOW,
    ) -> None:
        super().__init__(name, hz=hz, priority=priority)
        self._pin     = pin
        self._passive = passive
        self._active  = False
        self._freq    = 0.0
        self._pattern = "none"
        self._seq: list = []
        self._seq_idx:  int  = 0
        self._seq_tick: int  = 0

    def configure(self) -> None:
        mode = PinMode.PWM if self._passive else PinMode.OUTPUT
        self.hal.pin(self.name, board_pin=self._pin, mode=mode)
        self._off()
        logger.info("[BUZZ] '%s' pin=%d passive=%s", self.name, self._pin, self._passive)

    def on_activate(self) -> None:
        self.subscribe(f"/robot/cmd/buzzer/{self.name}", self._on_cmd)

    def _on_cmd(self, msg) -> None:
        d = msg.data
        if "state" in d:
            if d["state"] == "on":
                self._active  = True
                self._pattern = "none"
                self._freq    = float(d.get("frequency_hz", 1000.0))
            elif d["state"] == "off":
                self._active  = False
                self._pattern = "none"
        if "tone" in d and self._passive:
            self._freq    = float(d["tone"])
            self._active  = True
            self._pattern = "tone"
        if "pattern" in d and d["pattern"] in _PATTERNS:
            self._pattern  = d["pattern"]
            self._seq      = _PATTERNS[d["pattern"]]
            self._seq_idx  = 0
            self._seq_tick = 0

    def tick(self) -> None:
        if self._pattern not in ("none", "tone") and self._seq:
            freq, dur = self._seq[self._seq_idx]
            self._seq_tick += 1
            if freq > 0:
                self._on(freq)
            else:
                self._off()
            if self._seq_tick >= dur:
                self._seq_tick = 0
                self._seq_idx += 1
                if self._seq_idx >= len(self._seq):
                    self._seq_idx = 0
                    self._pattern = "none"
                    self._off()
        elif self._active:
            self._on(self._freq)
        else:
            self._off()

        self.publish(f"/robot/actuator/buzzer/{self.name}", {
            "active":       self._active,
            "frequency_hz": self._freq,
            "pattern":      self._pattern,
        })

    def _on(self, freq: float) -> None:
        if self._passive and freq > 0:
            self.hal.pwm_write(self._pin, 0.5, freq_hz=freq)
        else:
            self.hal.write(self.name, PinState.HIGH)

    def _off(self) -> None:
        if self._passive:
            self.hal.pwm_write(self._pin, 0.0)
        else:
            self.hal.write(self.name, PinState.LOW)

    def destroy(self) -> None:
        self._off()
        super().destroy()
