"""NEUROS V3 — Heartbeat Monitor.

Continuously monitors connected hardware drivers. If a heartbeat
is missed, it triggers the Dead Man Switch / Emergency Stop.
"""

import logging
import threading
import time
from typing import Dict

from neuros.drivers.base import Driver

logger = logging.getLogger(__name__)

class HeartbeatMonitor:
    """Monitors device heartbeats and triggers emergency stops if missed."""

    def __init__(self, check_interval_s: float = 1.0, max_missed: int = 3) -> None:
        self.check_interval_s = check_interval_s
        self.max_missed = max_missed
        self._drivers: Dict[str, Driver] = {}
        self._missed_counts: Dict[str, int] = {}
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._monitor_thread: threading.Thread | None = None

    def register_driver(self, device_id: str, driver: Driver) -> None:
        """Add a driver to the heartbeat monitoring loop."""
        with self._lock:
            self._drivers[device_id] = driver
            self._missed_counts[device_id] = 0
            logger.info("Heartbeat monitoring started for %r", device_id)

    def unregister_driver(self, device_id: str) -> None:
        """Remove a driver from heartbeat monitoring."""
        with self._lock:
            self._drivers.pop(device_id, None)
            self._missed_counts.pop(device_id, None)

    def start(self) -> None:
        """Start the background monitoring thread."""
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            return
        
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Heartbeat monitor started")

    def stop(self) -> None:
        """Stop the background monitoring thread."""
        self._stop_event.set()
        if self._monitor_thread is not None:
            self._monitor_thread.join()
            self._monitor_thread = None
        logger.info("Heartbeat monitor stopped")

    def _monitor_loop(self) -> None:
        """Main loop that pings all registered drivers."""
        while not self._stop_event.is_set():
            with self._lock:
                for device_id, driver in list(self._drivers.items()):
                    try:
                        alive = driver.heartbeat()
                        if alive:
                            self._missed_counts[device_id] = 0
                        else:
                            self._handle_missed(device_id, driver)
                    except Exception as e:
                        logger.error("Error pinging %r: %s", device_id, e)
                        self._handle_missed(device_id, driver)
                        
            time.sleep(self.check_interval_s)

    def _handle_missed(self, device_id: str, driver: Driver) -> None:
        """Handle a missed heartbeat, triggering E-Stop if limit exceeded."""
        self._missed_counts[device_id] += 1
        missed = self._missed_counts[device_id]
        
        if missed >= self.max_missed:
            logger.critical("DEAD MAN SWITCH: Device %r missed %d heartbeats!", device_id, missed)
            self._trigger_emergency_stop(device_id, driver)
        else:
            logger.warning("Device %r missed heartbeat (%d/%d)", device_id, missed, self.max_missed)

    def _trigger_emergency_stop(self, device_id: str, driver: Driver) -> None:
        """Directly call the driver's emergency stop method."""
        try:
            driver.emergency_stop()
        except Exception as e:
            logger.error("Failed to emergency stop device %r: %s", device_id, e)
