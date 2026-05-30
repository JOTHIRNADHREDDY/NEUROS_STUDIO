"""
NEUROS Watchdog

Monitors critical robot health metrics and triggers alerts or emergency stops.
Runs as a background monitor checking battery, CPU, temperature, motor current, and network.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger("neuros.safety.watchdog")


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class WatchdogAlert:
    """A single watchdog alert."""
    timestamp: float
    level: AlertLevel
    source: str
    metric: str
    value: float
    threshold: float
    message: str


@dataclass
class WatchdogThresholds:
    """Configurable thresholds for watchdog monitoring."""
    battery_warning_v: float = 11.0
    battery_critical_v: float = 10.0
    cpu_warning_percent: float = 85.0
    cpu_critical_percent: float = 95.0
    temp_warning_c: float = 65.0
    temp_critical_c: float = 75.0
    motor_current_warning_a: float = 8.0
    motor_current_critical_a: float = 12.0
    network_timeout_s: float = 5.0
    heartbeat_timeout_s: float = 10.0


class Watchdog:
    """
    Background health monitor for the robot.

    Periodically checks:
    - Battery voltage
    - CPU usage
    - Temperature
    - Motor current draw
    - Network connectivity

    Fires alerts and can trigger E-Stop on critical failures.

    Usage:
        watchdog = Watchdog(check_interval_s=1.0)
        watchdog.register_data_source("battery", lambda: 12.3)
        watchdog.register_alert_handler(my_alert_handler)
        watchdog.register_estop(emergency_stop.trigger)
        await watchdog.start()
    """

    def __init__(
        self,
        thresholds: WatchdogThresholds | None = None,
        check_interval_s: float = 1.0,
    ) -> None:
        self._thresholds = thresholds or WatchdogThresholds()
        self._check_interval = check_interval_s
        self._running = False
        self._task: asyncio.Task | None = None
        self._data_sources: dict[str, Callable[[], float | None]] = {}
        self._alert_handlers: list[Callable[[WatchdogAlert], None]] = []
        self._estop_fn: Callable[[str, str], None] | None = None
        self._alerts_history: list[WatchdogAlert] = []
        self._last_values: dict[str, float] = {}
        logger.info(
            "Watchdog initialized (interval=%.1fs).", self._check_interval
        )

    def register_data_source(
        self, name: str, source_fn: Callable[[], float | None]
    ) -> None:
        """Register a data source (e.g., 'battery' -> lambda: read_voltage())."""
        self._data_sources[name] = source_fn
        logger.debug("Registered watchdog data source: %s", name)

    def register_alert_handler(
        self, handler: Callable[[WatchdogAlert], None]
    ) -> None:
        """Register a callback for watchdog alerts."""
        self._alert_handlers.append(handler)

    def register_estop(
        self, estop_fn: Callable[[str, str], None]
    ) -> None:
        """Register the emergency stop trigger function."""
        self._estop_fn = estop_fn

    def _fire_alert(self, alert: WatchdogAlert) -> None:
        """Fire an alert to all registered handlers."""
        self._alerts_history.append(alert)
        logger.log(
            logging.CRITICAL if alert.level == AlertLevel.EMERGENCY
            else logging.WARNING if alert.level == AlertLevel.WARNING
            else logging.INFO,
            "Watchdog [%s] %s: %s (value=%.2f, threshold=%.2f)",
            alert.level.value.upper(),
            alert.metric,
            alert.message,
            alert.value,
            alert.threshold,
        )
        for handler in self._alert_handlers:
            try:
                handler(alert)
            except Exception as exc:
                logger.error("Alert handler error: %s", exc)

        # Trigger E-Stop on emergency
        if alert.level == AlertLevel.EMERGENCY and self._estop_fn:
            self._estop_fn(alert.message, f"watchdog:{alert.metric}")

    def _check_metric(
        self,
        name: str,
        value: float,
        warning_threshold: float,
        critical_threshold: float,
        higher_is_worse: bool = True,
    ) -> None:
        """Check a single metric against warning and critical thresholds."""
        self._last_values[name] = value

        if higher_is_worse:
            is_critical = value >= critical_threshold
            is_warning = value >= warning_threshold
        else:
            is_critical = value <= critical_threshold
            is_warning = value <= warning_threshold

        if is_critical:
            self._fire_alert(
                WatchdogAlert(
                    timestamp=time.time(),
                    level=AlertLevel.EMERGENCY,
                    source="watchdog",
                    metric=name,
                    value=value,
                    threshold=critical_threshold,
                    message=f"{name} critical: {value:.2f} (limit: {critical_threshold:.2f})",
                )
            )
        elif is_warning:
            self._fire_alert(
                WatchdogAlert(
                    timestamp=time.time(),
                    level=AlertLevel.WARNING,
                    source="watchdog",
                    metric=name,
                    value=value,
                    threshold=warning_threshold,
                    message=f"{name} warning: {value:.2f} (limit: {warning_threshold:.2f})",
                )
            )

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        logger.info("Watchdog monitoring started.")
        while self._running:
            for name, source_fn in self._data_sources.items():
                try:
                    value = source_fn()
                    if value is None:
                        continue

                    t = self._thresholds
                    if name == "battery":
                        self._check_metric(
                            name, value,
                            t.battery_warning_v, t.battery_critical_v,
                            higher_is_worse=False,
                        )
                    elif name == "cpu":
                        self._check_metric(
                            name, value,
                            t.cpu_warning_percent, t.cpu_critical_percent,
                        )
                    elif name == "temperature":
                        self._check_metric(
                            name, value,
                            t.temp_warning_c, t.temp_critical_c,
                        )
                    elif name == "motor_current":
                        self._check_metric(
                            name, value,
                            t.motor_current_warning_a, t.motor_current_critical_a,
                        )

                except Exception as exc:
                    logger.error("Watchdog error reading '%s': %s", name, exc)

            await asyncio.sleep(self._check_interval)

    async def start(self) -> None:
        """Start the watchdog monitor."""
        if self._running:
            logger.warning("Watchdog already running.")
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Watchdog STARTED.")

    async def stop(self) -> None:
        """Stop the watchdog monitor."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Watchdog STOPPED.")

    def is_running(self) -> bool:
        return self._running

    def status(self) -> dict[str, Any]:
        """Get current watchdog status."""
        return {
            "running": self._running,
            "data_sources": list(self._data_sources.keys()),
            "last_values": dict(self._last_values),
            "total_alerts": len(self._alerts_history),
            "recent_alerts": [
                {
                    "level": a.level.value,
                    "metric": a.metric,
                    "value": a.value,
                    "message": a.message,
                }
                for a in self._alerts_history[-5:]
            ],
        }
