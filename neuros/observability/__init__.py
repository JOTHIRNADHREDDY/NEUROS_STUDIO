"""
NEUROS Observability

Structured logging, metrics collection, and distributed tracing.
Tracks skill execution, agent execution, ROS bridge latency, and HAL latency.
"""

from __future__ import annotations

import logging
import time
import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("neuros.observability")


@dataclass
class MetricPoint:
    """A single metric data point."""
    name: str
    value: float
    timestamp: float = field(default_factory=time.time)
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class TraceSpan:
    """A single span in a distributed trace."""
    trace_id: str
    span_id: str
    name: str
    start_time: float
    end_time: float | None = None
    duration_ms: float = 0.0
    parent_span_id: str | None = None
    tags: dict[str, str] = field(default_factory=dict)
    status: str = "ok"
    error: str | None = None


class MetricsCollector:
    """Collects and stores metrics in-memory with optional file export."""

    def __init__(self, max_points: int = 10000) -> None:
        self._metrics: dict[str, deque[MetricPoint]] = {}
        self._max_points = max_points

    def record(self, name: str, value: float, **labels: str) -> None:
        if name not in self._metrics:
            self._metrics[name] = deque(maxlen=self._max_points)
        self._metrics[name].append(MetricPoint(name=name, value=value, labels=labels))

    def get(self, name: str, last_n: int = 100) -> list[MetricPoint]:
        points = self._metrics.get(name, deque())
        return list(points)[-last_n:]

    def summary(self, name: str) -> dict[str, float]:
        points = self._metrics.get(name, deque())
        if not points:
            return {"count": 0}
        values = [p.value for p in points]
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "latest": values[-1],
        }

    def list_metrics(self) -> list[str]:
        return list(self._metrics.keys())


class TraceCollector:
    """Collects distributed trace spans."""

    def __init__(self, max_traces: int = 1000) -> None:
        self._spans: deque[TraceSpan] = deque(maxlen=max_traces)

    def start_span(
        self, trace_id: str, span_id: str, name: str,
        parent_span_id: str | None = None, **tags: str,
    ) -> TraceSpan:
        span = TraceSpan(
            trace_id=trace_id,
            span_id=span_id,
            name=name,
            start_time=time.time(),
            parent_span_id=parent_span_id,
            tags=tags,
        )
        self._spans.append(span)
        return span

    def end_span(self, span: TraceSpan, status: str = "ok", error: str | None = None) -> None:
        span.end_time = time.time()
        span.duration_ms = (span.end_time - span.start_time) * 1000
        span.status = status
        span.error = error

    def get_trace(self, trace_id: str) -> list[TraceSpan]:
        return [s for s in self._spans if s.trace_id == trace_id]

    def recent_spans(self, limit: int = 50) -> list[TraceSpan]:
        return list(self._spans)[-limit:]


class StructuredLogger:
    """JSON-structured logger that writes to file and console."""

    def __init__(self, log_dir: str = "data/logs/", name: str = "neuros") -> None:
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self._log_dir / f"{name}.jsonl"
        self._logger = logging.getLogger(name)

    def log(self, level: str, component: str, message: str, **extra: Any) -> None:
        entry = {
            "timestamp": time.time(),
            "level": level,
            "component": component,
            "message": message,
            **extra,
        }
        # Write to JSONL file
        try:
            with open(self._log_file, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception:
            pass

        # Also log via Python logger
        log_fn = getattr(self._logger, level.lower(), self._logger.info)
        log_fn("[%s] %s", component, message)

    def info(self, component: str, message: str, **extra: Any) -> None:
        self.log("INFO", component, message, **extra)

    def warning(self, component: str, message: str, **extra: Any) -> None:
        self.log("WARNING", component, message, **extra)

    def error(self, component: str, message: str, **extra: Any) -> None:
        self.log("ERROR", component, message, **extra)


class ObservabilitySystem:
    """Aggregated observability: metrics + traces + structured logs."""

    def __init__(self) -> None:
        self.metrics = MetricsCollector()
        self.traces = TraceCollector()
        self.logs = StructuredLogger()
        logger.info("ObservabilitySystem initialized.")

    def record_skill_execution(self, skill_name: str, duration_ms: float, success: bool) -> None:
        self.metrics.record("skill_duration_ms", duration_ms, skill=skill_name)
        self.metrics.record("skill_success", 1.0 if success else 0.0, skill=skill_name)

    def record_agent_execution(self, agent_name: str, duration_ms: float, tokens: int) -> None:
        self.metrics.record("agent_duration_ms", duration_ms, agent=agent_name)
        self.metrics.record("agent_tokens", float(tokens), agent=agent_name)

    def record_hal_latency(self, hal_name: str, latency_ms: float) -> None:
        self.metrics.record("hal_latency_ms", latency_ms, hal=hal_name)

    def record_bus_latency(self, topic: str, latency_ms: float) -> None:
        self.metrics.record("bus_latency_ms", latency_ms, topic=topic)

    def dashboard(self) -> dict[str, Any]:
        """Return a summary dashboard of all metrics."""
        return {
            metric: self.metrics.summary(metric)
            for metric in self.metrics.list_metrics()
        }
