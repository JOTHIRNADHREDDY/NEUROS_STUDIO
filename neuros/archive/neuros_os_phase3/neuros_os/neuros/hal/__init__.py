"""
neuros.hal
==========
Universal Hardware Abstraction Layer — Phase 1.

The HAL is the bridge between the NEUROS kernel and physical hardware.
All hardware access must go through the HAL; nodes never touch hardware
directly.

Hardware detection strategy (Phase 1)
--------------------------------------
1. Check explicit `board=` argument first (user-specified)
2. Try to import `RPi.GPIO`  → Raspberry Pi HAL
3. Try serial port enumeration → Arduino HAL
4. Fall back to Simulator HAL (for development / CI)

Domain A HALs (this phase)
---------------------------
  ArduinoHAL    — serial-based communication with Arduino boards
  RaspberryPiHAL — direct GPIO via RPi.GPIO or gpiozero

Phase 2 will add:
  LinuxRTHAL    — PREEMPT-RT GPIO/SPI/I2C with low-latency scheduling
  ROS2HAL       — wraps NEUROS HAL in ROS2 publisher/subscriber nodes

Phase 4 will add:
  QNXCertifiedHAL — DO-178C / IEC 62304 compliant path
"""

from neuros.hal.base import HAL, HALError, PinMode, PinState
from neuros.hal.detect import auto_detect_hal

__all__ = ["HAL", "HALError", "PinMode", "PinState", "auto_detect_hal"]
