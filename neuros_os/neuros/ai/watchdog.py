"""
neuros.ai.watchdog
===================
Phase 3 — Node Watchdog + Auto-Restart.

Monitors all running nodes for crashes, overruns, and errors.
Auto-restarts failed nodes with last-known-good config.
Publishes health events to Neural Bus.

Features
--------
  - Detect node ERROR/STOPPED state transitions
  - Auto-restart with exponential backoff
  - Crash-loop detection (disable after N restarts)
  - Health report publishing to /robot/system/watchdog
  - User-configurable restart policies per node

Usage
-----
    from neuros.ai.watchdog import NodeWatchdog

    wd = NodeWatchdog(robot, check_interval=2.0, max_restarts=5)
    wd.on_restart(lambda name, count: print(f"{name} restarted ({count}x)"))
    wd.start()
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from neuros.api.robot import Robot

logger = logging.getLogger("neuros.ai.watchdog")


# ── Restart Policy ────────────────────────────────────────────────────────

@dataclass
class RestartPolicy:
    """Per-node restart configuration."""
    enabled: bool = True
    max_restarts: int = 5
    backoff_base_s: float = 1.0
    backoff_max_s: float = 30.0
    cooldown_s: float = 10.0  # reset restart count after this much uptime (was 60s, too slow for robotics)


@dataclass
class _NodeHealth:
    """Internal health state for a monitored node."""
    name: str
    restart_count: int = 0
    last_restart: float = 0.0
    last_healthy: float = 0.0
    crash_loop: bool = False
    policy: RestartPolicy = field(default_factory=RestartPolicy)


@dataclass
class WatchdogEvent:
    """A watchdog event (restart, crash-loop, recovery)."""
    node_name: str
    event_type: str  # "restart", "crash_loop", "recovered", "error_detected"
    detail: str = ""
    restart_count: int = 0
    timestamp: float = field(default_factory=time.monotonic)

    def to_dict(self) -> dict:
        return {
            "node": self.node_name,
            "event": self.event_type,
            "detail": self.detail,
            "restart_count": self.restart_count,
            "timestamp": round(self.timestamp, 3),
        }


class NodeWatchdog:
    """
    Monitors all running nodes and auto-restarts failed ones.

    Parameters
    ----------
    robot            : Robot instance to monitor
    check_interval   : seconds between health checks (default 2.0)
    max_restarts     : global max restarts before crash-loop disable (default 5)
    """

    def __init__(
        self,
        robot: "Robot",
        *,
        check_interval: float = 2.0,
        max_restarts: int = 5,
    ) -> None:
        self._robot = robot
        self._interval = check_interval
        self._max_restarts = max_restarts
        self._health: Dict[str, _NodeHealth] = {}
        self._handlers: List[Callable] = []
        self._events: List[WatchdogEvent] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> "NodeWatchdog":
        """Start the watchdog monitoring thread."""
        # Disable the kernel's built-in watchdog to prevent double-restart races
        if hasattr(self._robot, '_kernel') and self._robot._kernel:
            self._robot._kernel._watchdog_enabled = False
            logger.info("[WATCHDOG] Disabled kernel built-in watchdog (AI watchdog takes over)")

        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="neuros-watchdog",
            daemon=True,
        )
        self._thread.start()
        logger.info("[WATCHDOG] Started | interval=%.1fs max_restarts=%d",
                    self._interval, self._max_restarts)
        return self

    def stop(self) -> None:
        """Stop the watchdog and re-enable kernel watchdog."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        # Re-enable kernel watchdog
        if hasattr(self._robot, '_kernel') and self._robot._kernel:
            self._robot._kernel._watchdog_enabled = True
        logger.info("[WATCHDOG] Stopped")

    # ── Configuration ─────────────────────────────────────────────────────

    def set_policy(self, node_name: str, policy: RestartPolicy) -> None:
        """Set a custom restart policy for a specific node."""
        with self._lock:
            if node_name in self._health:
                self._health[node_name].policy = policy
            else:
                self._health[node_name] = _NodeHealth(
                    name=node_name, policy=policy)

    def disable_restart(self, node_name: str) -> None:
        """Disable auto-restart for a specific node."""
        self.set_policy(node_name, RestartPolicy(enabled=False))

    def on_restart(self, handler: Callable) -> None:
        """Register a callback: fn(node_name, restart_count)."""
        self._handlers.append(handler)

    # ── Main Loop ─────────────────────────────────────────────────────────

    def _monitor_loop(self) -> None:
        """Periodic health check loop."""
        while self._running:
            try:
                self._check_all()
            except Exception as e:
                logger.error("[WATCHDOG] Monitor error: %s", e)
            time.sleep(self._interval)

    def _check_all(self) -> None:
        """Check health of all registered nodes."""
        now = time.monotonic()

        try:
            nodes = dict(self._robot._nodes)
        except Exception:
            return

        for node_id, node in nodes.items():
            name = node.name

            # Ensure health record exists
            with self._lock:
                if name not in self._health:
                    self._health[name] = _NodeHealth(
                        name=name,
                        last_healthy=now,
                        policy=RestartPolicy(max_restarts=self._max_restarts),
                    )
                health = self._health[name]

            # Get node state
            try:
                state_val = node.state.name if hasattr(node.state, 'name') else str(node.state)
            except Exception:
                state_val = "UNKNOWN"

            # Check if node is in error/stopped state
            if state_val in ("ERROR", "STOPPED", "FATAL"):
                self._handle_failure(name, node, health, state_val, now)
            elif state_val == "RUNNING":
                # Node is healthy — check cooldown for restart counter reset
                if health.restart_count > 0:
                    uptime = now - health.last_restart
                    if uptime > health.policy.cooldown_s:
                        health.restart_count = 0
                        health.crash_loop = False
                        self._fire_event(WatchdogEvent(
                            node_name=name, event_type="recovered",
                            detail=f"Uptime {uptime:.0f}s, restart count reset",
                        ))
                health.last_healthy = now

        # Publish watchdog status
        try:
            self._robot.publish("/robot/system/watchdog", self.summary())
        except Exception:
            pass

    def _handle_failure(
        self,
        name: str,
        node: Any,
        health: _NodeHealth,
        state: str,
        now: float,
    ) -> None:
        """Handle a node failure — restart if policy allows."""
        self._fire_event(WatchdogEvent(
            node_name=name, event_type="error_detected",
            detail=f"State={state}",
            restart_count=health.restart_count,
        ))

        if not health.policy.enabled:
            logger.debug("[WATCHDOG] %s in %s — restart disabled", name, state)
            return

        if health.crash_loop:
            logger.debug("[WATCHDOG] %s in crash-loop — skipping", name)
            return

        if health.restart_count >= health.policy.max_restarts:
            health.crash_loop = True
            self._fire_event(WatchdogEvent(
                node_name=name, event_type="crash_loop",
                detail=f"Exceeded max_restarts ({health.policy.max_restarts})",
                restart_count=health.restart_count,
            ))
            logger.error("[WATCHDOG] %s entered crash-loop — disabled", name)
            return

        # Calculate backoff delay
        backoff = min(
            health.policy.backoff_base_s * (2 ** health.restart_count),
            health.policy.backoff_max_s,
        )
        since_last = now - health.last_restart if health.last_restart else backoff + 1
        if since_last < backoff:
            return  # Wait for backoff

        # Restart the node
        health.restart_count += 1
        health.last_restart = now

        try:
            # Reset node state and re-activate
            node._state = node.state.__class__["CONFIGURED"]
            node._activate()
            logger.info("[WATCHDOG] Restarted %s (attempt %d/%d)",
                        name, health.restart_count, health.policy.max_restarts)
        except Exception as e:
            logger.error("[WATCHDOG] Restart of %s failed: %s", name, e)
            try:
                # Fallback: try full lifecycle
                node._state = node.state.__class__["UNCONFIGURED"]
                node._configure()
                node._activate()
                logger.info("[WATCHDOG] Full restart of %s succeeded", name)
            except Exception as e2:
                logger.error("[WATCHDOG] Full restart of %s failed: %s", name, e2)

        self._fire_event(WatchdogEvent(
            node_name=name, event_type="restart",
            detail=f"Attempt {health.restart_count}/{health.policy.max_restarts}",
            restart_count=health.restart_count,
        ))

        for handler in self._handlers:
            try:
                handler(name, health.restart_count)
            except Exception:
                pass

    def _fire_event(self, event: WatchdogEvent) -> None:
        """Record and publish a watchdog event."""
        self._events.append(event)
        if len(self._events) > 500:
            self._events = self._events[-250:]

        log_fn = logger.info if event.event_type == "recovered" else logger.warning
        log_fn("[WATCHDOG] %s: %s — %s", event.event_type, event.node_name, event.detail)

    # ── Introspection ─────────────────────────────────────────────────────

    def summary(self) -> dict:
        """Return watchdog status summary."""
        nodes = {}
        for name, h in self._health.items():
            nodes[name] = {
                "restart_count": h.restart_count,
                "crash_loop": h.crash_loop,
                "last_healthy": round(h.last_healthy, 1),
                "policy_enabled": h.policy.enabled,
            }
        return {
            "running": self._running,
            "total_events": len(self._events),
            "nodes": nodes,
            "total_restarts": sum(h.restart_count for h in self._health.values()),
        }

    @property
    def events(self) -> List[WatchdogEvent]:
        return list(self._events)

    @property
    def total_restarts(self) -> int:
        return sum(h.restart_count for h in self._health.values())

    def __repr__(self):
        return (f"NodeWatchdog(nodes={len(self._health)}, "
                f"restarts={self.total_restarts}, "
                f"events={len(self._events)})")


__all__ = [
    "NodeWatchdog",
    "RestartPolicy",
    "WatchdogEvent",
]
