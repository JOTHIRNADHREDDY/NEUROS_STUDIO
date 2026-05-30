"""NEUROS V2 — Device registry.

Maintains a thread-safe, in-memory registry of every hardware device
known to the system.  Supports YAML-based persistence so that device
configurations survive restarts and can be version-controlled alongside
the robot project.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

import yaml

from neuros.devices.types import Device, DeviceStatus, DeviceType

logger = logging.getLogger(__name__)

# Mapping from lowercase YAML string → DeviceType enum member.
_DEVICE_TYPE_MAP: dict[str, DeviceType] = {t.value: t for t in DeviceType}


class DeviceRegistry:
    """Central registry for hardware devices.

    All public methods are protected by a re-entrant lock so the
    registry can be shared safely across threads.
    """

    def __init__(self) -> None:
        self._devices: dict[str, Device] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def register(self, device: Device) -> None:
        """Register *device*.

        Raises
        ------
        ValueError
            If a device with the same ``id`` is already registered.
        """
        with self._lock:
            if device.id in self._devices:
                raise ValueError(
                    f"Device {device.id!r} is already registered"
                )
            self._devices[device.id] = device
            logger.info(
                "Registered device %r (type=%s, driver=%s)",
                device.id,
                device.device_type.value,
                device.driver,
            )

    def unregister(self, device_id: str) -> None:
        """Remove the device identified by *device_id*.

        Raises
        ------
        KeyError
            If no device with that ID exists.
        """
        with self._lock:
            if device_id not in self._devices:
                raise KeyError(f"Device {device_id!r} is not registered")
            del self._devices[device_id]
            logger.info("Unregistered device %r", device_id)

    def update_status(self, device_id: str, status: DeviceStatus) -> None:
        """Update the status of an already-registered device.

        Raises
        ------
        KeyError
            If the device is not registered.
        """
        with self._lock:
            device = self.get(device_id)
            old = device.status
            device.status = status
            logger.info(
                "Device %r status: %s → %s",
                device_id,
                old.value,
                status.value,
            )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, device_id: str) -> Device:
        """Return the :class:`Device` identified by *device_id*.

        Raises
        ------
        KeyError
            If the device is not registered.
        """
        with self._lock:
            try:
                return self._devices[device_id]
            except KeyError:
                raise KeyError(
                    f"Device {device_id!r} is not registered"
                ) from None

    def list_devices(self) -> list[Device]:
        """Return a list of **all** registered devices."""
        with self._lock:
            return list(self._devices.values())

    def list_by_type(self, device_type: DeviceType) -> list[Device]:
        """Return devices whose :attr:`device_type` matches *device_type*."""
        with self._lock:
            return [
                dev
                for dev in self._devices.values()
                if dev.device_type is device_type
            ]

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self) -> list[Device]:
        """Run auto-discovery and register any new devices found.

        Delegates to :meth:`DeviceDiscovery.auto_discover` and
        registers devices that are not already known.

        Returns
        -------
        list[Device]
            Newly discovered and registered devices.
        """
        from neuros.devices.discovery import DeviceDiscovery

        discovered = DeviceDiscovery.auto_discover()
        newly_registered: list[Device] = []
        for device in discovered:
            with self._lock:
                if device.id not in self._devices:
                    self.register(device)
                    newly_registered.append(device)
        logger.info(
            "Discovery complete — %d new device(s) registered",
            len(newly_registered),
        )
        return newly_registered

    # ------------------------------------------------------------------
    # YAML persistence
    # ------------------------------------------------------------------

    def load_from_yaml(self, path: str) -> None:
        """Load device definitions from a YAML file and register them.

        The YAML schema mirrors ``robot.yaml``: a top-level ``devices``
        mapping where each key is the device ID and each value is a
        dict with ``type``, ``driver``, and optional ``port``, ``pin``,
        ``pins``, ``i2c_address``, and ``capabilities`` fields.

        Parameters
        ----------
        path:
            Filesystem path to the YAML file.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Device YAML not found: {path}")

        with file_path.open("r", encoding="utf-8") as fh:
            data: dict[str, Any] = yaml.safe_load(fh) or {}

        devices_section: dict[str, Any] = data.get("devices", {})
        if not devices_section:
            logger.warning("No 'devices' section found in %s", path)
            return

        for dev_id, dev_data in devices_section.items():
            device = self._parse_device_entry(dev_id, dev_data)
            # Skip duplicates silently during bulk load.
            with self._lock:
                if device.id not in self._devices:
                    self.register(device)
                else:
                    logger.debug(
                        "Skipping duplicate device %r during YAML load",
                        device.id,
                    )

        logger.info("Loaded devices from %s", path)

    def to_yaml(self, path: str) -> None:
        """Persist the current registry contents to a YAML file.

        Parameters
        ----------
        path:
            Filesystem path to write.  Parent directories are created
            automatically.
        """
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        devices_dict: dict[str, dict[str, Any]] = {}
        with self._lock:
            for dev_id, dev in self._devices.items():
                entry: dict[str, Any] = {
                    "type": dev.device_type.value,
                    "driver": dev.driver,
                }
                if dev.port is not None:
                    entry["port"] = dev.port
                if dev.pin is not None:
                    entry["pin"] = dev.pin
                if dev.config:
                    # Flatten well-known keys for readability.
                    if "pins" in dev.config:
                        entry["pins"] = dev.config["pins"]
                    if "i2c_address" in dev.config:
                        entry["i2c_address"] = dev.config["i2c_address"]
                    # Store remaining config as-is.
                    extra = {
                        k: v
                        for k, v in dev.config.items()
                        if k not in ("pins", "i2c_address")
                    }
                    if extra:
                        entry["config"] = extra
                if dev.capabilities:
                    entry["capabilities"] = dev.capabilities
                devices_dict[dev_id] = entry

        payload: dict[str, Any] = {"devices": devices_dict}
        with file_path.open("w", encoding="utf-8") as fh:
            yaml.dump(
                payload, fh, default_flow_style=False, sort_keys=False
            )

        logger.info("Saved %d device(s) to %s", len(devices_dict), path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_device_entry(dev_id: str, data: dict[str, Any]) -> Device:
        """Convert a raw YAML dict into a :class:`Device` instance."""
        raw_type = str(data.get("type", "custom")).lower()
        device_type = _DEVICE_TYPE_MAP.get(raw_type, DeviceType.CUSTOM)

        driver: str = data.get("driver", "unknown")
        port: str | None = data.get("port")

        # Support both singular ``pin`` and plural ``pins``.
        pin: int | None = data.get("pin")
        config: dict[str, Any] = {}
        if "pins" in data:
            config["pins"] = data["pins"]
        if "i2c_address" in data:
            # Accept both ``0x68`` (int from YAML) and ``"0x68"`` (str).
            raw_addr = data["i2c_address"]
            config["i2c_address"] = (
                int(raw_addr, 16) if isinstance(raw_addr, str) else raw_addr
            )

        # Merge any extra keys into config.
        known_keys = {"type", "driver", "port", "pin", "pins",
                       "i2c_address", "capabilities", "name"}
        for key, value in data.items():
            if key not in known_keys:
                config[key] = value

        capabilities: list[str] = data.get("capabilities", [])
        name: str = data.get("name", dev_id.replace("_", " ").title())

        return Device(
            id=dev_id,
            name=name,
            device_type=device_type,
            driver=driver,
            port=port,
            pin=pin,
            config=config,
            status=DeviceStatus.UNKNOWN,
            capabilities=capabilities,
        )

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        with self._lock:
            return len(self._devices)

    def __contains__(self, device_id: str) -> bool:
        with self._lock:
            return device_id in self._devices

    def __repr__(self) -> str:
        with self._lock:
            ids = list(self._devices.keys())
        return f"DeviceRegistry(devices={ids})"
