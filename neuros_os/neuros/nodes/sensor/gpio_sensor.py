"""
neuros.nodes.sensor.gpio_sensor
================================
Generic GPIO sensor node.

Reads a digital or analog input pin at the declared rate and publishes
the value to the Neural Bus.  Use this for:
  • Push buttons / limit switches
  • PIR motion sensors
  • IR proximity sensors
  • Simple analog sensors (LDR, NTC)
  • Reed switches, hall-effect sensors

Published topic: /robot/sensor/<name>
Payload: {"value": <int|float>, "pin": <board_pin>, "mode": <str>}
"""

from __future__ import annotations

import logging
from neuros.nodes.base import Node, NodePriority
from neuros.hal.base   import PinMode

logger = logging.getLogger("neuros.nodes.sensor.gpio")


class GPIOSensorNode(Node):
    """
    Reads one GPIO pin and publishes its value.

    Parameters
    ----------
    name        : node name (also used in the published topic)
    board_pin   : physical pin number on the board
    mode        : "input" | "pullup" | "pulldown" | "analog_in"
    hz          : polling rate in Hz (default 50)
    topic       : override the publish topic (default: /robot/sensor/<name>)
    threshold   : if set, only publish when |delta| > threshold (debounce)

    Example
    -------
        button = GPIOSensorNode("start_button", board_pin=2, mode="pullup", hz=20)
        robot.add_node(button)
    """

    _MODE_MAP = {
        "input":    PinMode.INPUT,
        "pullup":   PinMode.INPUT_PULLUP,
        "pulldown": PinMode.INPUT_PULLDOWN,
        "analog_in": PinMode.ANALOG_IN,
    }

    def __init__(
        self,
        name:      str,
        *,
        board_pin: int,
        mode:      str   = "input",
        hz:        float = 50.0,
        topic:     str   = "",
        threshold: float = 0.0,
        priority:  NodePriority = NodePriority.NORMAL,
    ) -> None:
        super().__init__(name, hz=hz, priority=priority)
        self._board_pin = board_pin
        self._mode_str  = mode
        self._pin_mode  = self._MODE_MAP.get(mode, PinMode.INPUT)
        self._topic     = topic or f"/robot/sensor/{name}"
        self._threshold = threshold
        self._last_value = None

    def configure(self) -> None:
        self.hal.pin(self.name, board_pin=self._board_pin, mode=self._pin_mode)
        logger.info(
            "[GPIO SENSOR] '%s' pin=%d mode=%s topic=%s",
            self.name, self._board_pin, self._mode_str, self._topic,
        )

    def tick(self) -> None:
        value = self.hal.read(self.name)
        # Convert PinState to int for JSON-safe payload
        if hasattr(value, "value"):
            value = value.value

        # Threshold debounce
        if self._threshold and self._last_value is not None:
            if abs(float(value) - float(self._last_value)) < self._threshold:
                return

        self._last_value = value
        self.publish(self._topic, {
            "value":    value,
            "pin":      self._board_pin,
            "mode":     self._mode_str,
            "node":     self.name,
        })

    @property
    def last_value(self):
        return self._last_value
