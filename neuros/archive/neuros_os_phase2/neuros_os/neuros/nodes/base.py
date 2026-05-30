"""
neuros.nodes.base
=================
Node — the fundamental unit of computation in NEUROS OS.

Every robot behaviour, sensor reader, actuator driver, AI pipeline
step, or planner is a Node. Nodes communicate exclusively through
the NeuralBus; they never call each other directly.

Lifecycle
---------
    __init__  → configure()  → activate()
                                   ↓
                              tick() [called at declared hz]
                                   ↓
                         on_emergency_stop() ← kernel
                                   ↓
                             destroy()

Design principles
-----------------
1. Nodes are stateless between ticks (all state → NeuralBus or explicit
   instance variables, never thread-local).
2. Every node heartbeats the kernel on each tick. Silent nodes trigger
   the watchdog.
3. Nodes declare their resource budget (cpu_budget_ms, mem_budget_kb)
   so the kernel can enforce limits in Phase 2+.

Domain compatibility matrix
----------------------------
  Domain A  (Zephyr / Arduino) : all basic nodes
  Domain B  (Linux RT / ROS2)  : all nodes + ROS2 bridge
  Domain C  (QNX certified)    : nodes with @certified decorator only
"""

from __future__ import annotations

import abc
import logging
import time
import enum
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from neuros.kernel.core import Kernel
    from neuros.bus.bus     import NeuralBus
    from neuros.bus.message import Message

logger = logging.getLogger("neuros.nodes")


class NodeState(enum.Enum):
    UNCONFIGURED  = "UNCONFIGURED"
    INACTIVE      = "INACTIVE"    # configured, not running
    ACTIVE        = "ACTIVE"      # running, ticking
    SUSPENDED     = "SUSPENDED"   # paused (e.g. emergency hold)
    ERROR         = "ERROR"
    DESTROYED     = "DESTROYED"


class NodePriority(enum.IntEnum):
    """Priority hints for the kernel scheduler."""
    LOW      = 10
    NORMAL   = 50
    HIGH     = 80
    REALTIME = 95
    SAFETY   = 100


class Node(abc.ABC):
    """
    Abstract NEUROS node.

    Subclass and implement at minimum:
        • tick()             — called at `hz` by the scheduler
        • configure()        — one-time setup (open serial port, etc.)
        • destroy()          — cleanup

    Optionally override:
        • on_activate()      — called when node is activated
        • on_suspend()       — called when node is suspended
        • on_emergency_stop(reason) — called on kernel E-stop

    Example
    -------
        class BlinkerNode(Node):
            def configure(self):
                self.hal.pin("LED", mode="output")

            def tick(self):
                self.hal.toggle("LED")
                self.publish("/robot/actuator/led", {"state": "toggle"})
    """

    def __init__(
        self,
        name:         str,
        *,
        hz:           float        = 10.0,
        priority:     NodePriority = NodePriority.NORMAL,
        cpu_budget_ms: float       = 10.0,
    ) -> None:
        self.name          = name
        self.hz            = hz
        self.priority      = priority
        self.cpu_budget_ms = cpu_budget_ms

        # Set by kernel on registration
        self._node_id:  Optional[str]     = None
        self._kernel:   Optional["Kernel"]   = None
        self._bus:      Optional["NeuralBus"] = None
        self._hal:      object             = None   # set by Robot on attach

        self._state     = NodeState.UNCONFIGURED
        self._tick_count = 0
        self._subs: List = []    # held subscriptions for cleanup

    # ── Properties ─────────────────────────────────────────────────────────
    @property
    def state(self) -> NodeState:
        return self._state

    @property
    def node_id(self) -> Optional[str]:
        return self._node_id

    @property
    def bus(self) -> "NeuralBus":
        if self._bus is None:
            raise RuntimeError(f"Node '{self.name}' is not attached to a NeuralBus.")
        return self._bus

    @property
    def hal(self):
        if self._hal is None:
            raise RuntimeError(f"Node '{self.name}' has no HAL attached.")
        return self._hal

    # ── Lifecycle hooks (override in subclass) ──────────────────────────────
    def configure(self) -> None:
        """One-time setup. Called before activate()."""

    def on_activate(self) -> None:
        """Called when the node transitions to ACTIVE."""

    def on_suspend(self) -> None:
        """Called when the node is suspended."""

    @abc.abstractmethod
    def tick(self) -> None:
        """
        Main execution body. Called repeatedly at `self.hz`.
        Must return quickly — blocking here blocks the scheduler.
        """

    def destroy(self) -> None:
        """Cleanup. Release hardware resources, close connections."""
        for sub in self._subs:
            try:
                self.bus.unsubscribe(sub)
            except Exception:
                pass

    def on_emergency_stop(self, reason: str) -> None:
        """Called by the kernel on emergency stop. Override for custom handling."""
        logger.warning("[NODE] %s received E-STOP: %s", self.name, reason)
        self._state = NodeState.SUSPENDED

    # ── Internal lifecycle transitions (called by Robot / Kernel) ──────────
    def _configure(self) -> None:
        self.configure()
        self._state = NodeState.INACTIVE

    def _activate(self) -> None:
        self._state = NodeState.ACTIVE
        self.on_activate()

    def _tick(self) -> None:
        """Internal tick wrapper — heartbeats kernel, updates metrics."""
        if self._state != NodeState.ACTIVE:
            return
        try:
            self.tick()
            self._tick_count += 1
            if self._kernel and self._node_id:
                self._kernel.heartbeat(self._node_id)
        except Exception as exc:
            logger.error("[NODE] %s tick raised: %s", self.name, exc)
            self._state = NodeState.ERROR

    def _restart(self) -> None:
        """Kernel-triggered restart after watchdog timeout."""
        logger.info("[NODE] restarting %s", self.name)
        try:
            self.destroy()
        except Exception:
            pass
        self._state = NodeState.UNCONFIGURED
        self._configure()
        self._activate()

    # ── Publish helpers ─────────────────────────────────────────────────────
    def publish(self, topic: str, data, *, msg_type=None) -> None:
        """Publish data to the Neural Bus."""
        from neuros.bus.message import Message, MessageType
        mt = msg_type or MessageType.DATA
        self.bus.publish(
            Message(topic=topic, data=data, msg_type=mt),
            source_id=self._node_id,
        )

    def subscribe(self, pattern: str, callback) -> None:
        """Subscribe to a topic pattern. Subscription is auto-cleaned on destroy()."""
        sub = self.bus.subscribe(pattern, callback, node_id=self._node_id or self.name)
        self._subs.append(sub)

    # ── Repr ────────────────────────────────────────────────────────────────
    def __repr__(self) -> str:
        return (
            f"<Node name={self.name!r} state={self._state.value} "
            f"hz={self.hz} ticks={self._tick_count}>"
        )
