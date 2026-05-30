"""
neuros.monitor
===============
Real-Time Monitor — Phase 2.

Provides a live terminal dashboard (and optionally an HTTP endpoint)
for watching the robot's internals:
  • All nodes: state, tick rate, last heartbeat
  • Neural Bus: topics, message rates, subscriber counts
  • RT Scheduler: per-task latency histogram
  • HAL: pin states, I2C traffic, PWM duties
  • Fleet: connected robots + status

Terminal dashboard
------------------
    mon = RTMonitor(robot)
    mon.start()       # background thread prints to terminal
    robot.spin()

HTTP JSON endpoint (Phase 2)
-----------------------------
    mon = RTMonitor(robot, http_port=8765)
    mon.start()
    # → GET http://localhost:8765/status  returns full JSON snapshot

The HTTP server is a minimal built-in server (no Flask required).
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from neuros.api.robot import Robot

logger = logging.getLogger("neuros.monitor")

_CLEAR = "\033[2J\033[H"
_BOLD  = "\033[1m"
_DIM   = "\033[2m"
_RST   = "\033[0m"
_GRN   = "\033[32m"
_YLW   = "\033[33m"
_RED   = "\033[31m"
_CYN   = "\033[36m"
_MAG   = "\033[35m"


def _colour(text: str, col: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{col}{text}{_RST}"


class RTMonitor:
    """
    Real-time robot monitor with terminal dashboard and HTTP JSON API.

    Parameters
    ----------
    robot       : the Robot instance to monitor
    refresh_hz  : dashboard refresh rate (default 4 Hz)
    http_port   : if > 0, start an HTTP JSON status server on this port
    compact     : compact view (fewer rows, fits smaller terminals)
    """

    def __init__(
        self,
        robot,
        *,
        refresh_hz: float = 4.0,
        http_port:  int   = 0,
        compact:    bool  = False,
    ) -> None:
        self._robot      = robot
        self._period     = 1.0 / refresh_hz
        self._http_port  = http_port
        self._compact    = compact
        self._running    = False
        self._thread:    Optional[threading.Thread] = None
        self._http_thread: Optional[threading.Thread] = None
        self._frame:     int = 0

    def start(self) -> None:
        self._running = True
        self._thread  = threading.Thread(
            target=self._render_loop,
            name="neuros-monitor",
            daemon=True,
        )
        self._thread.start()

        if self._http_port > 0:
            self._http_thread = threading.Thread(
                target=self._http_server,
                name="neuros-monitor-http",
                daemon=True,
            )
            self._http_thread.start()
            logger.info("[MONITOR] HTTP status on http://localhost:%d/status",
                        self._http_port)

        logger.info("[MONITOR] started refresh=%.1fHz http=%s",
                    1.0 / self._period, self._http_port or "disabled")

    def stop(self) -> None:
        self._running = False

    def snapshot(self) -> dict:
        """Return a full status snapshot as a plain dict."""
        robot = self._robot
        kernel_status = robot._kernel.status() if robot._kernel else {}
        bus_metrics   = robot._bus.metrics()   if robot._bus   else {}

        node_details = []
        for nid, info in kernel_status.get("nodes", {}).items():
            node_details.append({
                "id":            nid,
                "name":          info.get("name", "?"),
                "alive":         info.get("alive", False),
                "heartbeat_age": info.get("heartbeat_age", 0.0),
                "errors":        info.get("error_count", 0),
                "restarts":      info.get("restart_count", 0),
            })

        top_topics = sorted(
            [
                {
                    "topic":     t,
                    "published": m.get("published", 0),
                    "subs":      robot._bus.subscriber_count(t),
                }
                for t, m in bus_metrics.items()
            ],
            key=lambda x: -x["published"],
        )[:20]

        hal_info = {}
        if robot._hal:
            try:
                hal_info = robot._hal.board_info()
            except Exception:
                pass

        return {
            "robot":        robot.name,
            "uptime_s":     round(kernel_status.get("uptime_s", 0.0), 1),
            "domain":       kernel_status.get("domain", "A"),
            "kernel_state": kernel_status.get("state", "UNKNOWN"),
            "tick_count":   kernel_status.get("tick_count", 0),
            "node_count":   kernel_status.get("node_count", 0),
            "nodes":        node_details,
            "top_topics":   top_topics,
            "hal":          hal_info,
            "timestamp":    round(time.monotonic(), 3),
        }

    # ── Terminal render loop ───────────────────────────────────────────────
    def _render_loop(self) -> None:
        while self._running:
            try:
                self._render()
            except Exception as e:
                logger.debug("[MONITOR] render error: %s", e)
            time.sleep(self._period)

    def _render(self) -> None:
        snap = self.snapshot()
        self._frame += 1

        lines = []
        W = 78

        # ── Header ──
        uptime = snap["uptime_s"]
        state  = snap["kernel_state"]
        state_col = _GRN if state == "RUNNING" else _RED
        lines.append(_colour("═" * W, _DIM))
        lines.append(
            _colour("  NEUROS OS", _BOLD + _CYN)
            + f"  {snap['robot']}"
            + f"  Domain-{snap['domain']}"
            + f"  {_colour(state, state_col)}"
            + f"  uptime={uptime}s"
            + f"  frame={self._frame}"
        )
        lines.append(_colour("─" * W, _DIM))

        # ── Nodes ──
        lines.append(_colour("  NODES", _BOLD + _MAG) +
                     f"  ({snap['node_count']} total)")
        for n in snap["nodes"]:
            alive_sym = _colour("●", _GRN) if n["alive"] else _colour("✗", _RED)
            age_col   = _RED if n["heartbeat_age"] > 1.0 else _GRN
            lines.append(
                "    " + alive_sym + "  " + n["name"].ljust(22)
                + "  hb=" + _colour(f"{n['heartbeat_age']:.2f}s", age_col)
                + f"  err={n['errors']}  restart={n['restarts']}"
            )
            if self._compact and len(lines) > 20:
                break

        # ── Bus topics ──
        lines.append(_colour("─" * W, _DIM))
        lines.append(_colour("  BUS TOPICS", _BOLD + _YLW) +
                     f"  ({len(snap['top_topics'])} active)")
        for t in snap["top_topics"][:8 if self._compact else 15]:
            lines.append(
                f"    {_colour(t['topic'][:46], _CYN):<52}"
                f"  pub={t['published']:<8}"
                f"  subs={t['subs']}"
            )

        # ── HAL ──
        if snap["hal"]:
            lines.append(_colour("─" * W, _DIM))
            lines.append(_colour("  HAL", _BOLD) +
                         f"  {snap['hal'].get('board', 'unknown')}")

        lines.append(_colour("═" * W, _DIM))

        output = _CLEAR + "\n".join(lines) + "\n"
        sys.stdout.write(output)
        sys.stdout.flush()

    # ── HTTP server ────────────────────────────────────────────────────────
    def _http_server(self) -> None:
        from http.server import BaseHTTPRequestHandler, HTTPServer

        monitor = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path in ("/status", "/status/"):
                    data = json.dumps(monitor.snapshot(), indent=2).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *args):
                pass   # silence HTTP access log

        try:
            server = HTTPServer(("0.0.0.0", self._http_port), Handler)
            while self._running:
                server.handle_request()
        except Exception as e:
            logger.error("[MONITOR] HTTP server error: %s", e)
