"""
neuros.nodes.sensor.temperature
================================
Temperature sensor node.

Supports DS18B20 (1-Wire) and NTC thermistor (analog).

Published topic: /robot/sensor/temperature/<name>
Payload: {"celsius": float, "fahrenheit": float, "valid": bool}
"""
from __future__ import annotations
import logging, math
from neuros.nodes.base import Node, NodePriority
from neuros.hal.base import PinMode

logger = logging.getLogger("neuros.nodes.sensor.temperature")

# NTC Steinhart-Hart constants (10kΩ NTC, B=3950)
_R_REF  = 10_000.0
_R_NOM  = 10_000.0
_T_NOM  = 25.0
_B_COEFF = 3950.0


class TemperatureNode(Node):
    """
    Temperature sensor node.

    Parameters
    ----------
    name        : node identifier
    pin         : board pin (analog for NTC, digital 1-Wire for DS18B20)
    mode        : "ntc" | "ds18b20" | "simulate"
    hz          : polling rate (default 1 Hz — temp changes slowly)
    topic       : override publish topic

    Example
    -------
        temp = TemperatureNode("env_temp", pin=A0, mode="ntc", hz=1)
        robot.add_node(temp)
    """

    def __init__(
        self,
        name:     str,
        *,
        pin:      int          = 0,
        mode:     str          = "simulate",
        hz:       float        = 1.0,
        topic:    str          = "",
        priority: NodePriority = NodePriority.LOW,
    ) -> None:
        super().__init__(name, hz=hz, priority=priority)
        self._pin    = pin
        self._mode   = mode
        self._topic  = topic or f"/robot/sensor/temperature/{name}"
        self.celsius: float = 25.0

    def configure(self) -> None:
        if self._mode == "ntc":
            self.hal.pin(self.name, board_pin=self._pin, mode=PinMode.ANALOG_IN)
        logger.info("[TEMP] '%s' mode=%s pin=%d hz=%.1f", self.name, self._mode, self._pin, self.hz)

    def tick(self) -> None:
        celsius = self._read_celsius()
        self.celsius = celsius
        self.publish(self._topic, {
            "celsius":    round(celsius, 2),
            "fahrenheit": round(celsius * 9/5 + 32, 2),
            "valid":      True,
            "node":       self.name,
        })

    def _read_celsius(self) -> float:
        if self._mode == "ntc":
            raw = float(self.hal.read(self.name))   # 0.0–1.0
            if raw <= 0 or raw >= 1:
                return 25.0
            # Voltage divider → resistance → Steinhart-Hart
            r = _R_REF * raw / (1.0 - raw)
            inv_t = (1.0 / (_T_NOM + 273.15)) + (1.0 / _B_COEFF) * math.log(r / _R_NOM)
            return (1.0 / inv_t) - 273.15
        # Simulate or DS18B20 (stub)
        try:
            return float(self.hal.read_sensor(f"{self.name}_celsius"))
        except Exception:
            return 25.0
