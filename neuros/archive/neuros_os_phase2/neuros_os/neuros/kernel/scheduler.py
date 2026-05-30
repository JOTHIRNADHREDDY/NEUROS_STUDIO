"""
neuros.kernel.scheduler
=======================
Cooperative task scheduler — Phase 1.

Manages periodic callbacks at declared rates.
Phase 1 : threading-based, soft real-time.
Phase 2 : will be backed by PREEMPT-RT SCHED_FIFO.
Phase 4 : QNX pulse-based hard-RT scheduler.

Design note
-----------
Each task declares its desired period (Hz).  The scheduler runs a
single driver thread and dispatches tasks whose deadlines have elapsed.
Tasks that overrun their window emit a warning; repeated overruns
increment the `overrun_count` metric.
"""

from __future__ import annotations

import threading
import time
import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

logger = logging.getLogger("neuros.scheduler")


@dataclass
class Task:
    name:         str
    callback:     Callable[[], None]
    hz:           float
    priority:     int   = 50          # 0 = lowest, 100 = highest
    overrun_count: int  = 0
    call_count:   int   = 0
    _next_deadline: float = field(default_factory=time.monotonic)

    @property
    def period_s(self) -> float:
        return 1.0 / self.hz


class Scheduler:
    """
    Soft real-time cooperative scheduler.

    Usage
    -----
        sched = Scheduler(driver_hz=10_000)
        sched.add("imu_read",  callback=read_imu,  hz=1000, priority=90)
        sched.add("nav_update", callback=update_nav, hz=100,  priority=70)
        sched.add("telemetry", callback=send_telem, hz=10,   priority=30)
        sched.start()
        ...
        sched.stop()
    """

    OVERRUN_WARN_FACTOR = 1.5   # warn if task takes > 1.5× its period

    def __init__(self, *, driver_hz: int = 10_000) -> None:
        self._driver_hz  = driver_hz
        self._tasks: Dict[str, Task] = {}
        self._lock       = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop       = threading.Event()

    # ── Task management ────────────────────────────────────────────────────
    def add(
        self,
        name:     str,
        callback: Callable[[], None],
        *,
        hz:       float,
        priority: int = 50,
    ) -> None:
        task = Task(name=name, callback=callback, hz=hz, priority=priority)
        task._next_deadline = time.monotonic()
        with self._lock:
            self._tasks[name] = task
        logger.debug("[SCHED] added task='%s' hz=%.1f prio=%d", name, hz, priority)

    def remove(self, name: str) -> None:
        with self._lock:
            self._tasks.pop(name, None)

    # ── Lifecycle ──────────────────────────────────────────────────────────
    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._driver_loop, name="neuros-scheduler", daemon=True
        )
        self._thread.start()
        logger.info("[SCHED] started driver_hz=%d", self._driver_hz)

    def stop(self, *, timeout_s: float = 2.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout_s)
        logger.info("[SCHED] stopped")

    # ── Driver loop ────────────────────────────────────────────────────────
    def _driver_loop(self) -> None:
        period = 1.0 / self._driver_hz
        while not self._stop.is_set():
            now = time.monotonic()

            with self._lock:
                # Sort by priority (highest first) among due tasks
                due: List[Task] = sorted(
                    [t for t in self._tasks.values() if now >= t._next_deadline],
                    key=lambda t: -t.priority,
                )

            for task in due:
                t0 = time.monotonic()
                try:
                    task.callback()
                except Exception as exc:
                    logger.error("[SCHED] task='%s' raised: %s", task.name, exc)
                elapsed = time.monotonic() - t0
                task.call_count += 1
                task._next_deadline += task.period_s

                if elapsed > task.period_s * self.OVERRUN_WARN_FACTOR:
                    task.overrun_count += 1
                    logger.warning(
                        "[SCHED] task='%s' overran by %.1f ms (budget=%.1f ms)",
                        task.name,
                        (elapsed - task.period_s) * 1000,
                        task.period_s * 1000,
                    )

            time.sleep(period)

    # ── Introspection ──────────────────────────────────────────────────────
    def metrics(self) -> dict:
        with self._lock:
            return {
                name: {
                    "hz":           t.hz,
                    "priority":     t.priority,
                    "call_count":   t.call_count,
                    "overrun_count": t.overrun_count,
                }
                for name, t in self._tasks.items()
            }
