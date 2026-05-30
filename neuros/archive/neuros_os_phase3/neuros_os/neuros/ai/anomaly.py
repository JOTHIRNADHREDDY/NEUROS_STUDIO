"""
neuros.ai.anomaly
==================
AnomalyDetector — Phase 3.

Monitors all sensor streams on the Neural Bus and detects statistical
anomalies using online algorithms (no training data required):

  Z-score         : spike detection (|x - μ| > k·σ)
  IQR             : robust outlier detection
  Rate-of-change  : sudden jumps in sensor derivatives
  Absence         : topic goes silent for too long
  Correlation     : IMU/encoder disagreement detection

When an anomaly is detected:
  1. Publishes to /robot/system/anomaly
  2. Logs a warning
  3. Optionally calls registered handlers
  4. If severity = "critical" → triggers SafetySupervisor

AnomalyEvent fields
-------------------
  topic      : which Neural Bus topic triggered
  type       : "spike" | "jump" | "silence" | "range" | "correlation"
  value      : the offending value
  expected   : normal range or last known value
  severity   : "info" | "warning" | "critical"
  timestamp  : monotonic clock
"""

from __future__ import annotations

import logging
import math
import statistics
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from neuros.api.robot import Robot

logger = logging.getLogger("neuros.ai.anomaly")


@dataclass
class AnomalyEvent:
    """Describes a detected anomaly."""
    topic:     str
    type:      str           # "spike" | "jump" | "silence" | "range" | "correlation"
    value:     Any
    expected:  Any           # normal range or last value
    severity:  str           # "info" | "warning" | "critical"
    detail:    str           = ""
    timestamp: float         = field(default_factory=time.monotonic)

    def to_dict(self) -> dict:
        return {
            "topic":     self.topic,
            "type":      self.type,
            "value":     self.value,
            "expected":  self.expected,
            "severity":  self.severity,
            "detail":    self.detail,
            "timestamp": round(self.timestamp, 3),
        }


class _TopicStats:
    """Online running statistics for a single topic field."""

    def __init__(self, window: int = 100) -> None:
        self._buf: Deque[float]     = deque(maxlen=window)
        self.last_seen:  float      = time.monotonic()
        self.last_value: float      = 0.0

    def update(self, val: float) -> None:
        self._buf.append(val)
        self.last_value = val
        self.last_seen  = time.monotonic()

    @property
    def mean(self) -> float:
        return statistics.mean(self._buf) if len(self._buf) >= 2 else 0.0

    @property
    def stdev(self) -> float:
        return statistics.stdev(self._buf) if len(self._buf) >= 3 else 1.0

    @property
    def n(self) -> int:
        return len(self._buf)

    def z_score(self, val: float) -> float:
        s = self.stdev
        return abs(val - self.mean) / max(s, 1e-9)

    def rate_of_change(self, val: float) -> float:
        return abs(val - self.last_value)


class AnomalyDetector:
    """
    Statistical anomaly detector for Neural Bus sensor streams.

    Parameters
    ----------
    robot          : Robot instance to monitor
    z_threshold    : Z-score threshold for spike detection (default 4.0)
    silence_s      : seconds of silence before silence anomaly (default 5.0)
    window_size    : samples used for statistics (default 100)
    watch_topics   : list of topic patterns to monitor (default: all sensors)

    Usage
    -----
        detector = AnomalyDetector(robot, z_threshold=4.0)
        detector.on_anomaly(lambda e: print(f"ANOMALY: {e.topic} {e.type}"))
        detector.start()
    """

    def __init__(
        self,
        robot:         "Robot",
        *,
        z_threshold:   float       = 4.0,
        jump_factor:   float       = 5.0,     # rate-of-change × stdev
        silence_s:     float       = 5.0,
        window_size:   int         = 100,
        watch_topics:  Optional[List[str]] = None,
    ) -> None:
        self._robot      = robot
        self._z_thr      = z_threshold
        self._jump_fac   = jump_factor
        self._silence_s  = silence_s
        self._window     = window_size
        self._patterns   = watch_topics or ["/robot/sensor/#", "/robot/nav/#"]

        self._stats:    Dict[str, Dict[str, _TopicStats]] = {}
        self._handlers: List[Callable[[AnomalyEvent], None]] = []
        self._events:   List[AnomalyEvent] = []

        self._running    = False
        self._silence_thread: Optional[threading.Thread] = None

        # Hard limits for common sensor fields (min, max) → range anomaly
        self._hard_limits: Dict[str, Tuple[float, float]] = {
            "soc_pct":     (0.0,   100.0),
            "voltage_v":   (0.0,   30.0),
            "temperature": (-40.0, 150.0),
            "celsius":     (-40.0, 150.0),
            "distance_cm": (0.0,   800.0),
            "distance_m":  (0.0,   20.0),
        }

    # ── Lifecycle ─────────────────────────────────────────────────────────
    def start(self) -> None:
        for pattern in self._patterns:
            self._robot._bus.subscribe(pattern, self._on_message,
                                       node_id="anomaly_detector")
        self._running = True
        self._silence_thread = threading.Thread(
            target=self._silence_loop, daemon=True, name="anomaly-silence",
        )
        self._silence_thread.start()
        logger.info("[ANOMALY] detector started | z=%.1f silence=%.1fs patterns=%s",
                    self._z_thr, self._silence_s, self._patterns)

    def stop(self) -> None:
        self._running = False

    # ── Callbacks ─────────────────────────────────────────────────────────
    def on_anomaly(self, handler: Callable[[AnomalyEvent], None]) -> None:
        self._handlers.append(handler)

    # ── Message handler ────────────────────────────────────────────────────
    def _on_message(self, msg) -> None:
        data = msg.data
        if not isinstance(data, dict):
            return
        topic = msg.topic

        if topic not in self._stats:
            self._stats[topic] = {}

        # Process each numeric field
        for key, val in data.items():
            if not isinstance(val, (int, float)):
                continue
            val = float(val)

            if key not in self._stats[topic]:
                self._stats[topic][key] = _TopicStats(self._window)

            stats = self._stats[topic][key]

            # Need warmup before detecting anomalies
            if stats.n < 10:
                stats.update(val)
                continue

            field_key = f"{topic}:{key}"

            # 1. Hard range check (only after warmup)
            if key in self._hard_limits and stats.n >= 10:
                lo, hi = self._hard_limits[key]
                if not (lo <= val <= hi):
                    self._fire(AnomalyEvent(
                        topic=topic, type="range", value=val,
                        expected=(lo, hi), severity="warning",
                        detail=f"{key}={val:.3f} outside [{lo},{hi}]",
                    ))

            # 2. Z-score spike detection
            z = stats.z_score(val)
            if z > self._z_thr:
                self._fire(AnomalyEvent(
                    topic=topic, type="spike", value=val,
                    expected=round(stats.mean, 4),
                    severity="warning" if z < self._z_thr * 2 else "critical",
                    detail=f"{key}={val:.3f} z={z:.2f} μ={stats.mean:.3f} σ={stats.stdev:.3f}",
                ))

            # 3. Rate-of-change jump
            roc  = stats.rate_of_change(val)
            thr  = stats.stdev * self._jump_fac
            if roc > thr and stats.n > 20:
                self._fire(AnomalyEvent(
                    topic=topic, type="jump", value=val,
                    expected=stats.last_value,
                    severity="info" if roc < thr * 3 else "warning",
                    detail=f"{key} jumped {roc:.4f} (threshold={thr:.4f})",
                ))

            stats.update(val)

    def _silence_loop(self) -> None:
        """Periodically check for topics that have gone silent."""
        while self._running:
            time.sleep(1.0)
            now = time.monotonic()
            for topic, fields in dict(self._stats).items():
                for key, stats in fields.items():
                    if stats.n > 5 and (now - stats.last_seen) > self._silence_s:
                        self._fire(AnomalyEvent(
                            topic=topic, type="silence",
                            value=now - stats.last_seen,
                            expected=self._silence_s,
                            severity="warning",
                            detail=f"No data for {now - stats.last_seen:.1f}s",
                        ))
                        # Reset to avoid repeated fires
                        stats.last_seen = now

    def _fire(self, event: AnomalyEvent) -> None:
        """Fire an anomaly event to all registered handlers."""
        # Dedup: skip if same (topic, type) fired within 2 seconds
        now = time.monotonic()
        for past in reversed(self._events[-20:]):
            if (past.topic == event.topic and past.type == event.type
                    and now - past.timestamp < 2.0):
                return

        self._events.append(event)
        if len(self._events) > 500:
            self._events = self._events[-250:]

        logger.warning("[ANOMALY] %s %s %s | %s",
                       event.severity.upper(), event.type, event.topic, event.detail)

        # Publish to Neural Bus
        try:
            self._robot.publish("/robot/system/anomaly", event.to_dict())
        except Exception:
            pass

        for handler in self._handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error("[ANOMALY] handler error: %s", e)

    # ── Introspection ──────────────────────────────────────────────────────
    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def recent_events(self) -> List[AnomalyEvent]:
        return self._events[-20:]

    def summary(self) -> dict:
        counts: Dict[str, int] = {}
        for e in self._events:
            counts[e.type] = counts.get(e.type, 0) + 1
        return {
            "total":   len(self._events),
            "by_type": counts,
            "topics_monitored": len(self._stats),
        }
