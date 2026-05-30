"""
neuros.kernel.rt.process_iso
=============================
Process Isolator — Phase 2, Domain B.

Why process isolation?
----------------------
In Phase 1, all nodes run in the same Python process. A crash in one
node can bring down all nodes. In Phase 2 Domain B we spawn each
"node group" as an isolated OS process.

Communication between processes uses:
  • Shared memory (fast path) — sensor data, control commands
  • Unix domain sockets (IPC bus bridge) — Neural Bus across processes
  • multiprocessing.Queue (fallback) — low-bandwidth config/status

Architecture
------------
  Main Process
  ├─ Kernel (supervisor)
  ├─ NeuralBus IPC bridge (Unix socket server)
  └─ NodeGroup processes (fork/spawn)
       ├─ GroupProcess A — sensor nodes (IMU, LiDAR, Camera)
       ├─ GroupProcess B — navigation nodes
       └─ GroupProcess C — actuator nodes

Phase 2: multiprocessing-based isolation (Python stdlib only).
Phase 4: will use Linux namespaces + cgroups for Domain C certification.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import os
import signal
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

logger = logging.getLogger("neuros.kernel.rt.process_iso")


@dataclass
class IsolatedProcess:
    """Descriptor for a managed subprocess."""
    name:         str
    target:       Callable
    args:         tuple         = field(default_factory=tuple)
    kwargs:       dict          = field(default_factory=dict)
    restart_on_crash: bool      = True
    max_restarts: int           = 3

    # Runtime state
    _proc:         Optional[mp.Process] = field(default=None, repr=False)
    _start_time:   float                = field(default=0.0, repr=False)
    _restart_count: int                 = field(default=0, repr=False)

    @property
    def pid(self) -> Optional[int]:
        return self._proc.pid if self._proc else None

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.is_alive()

    @property
    def uptime_s(self) -> float:
        return time.monotonic() - self._start_time if self._start_time else 0.0


class ProcessIsolator:
    """
    Manages a fleet of isolated subprocesses.

    Each subprocess runs a callable (typically a function that creates
    and spins up a set of NEUROS nodes).

    Usage
    -----
        isolator = ProcessIsolator()

        def run_sensor_group(bus_addr):
            from neuros import Robot
            r = Robot("sensors", board="rpi")
            r.add_node(IMUNode("imu", hz=1000))
            r.start()
            r.spin()

        proc = IsolatedProcess("sensors", target=run_sensor_group,
                               args=("/tmp/neuros.sock",))
        isolator.add(proc)
        isolator.start_all()
        isolator.monitor()   # blocks, auto-restarts crashed processes
    """

    MONITOR_INTERVAL_S = 0.5

    def __init__(self, *, start_method: str = "fork") -> None:
        try:
            mp.set_start_method(start_method, force=False)
        except RuntimeError:
            pass   # Already set
        self._processes: Dict[str, IsolatedProcess] = {}
        self._running = False

    def add(self, proc: IsolatedProcess) -> None:
        self._processes[proc.name] = proc
        logger.debug("[ISOLATOR] registered process '%s'", proc.name)

    def remove(self, name: str) -> None:
        proc = self._processes.pop(name, None)
        if proc and proc.alive:
            self.stop_process(name)

    def start_all(self) -> None:
        for name in self._processes:
            self._spawn(name)
        self._running = True
        logger.info("[ISOLATOR] started %d processes", len(self._processes))

    def stop_all(self, *, timeout_s: float = 5.0) -> None:
        self._running = False
        for name in list(self._processes):
            self.stop_process(name, timeout_s=timeout_s)
        logger.info("[ISOLATOR] all processes stopped")

    def stop_process(self, name: str, *, timeout_s: float = 5.0) -> None:
        iso = self._processes.get(name)
        if not iso or not iso._proc:
            return
        logger.info("[ISOLATOR] stopping '%s' (pid=%s)", name, iso.pid)
        iso._proc.terminate()
        iso._proc.join(timeout=timeout_s)
        if iso._proc.is_alive():
            logger.warning("[ISOLATOR] SIGKILL '%s'", name)
            iso._proc.kill()
            iso._proc.join(1.0)

    def monitor(self, *, once: bool = False) -> None:
        """
        Monitor subprocess health. Auto-restart crashed processes.
        Call this in the main thread. Use `once=True` for a single scan.
        """
        while self._running:
            for name, iso in list(self._processes.items()):
                if not iso.alive:
                    exit_code = iso._proc.exitcode if iso._proc else None
                    logger.warning(
                        "[ISOLATOR] process '%s' exited (code=%s)", name, exit_code
                    )
                    if iso.restart_on_crash and iso._restart_count < iso.max_restarts:
                        logger.info("[ISOLATOR] restarting '%s' (attempt %d/%d)",
                                    name, iso._restart_count + 1, iso.max_restarts)
                        iso._restart_count += 1
                        self._spawn(name)
                    else:
                        logger.error(
                            "[ISOLATOR] '%s' exceeded max_restarts=%d — abandoned",
                            name, iso.max_restarts,
                        )
            if once:
                return
            time.sleep(self.MONITOR_INTERVAL_S)

    def status(self) -> Dict[str, dict]:
        return {
            name: {
                "alive":          iso.alive,
                "pid":            iso.pid,
                "uptime_s":       round(iso.uptime_s, 1),
                "restart_count":  iso._restart_count,
            }
            for name, iso in self._processes.items()
        }

    def _spawn(self, name: str) -> None:
        iso = self._processes[name]
        proc = mp.Process(
            target=iso.target,
            args=iso.args,
            kwargs=iso.kwargs,
            name=f"neuros-{name}",
            daemon=True,
        )
        proc.start()
        iso._proc       = proc
        iso._start_time = time.monotonic()
        logger.info("[ISOLATOR] spawned '%s' pid=%d", name, proc.pid)
