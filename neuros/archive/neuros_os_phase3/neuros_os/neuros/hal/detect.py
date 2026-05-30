"""
neuros.hal.detect  (Phase 2)
"""
from __future__ import annotations
import logging, os
from typing import Optional
from neuros.hal.base import HAL

logger = logging.getLogger("neuros.hal.detect")

def auto_detect_hal(board=None, port=None, *, baud=115200,
                    noise_level=0.0, sim_seed=None, i2c_bus=1) -> HAL:
    b = (board or "").lower().strip()
    if b in ("simulator", "sim"):    return _make_simulator(noise_level, sim_seed)
    if b == "arduino":               return _make_arduino(port or _find_arduino_port() or "/dev/ttyUSB0", baud)
    if b in ("rpi","pi","raspberrypi","raspberry_pi","raspberry-pi"): return _make_rpi(i2c_bus=i2c_bus)
    if b == "jetson":                return _make_jetson(i2c_bus=i2c_bus)

    j = _try_jetson(i2c_bus=i2c_bus)
    if j: logger.info("[DETECT] NVIDIA Jetson → JetsonHAL"); return j

    r = _try_rpi(i2c_bus=i2c_bus)
    if r: logger.info("[DETECT] Raspberry Pi → RaspberryPiHAL"); return r

    p = port or _find_arduino_port()
    if p:
        try:
            hal = _make_arduino(p, baud)
            logger.info("[DETECT] Arduino on %s → ArduinoHAL", p)
            return hal
        except Exception as e:
            logger.debug("[DETECT] Arduino probe failed: %s", e)

    logger.warning("[DETECT] No hardware — SimulatorHAL active")
    return _make_simulator(noise_level, sim_seed)

def _make_simulator(noise, seed):
    from neuros.hal.drivers.simulator import SimulatorHAL
    h = SimulatorHAL(noise_level=noise, seed=seed); h.connect(); return h

def _make_arduino(port, baud):
    from neuros.hal.drivers.arduino import ArduinoHAL
    h = ArduinoHAL(port=port, baud=baud); h.connect(); return h

def _make_rpi(*, i2c_bus=1):
    from neuros.hal.drivers.rpi import RaspberryPiHAL
    h = RaspberryPiHAL(i2c_bus=i2c_bus); h.connect(); return h

def _make_jetson(*, i2c_bus=1):
    from neuros.hal.drivers.jetson import JetsonHAL
    h = JetsonHAL(i2c_bus=i2c_bus); h.connect(); return h

def _try_jetson(*, i2c_bus=1):
    try:
        with open("/proc/device-tree/model") as f:
            m = f.read()
            if "Jetson" in m or "NVIDIA" in m: return _make_jetson(i2c_bus=i2c_bus)
    except FileNotFoundError: pass
    if os.path.exists("/usr/lib/aarch64-linux-gnu/tegra/"):
        try: return _make_jetson(i2c_bus=i2c_bus)
        except Exception: pass
    return None

def _try_rpi(*, i2c_bus=1):
    try:
        with open("/proc/device-tree/model") as f:
            if "Raspberry" in f.read(): return _make_rpi(i2c_bus=i2c_bus)
    except FileNotFoundError: pass
    try:
        import RPi.GPIO; return _make_rpi(i2c_bus=i2c_bus)
    except Exception: pass
    return None

def _find_arduino_port():
    try:
        import serial.tools.list_ports as lp
        for p in lp.comports():
            d = (p.description or "").lower(); m = (p.manufacturer or "").lower()
            if any(k in d or k in m for k in ("arduino","ch340","ftdi","cp210","ch341")):
                return p.device
    except ImportError: pass
    return None
