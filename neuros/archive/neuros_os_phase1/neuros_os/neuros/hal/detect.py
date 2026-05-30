"""
neuros.hal.detect
=================
Hardware auto-detection — chooses the correct HAL driver at runtime.

Detection order
---------------
1. `board="simulator"` or `board="sim"` → SimulatorHAL (explicit)
2. `board="arduino"` + `port=...`       → ArduinoHAL  (explicit)
3. `board="rpi"` or `board="pi"`        → RaspberryPiHAL (Phase 2)
4. Auto: try RPi.GPIO import             → RaspberryPiHAL (Phase 2)
5. Auto: try pyserial + scan ports      → ArduinoHAL
6. Fallback                             → SimulatorHAL (with warning)

Phase 2 will add Jetson Nano, BeagleBone, Orange Pi detection.
"""

from __future__ import annotations

import logging
from typing import Optional

from neuros.hal.base import HAL

logger = logging.getLogger("neuros.hal.detect")


def auto_detect_hal(
    board: Optional[str] = None,
    port:  Optional[str] = None,
    *,
    baud:  int           = 115_200,
    noise_level: float   = 0.0,
    sim_seed:    Optional[int] = None,
) -> HAL:
    """
    Detect and return the appropriate HAL for the current hardware.

    Parameters
    ----------
    board       : force a specific HAL ("arduino", "rpi", "simulator")
    port        : serial port for Arduino (e.g. "/dev/ttyUSB0")
    baud        : baud rate for Arduino
    noise_level : simulator noise (only used when SimulatorHAL is selected)
    sim_seed    : random seed for reproducible simulations

    Returns
    -------
    A connected HAL instance.

    Raises
    ------
    HALError if an explicit board is specified but cannot be initialised.
    """
    board_lower = (board or "").lower()

    # ── Explicit overrides ─────────────────────────────────────────────────
    if board_lower in ("simulator", "sim"):
        return _make_simulator(noise_level, sim_seed)

    if board_lower == "arduino":
        return _make_arduino(port or _find_arduino_port(), baud)

    if board_lower in ("rpi", "pi", "raspberrypi", "raspberry_pi"):
        return _make_rpi()

    # ── Auto-detection ─────────────────────────────────────────────────────
    # Try Raspberry Pi
    rpi_hal = _try_rpi()
    if rpi_hal is not None:
        logger.info("[DETECT] Raspberry Pi detected")
        return rpi_hal

    # Try Arduino over serial
    arduino_port = port or _find_arduino_port()
    if arduino_port:
        try:
            hal = _make_arduino(arduino_port, baud)
            logger.info("[DETECT] Arduino detected on %s", arduino_port)
            return hal
        except Exception as e:
            logger.debug("[DETECT] Arduino probe failed: %s", e)

    # Fallback to simulator
    logger.warning(
        "[DETECT] No hardware found — using SimulatorHAL. "
        "Pass board='arduino' or board='rpi' to connect real hardware."
    )
    return _make_simulator(noise_level, sim_seed)


# ── Factory helpers ────────────────────────────────────────────────────────
def _make_simulator(noise: float, seed: Optional[int]) -> HAL:
    from neuros.hal.drivers.simulator import SimulatorHAL
    hal = SimulatorHAL(noise_level=noise, seed=seed)
    hal.connect()
    return hal


def _make_arduino(port: str, baud: int) -> HAL:
    from neuros.hal.drivers.arduino import ArduinoHAL
    hal = ArduinoHAL(port=port, baud=baud)
    hal.connect()
    return hal


def _make_rpi() -> HAL:
    # Phase 2 — RaspberryPiHAL will live in hal/drivers/rpi.py
    raise NotImplementedError(
        "RaspberryPiHAL is a Phase 2 feature. "
        "Use board='simulator' or board='arduino' for Phase 1."
    )


def _try_rpi() -> Optional[HAL]:
    try:
        import RPi.GPIO as GPIO  # noqa: F401
        return _make_rpi()
    except (ImportError, NotImplementedError):
        return None


def _find_arduino_port() -> Optional[str]:
    """Scan serial ports for an Arduino-compatible device."""
    try:
        import serial.tools.list_ports as lp
        for port_info in lp.comports():
            desc = (port_info.description or "").lower()
            mfr  = (port_info.manufacturer or "").lower()
            if any(kw in desc or kw in mfr for kw in ("arduino", "ch340", "ftdi", "cp210")):
                logger.debug("[DETECT] found Arduino candidate: %s", port_info.device)
                return port_info.device
    except ImportError:
        pass
    return None
