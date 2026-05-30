"""
neuros.kernel.watchdog
======================
Standalone Watchdog — can be used independently of the full Kernel
for lightweight deployments (e.g. bare-metal Domain A without threading).

The Watchdog tracks named timers. Each call to `kick(name)` resets
the timer. If `timeout_s` elapses without a kick, the registered
callback fires.

Phase 1: software-only, monotonic-clock based.
Phase 2: will hook into hardware watchdog timer (WDT) on MCUs.
"""

from __future__ import annotations

import threading
import time
import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

logger = logging.getLogger("neuros.watchdog")


@dataclass
class WatchEntry:
    name:        str
    timeout_s:   float
    callback:    Callable[[str], None]
    last_kick:   float = field(default_factory=time.monotonic)
    fired:       bool  = False
    enabled:     bool  = True


class Watchdog:
    """
    Software watchdog timer.

    Usage
    -----
        def on_timeout(name):
            print(f"WATCHDOG: {name} timed out!")

        wd = Watchdog(poll_hz=100)
        wd.register("main_loop", timeout_s=0.5, callback=on_timeout)
        wd.start()

        # In your loop:
        wd.kick("main_loop")
    """

    def __init__(self, *, poll_hz: int = 100) -> None:
        self._poll_hz   = poll_hz
        self._entries:  Dict[str, WatchEntry] = {}
        self._lock      = threading.Lock()
        self._thread:   Optional[threading.Thread] = None
        self._stop      = threading.Event()

    def register(
        self,
        name:      str,
        timeout_s: float,
        callback:  Callable[[str], None],
    ) -> None:
        entry = WatchEntry(name=name, timeout_s=timeout_s, callback=callback)
        with self._lock:
            self._entries[name] = entry
        logger.debug("[WD] registered '%s' timeout=%.2fs", name, timeout_s)

    def unregister(self, name: str) -> None:
        with self._lock:
            self._entries.pop(name, None)

    def kick(self, name: str) -> None:
        """Reset the watchdog timer for `name`."""
        with self._lock:
            entry = self._entries.get(name)
        if entry:
            entry.last_kick = time.monotonic()
            entry.fired     = False

    def disable(self, name: str) -> None:
        with self._lock:
            if name in self._entries:
                self._entries[name].enabled = False

    def enable(self, name: str) -> None:
        with self._lock:
            if name in self._entries:
                entry          = self._entries[name]
                entry.enabled  = True
                entry.last_kick = time.monotonic()
                entry.fired    = False

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._poll_loop, name="neuros-watchdog", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def _poll_loop(self) -> None:
        period = 1.0 / self._poll_hz
        while not self._stop.is_set():
            now = time.monotonic()
            with self._lock:
                entries = list(self._entries.values())
            for e in entries:
                if not e.enabled or e.fired:
                    continue
                if now - e.last_kick > e.timeout_s:
                    e.fired = True
                    logger.warning("[WD] '%s' timed out after %.2fs", e.name, e.timeout_s)
                    try:
                        e.callback(e.name)
                    except Exception as exc:
                        logger.error("[WD] callback error for '%s': %s", e.name, exc)
            time.sleep(period)
