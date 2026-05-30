"""
neuros.hal.drivers.arduino
===========================
Arduino HAL — Domain A.

Communication: NEUROS Serial Protocol (NSP) over USB-Serial.
The Arduino-side firmware (`neuros-arduino-firmware`) runs as
a lightweight agent that translates NSP commands to hardware ops.

NSP wire format (v1)
----------------------
Command frames (host → Arduino):
    [START: 0xAA] [CMD_TYPE: 1B] [PIN: 1B] [VALUE: 2B] [CRC8: 1B] [END: 0x55]

Response frames (Arduino → host):
    [START: 0xAA] [STATUS: 1B] [DATA: 2B] [CRC8: 1B] [END: 0x55]

CMD_TYPE values
---------------
  0x01  PIN_MODE     (pin, mode)
  0x02  DIGITAL_WRITE (pin, value)
  0x03  DIGITAL_READ  (pin, _)    → returns 0/1
  0x04  ANALOG_WRITE  (pin, duty 0-255)
  0x05  ANALOG_READ   (pin, _)    → returns 10-bit ADC value
  0x06  PWM_WRITE     (pin, duty 0-255)
  0x07  UART_WRITE    (port, len) + payload
  0x08  UART_READ     (port, n)   → returns bytes
  0x09  I2C_WRITE     (addr, reg) + data
  0x0A  I2C_READ      (addr, reg) → returns bytes
  0x0F  BOARD_INFO    (_, _)      → returns JSON

Phase 1 implementation
-----------------------
This class communicates over `pyserial`. The firmware must be flashed
separately from the `neuros-firmware` package:
    neuros flash --board=arduino --port=/dev/ttyUSB0

For development without hardware, use SimulatorHAL instead.
Auto-detection falls back to SimulatorHAL if pyserial or the Arduino
is not available.
"""

from __future__ import annotations

import logging
import struct
import time
from typing import Any, Optional

from neuros.hal.base import HAL, HALError, PinMode, PinState

logger = logging.getLogger("neuros.hal.arduino")

# NSP byte constants
_START  = 0xAA
_END    = 0x55
_CMD_PIN_MODE      = 0x01
_CMD_DIG_WRITE     = 0x02
_CMD_DIG_READ      = 0x03
_CMD_ANA_WRITE     = 0x04
_CMD_ANA_READ      = 0x05
_CMD_PWM_WRITE     = 0x06
_CMD_I2C_WRITE     = 0x09
_CMD_I2C_READ      = 0x0A
_CMD_BOARD_INFO    = 0x0F

_MODE_MAP = {
    PinMode.INPUT:          0x00,
    PinMode.OUTPUT:         0x01,
    PinMode.INPUT_PULLUP:   0x02,
    PinMode.INPUT_PULLDOWN: 0x03,
    PinMode.PWM:            0x04,
    PinMode.ANALOG_IN:      0x05,
    PinMode.ANALOG_OUT:     0x06,
}


def _crc8(data: bytes) -> int:
    """Dallas/Maxim CRC-8 used in NSP frames."""
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x31) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


class ArduinoHAL(HAL):
    """
    Hardware driver for Arduino-family boards over USB serial.

    Parameters
    ----------
    port     : serial port path (e.g. '/dev/ttyUSB0', 'COM3')
    baud     : baud rate (default 115200)
    timeout  : read timeout in seconds
    """

    FRAME_SIZE = 7   # bytes

    def __init__(
        self,
        port:    str   = "/dev/ttyUSB0",
        baud:    int   = 115_200,
        *,
        timeout: float = 0.1,
    ) -> None:
        super().__init__(name="arduino")
        self._port    = port
        self._baud    = baud
        self._timeout = timeout
        self._serial  = None   # pyserial Serial instance

    # ── Connection ─────────────────────────────────────────────────────────
    def connect(self) -> None:
        try:
            import serial  # pyserial
        except ImportError:
            raise HALError(
                "pyserial is required for ArduinoHAL. "
                "Run: pip install pyserial"
            )
        try:
            self._serial = serial.Serial(
                self._port, self._baud, timeout=self._timeout
            )
            time.sleep(2.0)   # Arduino bootloader reset time
            self._connected = True
            logger.info("[ARDUINO HAL] connected port=%s baud=%d", self._port, self._baud)
        except serial.SerialException as e:
            raise HALError(f"Failed to open Arduino on {self._port}: {e}") from e

    def disconnect(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._connected = False
        logger.info("[ARDUINO HAL] disconnected")

    # ── Frame encode / decode ──────────────────────────────────────────────
    def _encode(self, cmd: int, pin: int, value: int) -> bytes:
        payload = bytes([cmd, pin]) + struct.pack(">H", value & 0xFFFF)
        crc     = _crc8(payload)
        return bytes([_START]) + payload + bytes([crc, _END])

    def _send_recv(self, frame: bytes) -> Optional[bytes]:
        if not self._serial or not self._serial.is_open:
            raise HALError("Arduino not connected.")
        self._serial.write(frame)
        resp = self._serial.read(self.FRAME_SIZE)
        if len(resp) < self.FRAME_SIZE:
            raise HALError(f"Short response: got {len(resp)} bytes, expected {self.FRAME_SIZE}")
        if resp[0] != _START or resp[-1] != _END:
            raise HALError("Invalid frame markers in response.")
        crc_calc = _crc8(resp[1:-2])
        if crc_calc != resp[-2]:
            raise HALError(f"CRC mismatch: {crc_calc:#x} vs {resp[-2]:#x}")
        return resp

    # ── HAL abstract implementations ───────────────────────────────────────
    def _configure_pin(self, board_pin: int, mode: PinMode) -> None:
        frame = self._encode(_CMD_PIN_MODE, board_pin, _MODE_MAP[mode])
        self._send_recv(frame)
        logger.debug("[ARDUINO HAL] pin %d → mode %s", board_pin, mode.value)

    def _write_pin(self, board_pin: int, value: Any) -> None:
        if isinstance(value, float):
            # Analog / PWM — map 0.0–1.0 → 0–255
            duty = int(value * 255) & 0xFF
            frame = self._encode(_CMD_ANA_WRITE, board_pin, duty)
        else:
            v = int(value) & 0x01
            frame = self._encode(_CMD_DIG_WRITE, board_pin, v)
        self._send_recv(frame)

    def _read_pin(self, board_pin: int) -> Any:
        mode = self._pin_modes.get(
            next((k for k, v in self._pin_map.items() if v == board_pin), ""),
            PinMode.INPUT,
        )
        if mode == PinMode.ANALOG_IN:
            frame = self._encode(_CMD_ANA_READ, board_pin, 0)
            resp  = self._send_recv(frame)
            return struct.unpack(">H", resp[2:4])[0] / 1023.0   # normalised 0–1
        frame = self._encode(_CMD_DIG_READ, board_pin, 0)
        resp  = self._send_recv(frame)
        return PinState(resp[2] & 0x01)

    def uart_write(self, data: bytes, *, port: int = 0) -> None:
        # For Phase 1, piggyback on the same serial connection
        if self._serial:
            self._serial.write(data)

    def uart_read(self, n_bytes: int = 1, *, port: int = 0) -> bytes:
        if self._serial:
            return self._serial.read(n_bytes)
        return b""

    def i2c_write(self, address: int, register: int, data: bytes) -> None:
        # Phase 1 stub — full I2C bridge in firmware v2
        logger.debug("[ARDUINO HAL] i2c_write addr=0x%02X reg=0x%02X data=%s", address, register, data.hex())

    def i2c_read(self, address: int, register: int, n_bytes: int) -> bytes:
        logger.debug("[ARDUINO HAL] i2c_read addr=0x%02X reg=0x%02X n=%d", address, register, n_bytes)
        return bytes(n_bytes)

    def pwm_write(self, board_pin: int, duty_cycle: float, *, freq_hz: float = 50.0) -> None:
        duty = int(duty_cycle * 255) & 0xFF
        frame = self._encode(_CMD_PWM_WRITE, board_pin, duty)
        self._send_recv(frame)

    def board_info(self) -> dict:
        # Simplified — full JSON response in firmware v2
        return {
            "board":   "Arduino (NSP v1)",
            "port":    self._port,
            "baud":    self._baud,
            "domain":  "A",
        }
