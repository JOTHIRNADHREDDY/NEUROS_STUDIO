"""
neuros.kernel.rt
================
Phase 2 — Linux Real-Time Kernel Extensions.

What this module adds over Phase 1
-------------------------------------
  RTScheduler      SCHED_FIFO / SCHED_RR thread-level priority on PREEMPT-RT
  ProcessIsolator  spawn Domain B nodes in isolated subprocesses
  LatencyMonitor   per-tick latency histogram, jitter tracking
  CPUAffinity      pin threads to specific CPU cores (NUMA-aware)
  MemoryLocker     mlockall() to prevent page-fault jitter in RT threads

Prerequisites
-------------
  Linux kernel with PREEMPT_RT patch (or PREEMPT_RT_FULL)
  Run as root, or add CAP_SYS_NICE capability:
      sudo setcap cap_sys_nice+ep $(which python3)

  Check RT kernel:
      uname -v | grep PREEMPT_RT
      cat /sys/kernel/realtime   # → 1

Phase 2 vs Phase 1 scheduling
-------------------------------
  Phase 1  : threading.Thread, SCHED_OTHER (CFS), soft-RT, jitter ~5ms
  Phase 2  : SCHED_FIFO priority 80, mlockall, CPU-pinned, jitter <500µs
  Phase 4  : QNX pulse-based, <10µs deterministic (Domain C)
"""

from neuros.kernel.rt.rt_scheduler  import RTScheduler, SchedPolicy, RTTask
from neuros.kernel.rt.process_iso   import ProcessIsolator, IsolatedProcess
from neuros.kernel.rt.latency_mon   import LatencyMonitor, LatencyStats
from neuros.kernel.rt.cpu_affinity  import CPUAffinity, pin_thread_to_core
from neuros.kernel.rt.mem_lock      import MemoryLocker

__all__ = [
    "RTScheduler", "SchedPolicy", "RTTask",
    "ProcessIsolator", "IsolatedProcess",
    "LatencyMonitor", "LatencyStats",
    "CPUAffinity", "pin_thread_to_core",
    "MemoryLocker",
]
