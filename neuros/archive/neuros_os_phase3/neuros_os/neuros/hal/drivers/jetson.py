"""
neuros.hal.drivers.jetson
==========================
NVIDIA Jetson HAL — Phase 2, Domain B.

Supports: Jetson Nano, Jetson Orin Nano, Jetson AGX Orin, Jetson Xavier NX.

Key differences from RaspberryPiHAL
-------------------------------------
  • Jetson uses Jetson.GPIO (pin-compatible with RPi.GPIO API)
  • Hardware has dedicated GPU — enables on-device inference (TensorRT)
  • Jetson AGX Orin supports hardware RT scheduling (GPC pre-emption)
  • CUDA streams available for camera processing nodes

Board detection
---------------
  Reads /proc/device-tree/model for "NVIDIA Jetson"
  Falls back to checking for /usr/lib/aarch64-linux-gnu/tegra/

GPU capabilities
----------------
  self.hal.cuda_available()  → bool
  self.hal.gpu_memory_mb()   → int
  self.hal.tensor_rt_engine(model_path) → TensorRT engine handle

Install
-------
  pip install Jetson.GPIO
  (CUDA/TensorRT provided by JetPack SDK)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from neuros.hal.base import HAL, HALError, PinMode, PinState

logger = logging.getLogger("neuros.hal.jetson")


def _detect_jetson_model() -> Optional[str]:
    try:
        with open("/proc/device-tree/model") as f:
            model = f.read().strip().rstrip("\x00")
            if "Jetson" in model or "NVIDIA" in model:
                return model
    except FileNotFoundError:
        pass
    if os.path.exists("/usr/lib/aarch64-linux-gnu/tegra/"):
        return "NVIDIA Jetson (Tegra)"
    return None


class JetsonHAL(HAL):
    """
    NVIDIA Jetson Hardware Abstraction Layer.

    Wraps Jetson.GPIO (same API as RPi.GPIO) and adds
    GPU/CUDA introspection for the AI Core layer.

    Parameters
    ----------
    i2c_bus   : I2C bus (default 1)
    uart_port : UART device (default /dev/ttyTHS1 — Jetson UART)

    Example
    -------
        hal = JetsonHAL()
        hal.connect()
        hal.pin("LED", board_pin=7, mode=PinMode.OUTPUT)
        print(hal.gpu_memory_mb())   # → 8192 (Jetson AGX Orin 8GB)
    """

    def __init__(
        self,
        *,
        i2c_bus:   int = 1,
        uart_port: str = "/dev/ttyTHS1",
        uart_baud: int = 115_200,
    ) -> None:
        super().__init__(name="jetson")
        self._i2c_bus   = i2c_bus
        self._uart_port = uart_port
        self._uart_baud = uart_baud
        self._gpio      = None
        self._smbus     = None
        self._serial    = None
        self._pwm_objs: Dict[int, Any] = {}
        self._model     = "NVIDIA Jetson (unknown)"

    # ── Connection ─────────────────────────────────────────────────────────
    def connect(self) -> None:
        try:
            import Jetson.GPIO as GPIO
            self._gpio = GPIO
        except ImportError:
            # Try RPi.GPIO as fallback (same API)
            try:
                import RPi.GPIO as GPIO
                self._gpio = GPIO
                logger.warning("[JETSON HAL] Jetson.GPIO not found, using RPi.GPIO")
            except ImportError:
                raise HALError(
                    "Jetson.GPIO not found. Install: pip install Jetson.GPIO\n"
                    "Or use SimulatorHAL for development without hardware."
                )

        self._model = _detect_jetson_model() or "NVIDIA Jetson"
        self._gpio.setmode(self._gpio.BCM)
        self._gpio.setwarnings(False)
        self._connected = True
        logger.info("[JETSON HAL] connected | model=%s cuda=%s gpu_mem=%sMB",
                    self._model, self.cuda_available(), self.gpu_memory_mb())

    def disconnect(self) -> None:
        for pwm in self._pwm_objs.values():
            try: pwm.stop()
            except Exception: pass
        if self._gpio:
            self._gpio.cleanup()
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._connected = False
        logger.info("[JETSON HAL] disconnected")

    # ── GPIO (same as RPi) ─────────────────────────────────────────────────
    def _configure_pin(self, board_pin: int, mode: PinMode) -> None:
        GPIO = self._gpio
        mode_map = {
            PinMode.OUTPUT:         GPIO.OUT,
            PinMode.INPUT:          GPIO.IN,
            PinMode.INPUT_PULLUP:   GPIO.IN,
            PinMode.INPUT_PULLDOWN: GPIO.IN,
            PinMode.PWM:            GPIO.OUT,
        }
        pud_map = {
            PinMode.INPUT_PULLUP:   getattr(GPIO, "PUD_UP",   None),
            PinMode.INPUT_PULLDOWN: getattr(GPIO, "PUD_DOWN", None),
        }
        gpio_dir = mode_map.get(mode, GPIO.OUT)
        pud      = pud_map.get(mode)
        if pud:
            GPIO.setup(board_pin, gpio_dir, pull_up_down=pud)
        else:
            GPIO.setup(board_pin, gpio_dir)

    def _write_pin(self, board_pin: int, value: Any) -> None:
        if isinstance(value, float):
            self.pwm_write(board_pin, value)
        else:
            self._gpio.output(board_pin, bool(int(value)))

    def _read_pin(self, board_pin: int) -> Any:
        return PinState(self._gpio.input(board_pin))

    def pwm_write(self, board_pin: int, duty_cycle: float, *, freq_hz: float = 50.0) -> None:
        duty_pct = max(0.0, min(100.0, duty_cycle * 100.0))
        if board_pin not in self._pwm_objs:
            self._gpio.setup(board_pin, self._gpio.OUT)
            pwm = self._gpio.PWM(board_pin, freq_hz)
            pwm.start(duty_pct)
            self._pwm_objs[board_pin] = pwm
        else:
            self._pwm_objs[board_pin].ChangeDutyCycle(duty_pct)

    def uart_write(self, data: bytes, *, port: int = 0) -> None:
        self._ensure_uart()
        self._serial.write(data)

    def uart_read(self, n_bytes: int = 1, *, port: int = 0) -> bytes:
        self._ensure_uart()
        return self._serial.read(n_bytes)

    def _ensure_uart(self) -> None:
        if self._serial is None:
            try:
                import serial
                self._serial = serial.Serial(self._uart_port, self._uart_baud, timeout=0.1)
            except Exception as e:
                raise HALError(f"Jetson UART init failed: {e}") from e

    def i2c_write(self, address: int, register: int, data: bytes) -> None:
        bus = self._get_smbus()
        bus.write_i2c_block_data(address, register, list(data))

    def i2c_read(self, address: int, register: int, n_bytes: int) -> bytes:
        return bytes(self._get_smbus().read_i2c_block_data(address, register, n_bytes))

    def _get_smbus(self):
        if self._smbus is None:
            try:
                import smbus2
                self._smbus = smbus2.SMBus(self._i2c_bus)
            except ImportError:
                raise HALError("smbus2 not installed: pip install smbus2")
        return self._smbus

    # ── GPU / CUDA introspection ───────────────────────────────────────────
    def cuda_available(self) -> bool:
        """Check if CUDA is available on this Jetson."""
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=2.0,
            )
            return result.returncode == 0
        except Exception:
            return os.path.exists("/dev/nvhost-ctrl")

    def gpu_memory_mb(self) -> Optional[int]:
        """Return total GPU memory in MB."""
        try:
            with open("/sys/kernel/debug/nvmap/iovmm/maps") as f:
                # Jetson unified memory — read from tegra stats
                pass
        except Exception:
            pass
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2.0,
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except Exception:
            pass
        return None

    def board_info(self) -> dict:
        return {
            "board":        self._model,
            "domain":       "B",
            "cuda":         self.cuda_available(),
            "gpu_memory_mb": self.gpu_memory_mb(),
            "i2c_bus":      self._i2c_bus,
        }
