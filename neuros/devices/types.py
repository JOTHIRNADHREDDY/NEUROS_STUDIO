"""NEUROS V2 — Device type definitions.

Defines the full vocabulary of device categories, lifecycle states, and
the ``Device`` dataclass that carries all metadata for a registered
hardware peripheral.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, unique


@unique
class DeviceType(Enum):
    """Category of a hardware peripheral managed by the device registry."""

    MOTOR = "motor"
    SERVO = "servo"
    CAMERA = "camera"
    LIDAR = "lidar"
    IMU = "imu"
    ULTRASONIC = "ultrasonic"
    ENCODER = "encoder"
    BATTERY_MONITOR = "battery_monitor"
    LED = "led"
    BUZZER = "buzzer"
    GPIO = "gpio"
    GRIPPER = "gripper"
    SPEAKER = "speaker"
    MICROPHONE = "microphone"
    CUSTOM = "custom"


@unique
class DeviceStatus(Enum):
    """Lifecycle / connection state of a device."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    INITIALIZING = "initializing"
    UNKNOWN = "unknown"


@dataclass
class Device:
    """Metadata record for a single hardware device.

    Parameters
    ----------
    id:
        Unique string identifier used throughout NEUROS to reference
        this device (e.g. ``"motor_left"``).
    name:
        Human-readable label shown in dashboards and logs.
    device_type:
        The broad category of this device.
    driver:
        Name of the HAL driver that controls this device
        (e.g. ``"bts7960"``, ``"usb_camera"``).
    port:
        Optional serial / device-file path (e.g. ``"/dev/ttyUSB0"``).
    pin:
        Optional single GPIO pin number.  For multi-pin devices, store
        pin mappings in :attr:`config`.
    config:
        Arbitrary driver-specific configuration (pin lists, baud rates,
        I2C addresses, calibration values, etc.).
    status:
        Current lifecycle state.  Defaults to ``UNKNOWN``.
    capabilities:
        List of capability names this device contributes to.  Used by
        :meth:`CapabilityRegistry.validate_requirements` to verify that
        all required hardware is present.
    """

    id: str
    name: str
    device_type: DeviceType
    driver: str
    port: str | None = None
    pin: int | None = None
    config: dict = field(default_factory=dict)
    status: DeviceStatus = DeviceStatus.UNKNOWN
    capabilities: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        """Return ``True`` if the device is in the CONNECTED state."""
        return self.status is DeviceStatus.CONNECTED

    def __str__(self) -> str:
        return (
            f"Device({self.id!r}, type={self.device_type.value}, "
            f"driver={self.driver!r}, status={self.status.value})"
        )
