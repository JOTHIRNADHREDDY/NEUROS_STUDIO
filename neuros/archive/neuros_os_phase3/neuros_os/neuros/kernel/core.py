"""
neuros.kernel.core
==================
The NEUROS Kernel — Phase 1 implementation.

Responsibilities
----------------
  • Node lifecycle     register / activate / suspend / terminate
  • Health watchdog    heartbeat monitoring, auto-restart on failure
  • Resource allocator CPU/memory budget per node
  • Safety supervisor  emergency-stop propagation (stub, wired in Phase 4)
  • Metrics collector  per-node timing, error rates

Thread model (Phase 1)
-----------------------
  Kernel runs a single daemon thread at kernel_hz (default 1000 Hz).
  Nodes are run in the calling thread unless asyncio is used.
  Phase 2 will add process isolation per domain.

Domain flag
-----------
  DOMAIN_A  — Zephyr / Arduino / MCU  (this phase, soft-RT only)
  DOMAIN_B  — Linux RT + ROS2         (Phase 2)
  DOMAIN_C  — QNX Certified           (Phase 4+)
"""

from __future__ import annotations

import threading
import time
import logging
import enum
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from neuros.nodes.base import Node

logger = logging.getLogger("neuros.kernel")


# ── Domain enum ────────────────────────────────────────────────────────────
class Domain(enum.Enum):
    A = "A"   # Zephyr / MCU / Arduino
    B = "B"   # Linux RT / ROS2
    C = "C"   # QNX Certified / safety-critical


# ── Kernel state ───────────────────────────────────────────────────────────
class KernelState(enum.Enum):
    INIT        = "INIT"
    RUNNING     = "RUNNING"
    EMERGENCY   = "EMERGENCY"
    SHUTDOWN    = "SHUTDOWN"


# ── Per-node record inside kernel ──────────────────────────────────────────
@dataclass
class NodeRecord:
    node:           "Node"
    node_id:        str            = field(default_factory=lambda: str(uuid.uuid4())[:8])
    last_heartbeat: float          = field(default_factory=time.monotonic)
    error_count:    int            = 0
    restart_count:  int            = 0
    cpu_budget_ms:  float          = 10.0   # max allowed time per tick
    alive:          bool           = True


# ── NEUROS Kernel ──────────────────────────────────────────────────────────
class Kernel:
    """
    Central kernel of NEUROS OS.

    Usage
    -----
        kernel = Kernel(domain=Domain.A, kernel_hz=1000)
        kernel.register(my_node)
        kernel.start()
        ...
        kernel.shutdown()
    """

    # Watchdog: node is considered hung if no heartbeat for this many seconds
    WATCHDOG_TIMEOUT_S: float = 2.0
    # Max auto-restarts before the node is blacklisted
    MAX_RESTARTS: int = 3

    def __init__(
        self,
        *,
        domain: Domain   = Domain.A,
        kernel_hz: int   = 1000,
        name: str        = "neuros-kernel",
    ) -> None:
        self.domain     = domain
        self.kernel_hz  = kernel_hz
        self.name       = name
        self.state      = KernelState.INIT

        self._nodes: Dict[str, NodeRecord] = {}          # id → record
        self._lock  = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Callbacks
        self._on_node_failure: List[Callable] = []
        self._on_emergency:    List[Callable] = []

        # Metrics
        self._tick_count: int  = 0
        self._start_time: float = 0.0

        logger.info(
            "[KERNEL] NEUROS Kernel v0.1 initialising | domain=%s hz=%d",
            domain.value, kernel_hz,
        )

    # ── Registration ───────────────────────────────────────────────────────
    def register(self, node: "Node") -> str:
        """Register a node with the kernel. Returns the assigned node_id."""
        record = NodeRecord(node=node)
        node._kernel    = self              # back-reference
        node._node_id   = record.node_id
        with self._lock:
            self._nodes[record.node_id] = record
        logger.debug("[KERNEL] registered node=%s id=%s", node.name, record.node_id)
        return record.node_id

    def unregister(self, node_id: str) -> None:
        """Remove a node from the kernel."""
        with self._lock:
            rec = self._nodes.pop(node_id, None)
        if rec:
            logger.debug("[KERNEL] unregistered node_id=%s", node_id)

    # ── Lifecycle ──────────────────────────────────────────────────────────
    def start(self) -> None:
        """Start the kernel daemon thread."""
        if self.state != KernelState.INIT:
            raise RuntimeError("Kernel already started or shut down.")

        self.state      = KernelState.RUNNING
        self._start_time = time.monotonic()
        self._thread    = threading.Thread(
            target=self._kernel_loop,
            name=f"{self.name}-loop",
            daemon=True,
        )
        self._thread.start()
        logger.info("[KERNEL] started | state=RUNNING")

    def shutdown(self, *, timeout_s: float = 3.0) -> None:
        """Gracefully shut down the kernel and all nodes."""
        logger.info("[KERNEL] shutdown requested")
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout_s)
        self._terminate_all_nodes()
        self.state = KernelState.SHUTDOWN
        logger.info("[KERNEL] shutdown complete | uptime=%.1fs", self.uptime_s)

    def emergency_stop(self, reason: str = "unspecified") -> None:
        """
        Trigger a full emergency stop.
        Suspends all nodes immediately and fires safety callbacks.
        """
        logger.critical("[KERNEL] EMERGENCY STOP — reason: %s", reason)
        self.state = KernelState.EMERGENCY
        with self._lock:
            nodes = list(self._nodes.values())
        for rec in nodes:
            try:
                rec.node.on_emergency_stop(reason)
            except Exception:
                pass
        for cb in self._on_emergency:
            try:
                cb(reason)
            except Exception:
                pass

    # ── Kernel main loop ───────────────────────────────────────────────────
    def _kernel_loop(self) -> None:
        period_s = 1.0 / self.kernel_hz
        while not self._stop_event.is_set():
            t0 = time.monotonic()
            self._tick_count += 1

            if self.state == KernelState.RUNNING:
                self._watchdog_scan()

            elapsed = time.monotonic() - t0
            sleep   = max(0.0, period_s - elapsed)
            time.sleep(sleep)

    def _watchdog_scan(self) -> None:
        """Check all nodes for heartbeat timeouts and trigger restarts."""
        now = time.monotonic()
        with self._lock:
            records = list(self._nodes.values())

        for rec in records:
            if not rec.alive:
                continue
            age = now - rec.last_heartbeat
            if age > self.WATCHDOG_TIMEOUT_S:
                self._handle_node_timeout(rec, age)

    def _handle_node_timeout(self, rec: NodeRecord, age: float) -> None:
        logger.warning(
            "[WATCHDOG] node=%s id=%s heartbeat_age=%.2fs — attempting restart",
            rec.node.name, rec.node_id, age,
        )
        for cb in self._on_node_failure:
            try:
                cb(rec.node_id, rec.node.name, age)
            except Exception:
                pass

        if rec.restart_count >= self.MAX_RESTARTS:
            logger.error(
                "[WATCHDOG] node=%s exceeded max_restarts=%d — blacklisting",
                rec.node.name, self.MAX_RESTARTS,
            )
            rec.alive = False
            return

        try:
            rec.node._restart()
            rec.restart_count += 1
            rec.last_heartbeat = time.monotonic()
            logger.info("[WATCHDOG] node=%s restarted (attempt %d)", rec.node.name, rec.restart_count)
        except Exception as e:
            logger.error("[WATCHDOG] restart failed for node=%s: %s", rec.node.name, e)

    def _terminate_all_nodes(self) -> None:
        with self._lock:
            records = list(self._nodes.values())
        for rec in records:
            try:
                rec.node.destroy()
            except Exception:
                pass

    # ── Heartbeat (called by nodes) ────────────────────────────────────────
    def heartbeat(self, node_id: str) -> None:
        """Called by each node on every tick to signal it is alive."""
        with self._lock:
            rec = self._nodes.get(node_id)
        if rec:
            rec.last_heartbeat = time.monotonic()

    # ── Callbacks ──────────────────────────────────────────────────────────
    def on_node_failure(self, cb: Callable) -> None:
        """Register a callback: cb(node_id, node_name, heartbeat_age)."""
        self._on_node_failure.append(cb)

    def on_emergency(self, cb: Callable) -> None:
        """Register an emergency-stop callback: cb(reason)."""
        self._on_emergency.append(cb)

    # ── Introspection ─────────────────────────────────────────────────────
    @property
    def uptime_s(self) -> float:
        return time.monotonic() - self._start_time if self._start_time else 0.0

    @property
    def node_count(self) -> int:
        with self._lock:
            return len(self._nodes)

    def status(self) -> dict:
        with self._lock:
            nodes_snapshot = {
                nid: {
                    "name":          rec.node.name,
                    "alive":         rec.alive,
                    "error_count":   rec.error_count,
                    "restart_count": rec.restart_count,
                    "heartbeat_age": round(time.monotonic() - rec.last_heartbeat, 3),
                }
                for nid, rec in self._nodes.items()
            }
        return {
            "kernel":     self.name,
            "domain":     self.domain.value,
            "state":      self.state.value,
            "uptime_s":   round(self.uptime_s, 2),
            "tick_count": self._tick_count,
            "node_count": len(nodes_snapshot),
            "nodes":      nodes_snapshot,
        }

    def __repr__(self) -> str:
        return (
            f"<Kernel domain={self.domain.value} state={self.state.value} "
            f"nodes={self.node_count} uptime={self.uptime_s:.1f}s>"
        )
