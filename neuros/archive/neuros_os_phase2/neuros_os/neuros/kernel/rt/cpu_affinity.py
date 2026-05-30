"""
neuros.kernel.rt.cpu_affinity
==============================
CPU Affinity utilities — Phase 2.
"""
from __future__ import annotations
import logging, os, platform
from typing import Optional, Set

logger = logging.getLogger("neuros.kernel.rt.affinity")


class CPUAffinity:
    """Query and set CPU affinity for RT threads."""

    @staticmethod
    def available_cpus() -> Set[int]:
        try:
            return os.sched_getaffinity(0)
        except AttributeError:
            return set(range(os.cpu_count() or 1))

    @staticmethod
    def pin_to(cpu_set: Set[int]) -> bool:
        try:
            os.sched_setaffinity(0, cpu_set)
            return True
        except (AttributeError, OSError) as e:
            logger.debug("[AFFINITY] could not pin CPUs: %s", e)
            return False

    @staticmethod
    def isolate_rt_cores(n_rt_cores: int = 2) -> Optional[Set[int]]:
        """
        Reserve the last `n_rt_cores` CPUs for RT threads.
        Returns the RT core set if successful.

        Typical setup for a 4-core system:
          CPU 0–1 : OS + non-RT tasks
          CPU 2–3 : NEUROS RT tasks (isolated)
        """
        cpus = CPUAffinity.available_cpus()
        total = len(cpus)
        if total < n_rt_cores + 1:
            logger.warning("[AFFINITY] not enough CPUs for isolation (have %d)", total)
            return None
        rt_cores = set(sorted(cpus)[-n_rt_cores:])
        return rt_cores


def pin_thread_to_core(core: int) -> bool:
    """Pin the calling thread to a specific CPU core."""
    try:
        os.sched_setaffinity(0, {core})
        logger.debug("[AFFINITY] thread pinned to CPU %d", core)
        return True
    except (AttributeError, OSError) as e:
        logger.debug("[AFFINITY] pin_thread_to_core failed: %s", e)
        return False
