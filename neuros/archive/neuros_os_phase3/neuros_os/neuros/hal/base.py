"""
neuros.hal.base
===============
Abstract HAL — defines the contract every hardware driver must satisfy.

All hardware operations are defined here as abstract methods.
This means user code is 100% hardware-agnostic: swap out an Arduino
for a Raspberry Pi and the node code doesn't change.

Pin model (Phase 1 — Domain A)
-------------------------------
Pins are identified by logical names OR board numbers.
  hal.pin("LED", mode=PinMode.OUTPUT)
  hal.write("LED", PinState.HIGH)
  hal.read("BUTTON")

Higher-level abstractions (Phase 1)
-------------------------------------
  hal.motor(name, channel)   → MotorProxy
  hal.servo(name, pin)       → ServoProxy
  hal.sensor(name, type)     → SensorProxy
  hal.i2c(address)           → I2CProxy
  hal.spi(bus, cs)           → SPIProxy
  hal.uart(port, baud)       → UARTProxy
"""

from __future__ import annotations

import abc
import enum
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("neuros.hal")


class HALError(Exception):
    """Raised on hardware communication failure."""


class PinMode(enum.Enum):
    INPUT         = "INPUT"
    OUTPUT        = "OUTPUT"
    INPUT_PULLUP  = "INPUT_PULLUP"
    INPUT_PULLDOWN = "INPUT_PULLDOWN"
    PWM           = "PWM"
    ANALOG_IN     = "ANALOG_IN"
    ANALOG_OUT    = "ANALOG_OUT"


class PinState(enum.IntEnum):
    LOW  = 0
    HIGH = 1


class HAL(abc.ABC):
    """
    Abstract Hardware Abstraction Layer.

    Every NEUROS hardware driver subclasses this.
    No node should ever import a concrete HAL class directly —
    always use `auto_detect_hal()` or `Robot(board=...)`.
    """

    def __init__(self, *, name: str = "hal") -> None:
        self.name            = name
        self._pin_map:  Dict[str, int]      = {}   # logical_name → board_pin
        self._pin_modes: Dict[str, PinMode] = {}
        self._connected: bool               = False

    # ── Connection lifecycle ───────────────────────────────────────────────
    @abc.abstractmethod
    def connect(self) -> None:
        """Open hardware connection. Called once during Robot.start()."""

    @abc.abstractmethod
    def disconnect(self) -> None:
        """Close hardware connection. Called during Robot.stop()."""

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Pin operations ─────────────────────────────────────────────────────
    def pin(
        self,
        name:       str,
        *,
        board_pin:  Optional[int] = None,
        mode:       PinMode       = PinMode.OUTPUT,
    ) -> None:
        """Register and configure a pin by logical name."""
        if board_pin is not None:
            self._pin_map[name] = board_pin
        elif name not in self._pin_map:
            raise HALError(f"Pin '{name}' not mapped. Provide board_pin on first use.")
        self._pin_modes[name] = mode
        self._configure_pin(self._pin_map[name], mode)

    def write(self, name: str, value: Union[PinState, int, float]) -> None:
        """Write a value to a named pin."""
        pin = self._resolve(name)
        self._write_pin(pin, value)

    def read(self, name: str) -> Union[PinState, float]:
        """Read a value from a named pin."""
        pin = self._resolve(name)
        return self._read_pin(pin)

    def toggle(self, name: str) -> None:
        """Toggle a digital output pin."""
        current = self.read(name)
        self.write(name, PinState.LOW if current else PinState.HIGH)

    def _resolve(self, name: str) -> int:
        if name not in self._pin_map:
            raise HALError(f"Pin '{name}' not registered. Call hal.pin() first.")
        return self._pin_map[name]

    # ── Abstract hardware primitives ───────────────────────────────────────
    @abc.abstractmethod
    def _configure_pin(self, board_pin: int, mode: PinMode) -> None: ...

    @abc.abstractmethod
    def _write_pin(self, board_pin: int, value: Any) -> None: ...

    @abc.abstractmethod
    def _read_pin(self, board_pin: int) -> Any: ...

    # ── Serial / UART ──────────────────────────────────────────────────────
    @abc.abstractmethod
    def uart_write(self, data: bytes, *, port: int = 0) -> None: ...

    @abc.abstractmethod
    def uart_read(self, n_bytes: int = 1, *, port: int = 0) -> bytes: ...

    # ── I2C ───────────────────────────────────────────────────────────────
    @abc.abstractmethod
    def i2c_write(self, address: int, register: int, data: bytes) -> None: ...

    @abc.abstractmethod
    def i2c_read(self, address: int, register: int, n_bytes: int) -> bytes: ...

    # ── PWM (motors / servos) ──────────────────────────────────────────────
    @abc.abstractmethod
    def pwm_write(self, board_pin: int, duty_cycle: float, *, freq_hz: float = 50.0) -> None:
        """Write PWM. duty_cycle in [0.0, 1.0]."""

    # ── System info ────────────────────────────────────────────────────────
    @abc.abstractmethod
    def board_info(self) -> dict:
        """Return board name, CPU, flash, RAM, etc."""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} connected={self._connected}>"
