"""
neuros.nodes.sensor.battery
=============================
Battery monitor node.

Reads battery voltage via ADC voltage divider, computes state-of-charge
(SoC), and publishes alerts when voltage drops below threshold.

Published topics
----------------
  /robot/sensor/battery          {"voltage_v": float, "soc_pct": float,
                                   "status": "ok"|"low"|"critical"}
  /robot/system/battery_alert    published only on status change to low/critical

Battery profiles (Phase 1)
--------------------------
  "lipo_1s"   : 3.0 V – 4.2 V  (1-cell LiPo)
  "lipo_2s"   : 6.0 V – 8.4 V
  "lipo_3s"   : 9.0 V – 12.6 V
  "lipo_4s"   : 12.0 V – 16.8 V
  "nimh_6v"   : 5.5 V – 7.2 V
  "aa_4x"     : 3.5 V – 6.0 V   (4× AA alkaline)
  "usb_5v"    : 4.5 V – 5.25 V
"""
from __future__ import annotations
import logging
from neuros.nodes.base import Node, NodePriority
from neuros.hal.base   import PinMode

logger = logging.getLogger("neuros.nodes.sensor.battery")

_PROFILES = {
    "lipo_1s":  (3.0,  4.2),
    "lipo_2s":  (6.0,  8.4),
    "lipo_3s":  (9.0, 12.6),
    "lipo_4s":  (12.0, 16.8),
    "nimh_6v":  (5.5,  7.2),
    "aa_4x":    (3.5,  6.0),
    "usb_5v":   (4.5,  5.25),
}


class BatteryMonitorNode(Node):
    """
    Battery voltage monitor.

    Parameters
    ----------
    name           : node identifier
    pin            : analog input pin connected to voltage divider output
    profile        : battery chemistry profile string (see _PROFILES)
    divider_ratio  : voltage divider ratio (Vbat = Vpin * ratio).
                     Example: 10kΩ + 10kΩ divider on 5V ADC → ratio = 2.0
    adc_vref       : ADC reference voltage (default 5.0 V for Arduino)
    low_pct        : SoC % to trigger "low" alert (default 20)
    critical_pct   : SoC % to trigger "critical" alert (default 5)
    hz             : polling rate (default 0.5 Hz)
    """

    def __init__(
        self,
        name:           str,
        *,
        pin:            int          = 0,
        profile:        str          = "lipo_1s",
        divider_ratio:  float        = 2.0,
        adc_vref:       float        = 5.0,
        low_pct:        int          = 20,
        critical_pct:   int          = 5,
        hz:             float        = 0.5,
        priority:       NodePriority = NodePriority.LOW,
    ) -> None:
        super().__init__(name, hz=hz, priority=priority)
        self._pin           = pin
        self._divider       = divider_ratio
        self._vref          = adc_vref
        self._vmin, self._vmax = _PROFILES.get(profile, (3.0, 4.2))
        self._low_v         = self._vmin + (self._vmax - self._vmin) * (low_pct / 100)
        self._crit_v        = self._vmin + (self._vmax - self._vmin) * (critical_pct / 100)
        self._last_status   = "ok"

        self.voltage_v: float = self._vmax
        self.soc_pct:   float = 100.0
        self.status:    str   = "ok"

    def configure(self) -> None:
        self.hal.pin(self.name, board_pin=self._pin, mode=PinMode.ANALOG_IN)
        logger.info("[BATT] '%s' pin=%d profile=[%.1fV–%.1fV] divider=%.1fx",
                    self.name, self._pin, self._vmin, self._vmax, self._divider)

    def tick(self) -> None:
        raw = float(self.hal.read(self.name))          # 0.0–1.0
        v   = raw * self._vref * self._divider         # actual battery voltage

        # Clamp and compute SoC
        v   = max(self._vmin, min(self._vmax, v))
        soc = (v - self._vmin) / (self._vmax - self._vmin) * 100.0

        self.voltage_v = round(v, 3)
        self.soc_pct   = round(soc, 1)
        self.status    = ("critical" if v <= self._crit_v
                          else "low" if v <= self._low_v
                          else "ok")

        self.publish("/robot/sensor/battery", {
            "voltage_v": self.voltage_v,
            "soc_pct":   self.soc_pct,
            "status":    self.status,
        })

        # Alert on status change
        if self.status != self._last_status and self.status != "ok":
            logger.warning("[BATT] Battery %s! %.2fV (%.1f%%)", self.status.upper(), v, soc)
            self.publish("/robot/system/battery_alert", {
                "status":    self.status,
                "voltage_v": self.voltage_v,
                "soc_pct":   self.soc_pct,
            })
        self._last_status = self.status
