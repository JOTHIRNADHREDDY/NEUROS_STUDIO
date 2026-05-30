"""NEUROS V2 — Device auto-discovery.

Provides static helper methods that probe the host for connected
hardware peripherals (serial ports, I2C devices, USB cameras).
Results are returned as lightweight dicts or :class:`Device` instances
suitable for immediate registration.

.. note::

   NEUROS is AI *middleware*, not an operating system.  Discovery
   methods rely on standard Linux / host OS APIs and do **not** touch
   real-time control loops.
"""

from __future__ import annotations

import logging
from typing import Any

from neuros.devices.types import Device, DeviceStatus, DeviceType

logger = logging.getLogger(__name__)


class DeviceDiscovery:
    """Collection of static methods for probing host hardware."""

    # ------------------------------------------------------------------
    # Serial ports
    # ------------------------------------------------------------------

    @staticmethod
    def scan_serial_ports() -> list[dict[str, Any]]:
        """List available serial/COM ports on the host.

        Returns a list of dicts, each containing ``port``, ``description``,
        and ``hwid`` keys.  Uses :mod:`serial.tools.list_ports` when
        available; returns an empty list otherwise.
        """
        try:
            from serial.tools.list_ports import comports
        except ImportError:
            logger.warning(
                "pyserial is not installed — serial port scan skipped"
            )
            return []

        ports: list[dict[str, Any]] = []
        for port_info in comports():
            ports.append(
                {
                    "port": port_info.device,
                    "description": port_info.description,
                    "hwid": port_info.hwid,
                }
            )
        logger.info("Serial scan found %d port(s)", len(ports))
        return ports

    # ------------------------------------------------------------------
    # I2C
    # ------------------------------------------------------------------

    @staticmethod
    def scan_i2c(bus_number: int = 1) -> list[int]:
        """Scan an I2C bus and return addresses of responding devices.

        Uses :mod:`smbus2` when available.  Returns an empty list on
        import failure or OS-level errors (e.g. running on Windows or
        macOS where ``/dev/i2c-*`` does not exist).

        Parameters
        ----------
        bus_number:
            I2C bus index (default ``1`` for Raspberry Pi).
        """
        try:
            from smbus2 import SMBus
        except ImportError:
            logger.warning(
                "smbus2 is not installed — I2C scan skipped"
            )
            return []

        addresses: list[int] = []
        try:
            with SMBus(bus_number) as bus:
                for addr in range(0x03, 0x78):
                    try:
                        bus.read_byte(addr)
                        addresses.append(addr)
                    except OSError:
                        continue
        except FileNotFoundError:
            logger.warning(
                "I2C bus /dev/i2c-%d not found — scan skipped",
                bus_number,
            )
        except Exception:
            logger.exception("Unexpected error during I2C scan")

        logger.info(
            "I2C bus %d scan found %d device(s): %s",
            bus_number,
            len(addresses),
            [hex(a) for a in addresses],
        )
        return addresses

    # ------------------------------------------------------------------
    # USB cameras
    # ------------------------------------------------------------------

    @staticmethod
    def scan_usb_cameras() -> list[dict[str, Any]]:
        """Detect available USB / V4L2 cameras.

        Attempts to open ``/dev/video{0..9}`` using OpenCV.  Falls back
        gracefully when OpenCV is not installed.

        Returns a list of dicts with ``index`` and ``port`` keys.
        """
        try:
            import cv2  # type: ignore[import-untyped]
        except ImportError:
            logger.warning(
                "opencv-python is not installed — camera scan skipped"
            )
            return []

        cameras: list[dict[str, Any]] = []
        for idx in range(10):
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                cameras.append(
                    {"index": idx, "port": f"/dev/video{idx}"}
                )
                cap.release()
        logger.info("Camera scan found %d camera(s)", len(cameras))
        return cameras

    # ------------------------------------------------------------------
    # Combined auto-discovery
    # ------------------------------------------------------------------

    @staticmethod
    def auto_discover() -> list[Device]:
        """Run all available scans and return candidate devices.

        Each discovered peripheral is wrapped in a :class:`Device`
        with status set to :attr:`DeviceStatus.INITIALIZING`.  The
        caller is responsible for verifying and registering them.
        """
        devices: list[Device] = []

        # --- Serial ports ---
        for port_info in DeviceDiscovery.scan_serial_ports():
            port: str = port_info["port"]
            dev = Device(
                id=f"serial_{port.replace('/', '_').replace('\\', '_').strip('_')}",
                name=f"Serial Device ({port})",
                device_type=DeviceType.CUSTOM,
                driver="auto_detected",
                port=port,
                config={"description": port_info.get("description", ""),
                        "hwid": port_info.get("hwid", "")},
                status=DeviceStatus.INITIALIZING,
            )
            devices.append(dev)

        # --- I2C devices ---
        for addr in DeviceDiscovery.scan_i2c():
            dev = Device(
                id=f"i2c_{addr:#04x}",
                name=f"I2C Device @ {addr:#04x}",
                device_type=DeviceType.CUSTOM,
                driver="auto_detected",
                config={"i2c_address": addr},
                status=DeviceStatus.INITIALIZING,
            )
            devices.append(dev)

        # --- USB cameras ---
        for cam_info in DeviceDiscovery.scan_usb_cameras():
            idx: int = cam_info["index"]
            dev = Device(
                id=f"camera_{idx}",
                name=f"USB Camera {idx}",
                device_type=DeviceType.CAMERA,
                driver="usb_camera",
                port=cam_info["port"],
                status=DeviceStatus.INITIALIZING,
            )
            devices.append(dev)

        logger.info(
            "Auto-discovery complete — %d candidate device(s)", len(devices)
        )
        return devices
