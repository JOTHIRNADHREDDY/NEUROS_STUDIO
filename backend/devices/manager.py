import logging

logger = logging.getLogger("neuros.devices")

class DeviceManager:
    """
    Device abstraction layer for managing connected hardware.
    """
    def __init__(self):
        self.registered_devices = {}

    def discover_devices(self):
        logger.info("Scanning for connected devices (ESP32, STM32, Jetson)...")
        # Mock discovery
        return [
            {"id": "dev_1", "type": "ESP32", "port": "COM3"},
            {"id": "dev_2", "type": "Generic_Serial", "port": "COM4"}
        ]
