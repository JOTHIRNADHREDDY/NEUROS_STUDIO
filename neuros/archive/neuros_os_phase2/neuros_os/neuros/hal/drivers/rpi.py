"""
neuros.hal.drivers.rpi
=======================
Raspberry Pi HAL — Phase 2, Domain B.

Supports Raspberry Pi 3B / 3B+ / 4B / 5 / Zero 2W.

Hardware interfaces
-------------------
  GPIO          : RPi.GPIO (falling back to lgpio on Pi 5)
  PWM           : Software PWM via RPi.GPIO; Hardware PWM on GPIO12/13/18/19
  I2C           : smbus2 (bus 1 on all Pi models)
  SPI           : spidev (bus 0, CE0/CE1)
  UART          : pyserial (/dev/ttyAMA0 or /dev/ttyS0)

Board detection
---------------
  Reads /proc/device-tree/model to identify Pi model.
  Sets GPIO mode to BCM (Broadcom pin numbering) automatically.

Hardware PWM pins (Pi 3/4)
---------------------------
  GPIO 12  : PWM0   (alt func 0)
  GPIO 13  : PWM1   (alt func 0)
  GPIO 18  : PWM0   (alt func 5)
  GPIO 19  : PWM1   (alt func 5)

Auto-detection
--------------
  Detected when /sys/firmware/devicetree/base/model contains "Raspberry Pi"
  or when RPi.GPIO imports successfully.

Install
-------
  pip install RPi.GPIO smbus2 spidev
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

from neuros.hal.base import HAL, HALError, PinMode, PinState

logger = logging.getLogger("neuros.hal.rpi")

# Hardware PWM pins for Pi 3/4
_HW_PWM_PINS = {12, 13, 18, 19}

# Pin mode mappings to RPi.GPIO constants (resolved at import time if available)
_MODE_TO_GPIO: Dict[str, int] = {}


def _load_gpio():
    """Import RPi.GPIO lazily."""
    try:
        import RPi.GPIO as GPIO
        return GPIO
    except (ImportError, RuntimeError):
        return None


def _load_smbus():
    try:
        import smbus2
        return smbus2
    except ImportError:
        return None


def _detect_pi_model() -> str:
    try:
        with open("/proc/device-tree/model") as f:
            return f.read().strip().rstrip("\x00")
    except FileNotFoundError:
        pass
    try:
        with open("/sys/firmware/devicetree/base/model") as f:
            return f.read().strip().rstrip("\x00")
    except FileNotFoundError:
        pass
    return "Raspberry Pi (unknown model)"


class RaspberryPiHAL(HAL):
    """
    Raspberry Pi Hardware Abstraction Layer.

    Parameters
    ----------
    i2c_bus     : I2C bus number (default 1 for all modern Pi)
    spi_bus     : SPI bus number (default 0)
    uart_port   : serial device (default "/dev/ttyAMA0")
    uart_baud   : UART baud rate (default 115200)

    Example
    -------
        hal = RaspberryPiHAL()
        hal.connect()

        hal.pin("LED",    board_pin=17, mode=PinMode.OUTPUT)
        hal.pin("BUTTON", board_pin=27, mode=PinMode.INPUT_PULLUP)
        hal.write("LED", PinState.HIGH)
        val = hal.read("BUTTON")
    """

    def __init__(
        self,
        *,
        i2c_bus:   int = 1,
        spi_bus:   int = 0,
        uart_port: str = "/dev/ttyAMA0",
        uart_baud: int = 115_200,
    ) -> None:
        super().__init__(name="rpi")
        self._i2c_bus   = i2c_bus
        self._spi_bus   = spi_bus
        self._uart_port = uart_port
        self._uart_baud = uart_baud

        self._gpio     = None   # RPi.GPIO module
        self._smbus    = None   # smbus2.SMBus instance
        self._spi      = None   # spidev.SpiDev instance
        self._serial   = None   # pyserial.Serial instance
        self._pwm_objs: Dict[int, Any] = {}   # board_pin → GPIO.PWM object
        self._model    = "unknown"

    # ── Connection ─────────────────────────────────────────────────────────
    def connect(self) -> None:
        self._gpio = _load_gpio()
        if self._gpio is None:
            raise HALError(
                "RPi.GPIO not found. Install: pip install RPi.GPIO\n"
                "If you're not on a Raspberry Pi, use SimulatorHAL instead."
            )
        self._model = _detect_pi_model()
        self._gpio.setmode(self._gpio.BCM)
        self._gpio.setwarnings(False)
        self._connected = True
        logger.info("[RPI HAL] connected | model=%s i2c_bus=%d", self._model, self._i2c_bus)

    def disconnect(self) -> None:
        # Stop all PWM objects
        for pwm in self._pwm_objs.values():
            try:
                pwm.stop()
            except Exception:
                pass
        if self._gpio:
            self._gpio.cleanup()
        if self._serial and self._serial.is_open:
            self._serial.close()
        if self._smbus:
            try:
                self._smbus.close()
            except Exception:
                pass
        self._connected = False
        logger.info("[RPI HAL] disconnected")

    # ── Pin operations ─────────────────────────────────────────────────────
    def _configure_pin(self, board_pin: int, mode: PinMode) -> None:
        GPIO = self._gpio
        mode_map = {
            PinMode.OUTPUT:         GPIO.OUT,
            PinMode.INPUT:          GPIO.IN,
            PinMode.INPUT_PULLUP:   GPIO.IN,
            PinMode.INPUT_PULLDOWN: GPIO.IN,
            PinMode.PWM:            GPIO.OUT,
            PinMode.ANALOG_IN:      GPIO.IN,   # Pi has no native ADC
            PinMode.ANALOG_OUT:     GPIO.OUT,
        }
        pud_map = {
            PinMode.INPUT_PULLUP:   GPIO.PUD_UP,
            PinMode.INPUT_PULLDOWN: GPIO.PUD_DOWN,
        }
        gpio_mode = mode_map.get(mode, GPIO.OUT)
        pud       = pud_map.get(mode, GPIO.PUD_OFF)
        GPIO.setup(board_pin, gpio_mode, pull_up_down=pud)
        logger.debug("[RPI HAL] setup pin=%d mode=%s", board_pin, mode.value)

    def _write_pin(self, board_pin: int, value: Any) -> None:
        if isinstance(value, float):
            # PWM duty cycle
            self.pwm_write(board_pin, value)
        else:
            v = GPIO = self._gpio
            GPIO.output(board_pin, bool(int(value)))

    def _read_pin(self, board_pin: int) -> Any:
        raw = self._gpio.input(board_pin)
        return PinState(raw)

    # ── PWM ────────────────────────────────────────────────────────────────
    def pwm_write(
        self,
        board_pin:  int,
        duty_cycle: float,
        *,
        freq_hz:    float = 50.0,
    ) -> None:
        duty_cycle = max(0.0, min(1.0, duty_cycle))
        duty_pct   = duty_cycle * 100.0

        if board_pin not in self._pwm_objs:
            # Create new PWM object
            self._gpio.setup(board_pin, self._gpio.OUT)
            pwm = self._gpio.PWM(board_pin, freq_hz)
            pwm.start(duty_pct)
            self._pwm_objs[board_pin] = pwm
            logger.debug("[RPI HAL] PWM started pin=%d freq=%.1f", board_pin, freq_hz)
        else:
            self._pwm_objs[board_pin].ChangeDutyCycle(duty_pct)

    # ── UART ───────────────────────────────────────────────────────────────
    def uart_write(self, data: bytes, *, port: int = 0) -> None:
        if self._serial is None:
            self._init_uart()
        self._serial.write(data)

    def uart_read(self, n_bytes: int = 1, *, port: int = 0) -> bytes:
        if self._serial is None:
            self._init_uart()
        return self._serial.read(n_bytes)

    def _init_uart(self) -> None:
        try:
            import serial
            self._serial = serial.Serial(
                self._uart_port, self._uart_baud, timeout=0.1
            )
            logger.info("[RPI HAL] UART opened %s @%d", self._uart_port, self._uart_baud)
        except Exception as e:
            raise HALError(f"UART init failed: {e}") from e

    # ── I2C ────────────────────────────────────────────────────────────────
    def i2c_write(self, address: int, register: int, data: bytes) -> None:
        bus = self._get_smbus()
        bus.write_i2c_block_data(address, register, list(data))

    def i2c_read(self, address: int, register: int, n_bytes: int) -> bytes:
        bus = self._get_smbus()
        raw = bus.read_i2c_block_data(address, register, n_bytes)
        return bytes(raw)

    def _get_smbus(self):
        if self._smbus is None:
            smbus2 = _load_smbus()
            if smbus2 is None:
                raise HALError("smbus2 not installed: pip install smbus2")
            self._smbus = smbus2.SMBus(self._i2c_bus)
        return self._smbus

    # ── System info ─────────────────────────────────────────────────────────
    def board_info(self) -> dict:
        return {
            "board":    self._model,
            "domain":   "B",
            "i2c_bus":  self._i2c_bus,
            "spi_bus":  self._spi_bus,
            "uart":     self._uart_port,
        }

    def get_cpu_temp(self) -> Optional[float]:
        """Read CPU temperature (Raspberry Pi specific)."""
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return int(f.read().strip()) / 1000.0
        except FileNotFoundError:
            return None
