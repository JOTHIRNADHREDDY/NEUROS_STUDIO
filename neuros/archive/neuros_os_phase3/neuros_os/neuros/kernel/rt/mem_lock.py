"""
neuros.kernel.rt.mem_lock
==========================
Memory locker — Phase 2.

Calls mlockall(MCL_CURRENT | MCL_FUTURE) to lock all current and future
pages into RAM. This eliminates page-fault induced jitter in RT threads.

Required for sub-millisecond latency guarantees.
Requires root or CAP_IPC_LOCK capability.
"""
from __future__ import annotations
import ctypes
import logging
import platform

logger = logging.getLogger("neuros.kernel.rt.mem_lock")

MCL_CURRENT = 1
MCL_FUTURE  = 2


class MemoryLocker:
    """
    Locks process memory to prevent page-fault RT jitter.

    Usage
    -----
        locker = MemoryLocker()
        if locker.lock():
            print("All memory locked — zero page-fault jitter")
        else:
            print("Could not lock memory — running with potential jitter")
    """

    def __init__(self) -> None:
        self._locked = False

    def lock(self) -> bool:
        """Lock all current and future pages into RAM."""
        if platform.system() != "Linux":
            logger.debug("[MEMLOCK] not on Linux — skip")
            return False
        try:
            libc = ctypes.CDLL("libc.so.6", use_errno=True)
            ret  = libc.mlockall(MCL_CURRENT | MCL_FUTURE)
            if ret != 0:
                errno = ctypes.get_errno()
                logger.warning("[MEMLOCK] mlockall failed errno=%d "
                               "(need CAP_IPC_LOCK or root)", errno)
                return False
            self._locked = True
            logger.info("[MEMLOCK] all memory locked — page-fault jitter eliminated")
            return True
        except Exception as e:
            logger.debug("[MEMLOCK] mlockall exception: %s", e)
            return False

    def unlock(self) -> None:
        if not self._locked:
            return
        try:
            libc = ctypes.CDLL("libc.so.6", use_errno=True)
            libc.munlockall()
            self._locked = False
        except Exception:
            pass

    @property
    def is_locked(self) -> bool:
        return self._locked
