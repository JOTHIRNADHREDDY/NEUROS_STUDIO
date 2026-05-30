"""
neuros.hal.drivers.simulator
=============================
Simulator HAL — software-only, no physical hardware required.

Used when:
  • Running in CI / test environments
  • Developing nodes before hardware arrives
  • Running on the Digital Twin (Simulation Layer)
  • Auto-detection fallback when no real board is found

The simulator records all writes and replays reads from configurable
sensor scripts. This makes it suitable for deterministic integration
testing.

Sensor simulation
-----------------
  sim_hal.inject("IMU", {"ax": 0.1, "ay": 0.0, "az": 9.81})
  sim_hal.inject_stream("LIDAR", my_generator_fn)

The simulator also emits all operations as Neural Bus messages so
the node graph visualiser works correctly without hardware.
"""

from __future__ import annotations

import logging
import random
import time
from collections import defaultdict
from typing import Any, Callable, Dict, Generator, Optional, Union

from neuros.hal.base import HAL, HALError, PinMode, PinState

logger = logging.getLogger("neuros.hal.simulator")


class SimulatorHAL(HAL):
    """
    Software simulator — zero hardware dependencies.

    Operations are no-ops by default (writes succeed silently,
    reads return configurable values or defaults).

    Usage
    -----
        hal = SimulatorHAL(noise_level=0.02)
        hal.connect()

        # Inject a fixed sensor value
        hal.inject_pin_read(3, 1)    # pin 3 always reads HIGH

        # Inject noisy analog
        hal.inject_pin_read(A0, lambda: random.gauss(0.5, 0.02))
    """

    def __init__(self, *, noise_level: float = 0.0, seed: Optional[int] = None) -> None:
        super().__init__(name="simulator")
        self._noise    = noise_level
        self._rng      = random.Random(seed)
        # Storage
        self._pin_states:    Dict[int, Any]      = defaultdict(int)
        self._pin_injectors: Dict[int, Callable] = {}
        self._uart_buffers:  Dict[int, bytearray] = defaultdict(bytearray)
        self._i2c_store:     Dict[tuple, bytes]  = {}
        self._sensor_feeds:  Dict[str, Any]      = {}
        self._write_log:     list                = []   # (timestamp, board_pin, value)
        # Stats
        self._read_count  = 0
        self._write_count = 0

    # ── Connection ─────────────────────────────────────────────────────────
    def connect(self) -> None:
        self._connected = True
        logger.info("[SIM HAL] connected (no hardware)")

    def disconnect(self) -> None:
        self._connected = False
        logger.info("[SIM HAL] disconnected")

    # ── Pin injection helpers ───────────────────────────────────────────────
    def inject_pin_read(self, board_pin: int, value: Union[Any, Callable]) -> None:
        """Set what a pin read returns. `value` can be a constant or a callable."""
        if callable(value):
            self._pin_injectors[board_pin] = value
        else:
            self._pin_injectors[board_pin] = lambda: value

    def inject_sensor(self, name: str, value: Any) -> None:
        """Inject a named sensor value (used by SensorProxy)."""
        self._sensor_feeds[name] = value

    def read_sensor(self, name: str) -> Any:
        val = self._sensor_feeds.get(name, 0.0)
        if callable(val):
            val = val()
        if self._noise and isinstance(val, (int, float)):
            val += self._rng.gauss(0, self._noise)
        return val

    # ── HAL abstract implementations ───────────────────────────────────────
    def _configure_pin(self, board_pin: int, mode: PinMode) -> None:
        logger.debug("[SIM HAL] configure pin=%d mode=%s", board_pin, mode.value)

    def _write_pin(self, board_pin: int, value: Any) -> None:
        self._pin_states[board_pin] = value
        self._write_count += 1
        self._write_log.append((time.monotonic(), board_pin, value))
        logger.debug("[SIM HAL] write pin=%d value=%s", board_pin, value)

    def _read_pin(self, board_pin: int) -> Any:
        self._read_count += 1
        injector = self._pin_injectors.get(board_pin)
        if injector:
            val = injector()
        else:
            val = self._pin_states[board_pin]
        if self._noise and isinstance(val, (int, float)):
            val += self._rng.gauss(0, self._noise)
        logger.debug("[SIM HAL] read pin=%d → %s", board_pin, val)
        return val

    def uart_write(self, data: bytes, *, port: int = 0) -> None:
        self._uart_buffers[port].extend(data)
        logger.debug("[SIM HAL] uart_write port=%d data=%r", port, data)

    def uart_read(self, n_bytes: int = 1, *, port: int = 0) -> bytes:
        buf  = self._uart_buffers[port]
        data = bytes(buf[:n_bytes])
        del buf[:n_bytes]
        return data

    def i2c_write(self, address: int, register: int, data: bytes) -> None:
        self._i2c_store[(address, register)] = data
        logger.debug("[SIM HAL] i2c_write 0x%02X reg=0x%02X", address, register)

    def i2c_read(self, address: int, register: int, n_bytes: int) -> bytes:
        stored = self._i2c_store.get((address, register), bytes(n_bytes))
        return stored[:n_bytes]

    def pwm_write(self, board_pin: int, duty_cycle: float, *, freq_hz: float = 50.0) -> None:
        self._pin_states[board_pin] = duty_cycle
        logger.debug("[SIM HAL] pwm pin=%d duty=%.3f freq=%.1fHz", board_pin, duty_cycle, freq_hz)

    def board_info(self) -> dict:
        return {
            "board":        "NEUROS Simulator",
            "domain":       "A (simulated)",
            "noise_level":  self._noise,
            "reads":        self._read_count,
            "writes":       self._write_count,
        }

    # ── Write log for testing ──────────────────────────────────────────────
    def get_write_log(self, *, since: float = 0.0) -> list:
        return [(t, pin, val) for t, pin, val in self._write_log if t >= since]

    def clear_log(self) -> None:
        self._write_log.clear()
