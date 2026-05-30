"""
neuros.kernel.rt.latency_mon
=============================
Latency Monitor — Phase 2, Domain B.

Tracks per-task latency distribution. Essential for verifying that
a PREEMPT-RT system is meeting its timing requirements before going
to Domain C (QNX certified) in Phase 4.

Metrics collected
-----------------
  min / max / mean / P50 / P95 / P99 / P99.9 latency (µs)
  overrun count (executions exceeding budget)
  jitter = max_latency - min_latency

Usage
-----
    mon = LatencyMonitor(budget_us=500)
    for each tick:
        t = mon.start()
        # ... do work ...
        mon.stop(t)

    stats = mon.stats()
    print(stats.p99_us)   # → e.g. 312.4 µs
"""

from __future__ import annotations

import time
import statistics
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class LatencyStats:
    """Latency statistics snapshot."""
    name:          str
    sample_count:  int
    min_us:        float
    max_us:        float
    mean_us:       float
    p50_us:        float
    p95_us:        float
    p99_us:        float
    p999_us:       float
    jitter_us:     float
    overrun_count: int
    budget_us:     float

    @property
    def within_budget_pct(self) -> float:
        if self.sample_count == 0:
            return 100.0
        return (1.0 - self.overrun_count / self.sample_count) * 100.0

    def __str__(self) -> str:
        return (
            f"LatencyStats[{self.name}] "
            f"n={self.sample_count} "
            f"min={self.min_us:.1f}µs "
            f"p50={self.p50_us:.1f}µs "
            f"p99={self.p99_us:.1f}µs "
            f"max={self.max_us:.1f}µs "
            f"jitter={self.jitter_us:.1f}µs "
            f"overruns={self.overrun_count} "
            f"within_budget={self.within_budget_pct:.1f}%"
        )


class LatencyMonitor:
    """
    High-resolution latency monitor for RT tasks.

    Parameters
    ----------
    name       : task identifier for reporting
    budget_us  : expected maximum execution time in microseconds
    max_samples: rolling window size (default 10,000 samples)
    """

    def __init__(
        self,
        name:        str   = "task",
        budget_us:   float = 1000.0,
        max_samples: int   = 10_000,
    ) -> None:
        self.name        = name
        self.budget_us   = budget_us
        self.max_samples = max_samples
        self._samples:   List[float] = []
        self._overruns:  int         = 0

    def start(self) -> float:
        """Record start timestamp. Returns the timestamp for use in stop()."""
        return time.perf_counter()

    def stop(self, start_ts: float) -> float:
        """Record end, compute latency. Returns latency in µs."""
        elapsed_us = (time.perf_counter() - start_ts) * 1_000_000
        self._samples.append(elapsed_us)
        if len(self._samples) > self.max_samples:
            self._samples.pop(0)
        if elapsed_us > self.budget_us:
            self._overruns += 1
        return elapsed_us

    def stats(self) -> LatencyStats:
        """Compute and return a statistics snapshot."""
        s = sorted(self._samples)
        n = len(s)
        if n == 0:
            return LatencyStats(
                name=self.name, sample_count=0,
                min_us=0.0, max_us=0.0, mean_us=0.0,
                p50_us=0.0, p95_us=0.0, p99_us=0.0, p999_us=0.0,
                jitter_us=0.0, overrun_count=0, budget_us=self.budget_us,
            )

        def pct(p: float) -> float:
            idx = min(int(n * p / 100), n - 1)
            return s[idx]

        return LatencyStats(
            name          = self.name,
            sample_count  = n,
            min_us        = round(s[0],  2),
            max_us        = round(s[-1], 2),
            mean_us       = round(statistics.mean(s), 2),
            p50_us        = round(pct(50.0),  2),
            p95_us        = round(pct(95.0),  2),
            p99_us        = round(pct(99.0),  2),
            p999_us       = round(pct(99.9),  2),
            jitter_us     = round(s[-1] - s[0], 2),
            overrun_count = self._overruns,
            budget_us     = self.budget_us,
        )

    def reset(self) -> None:
        self._samples.clear()
        self._overruns = 0

    def __len__(self) -> int:
        return len(self._samples)
