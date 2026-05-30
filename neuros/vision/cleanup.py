"""
NEUROS Vision Shared Memory Cleanup Manager

Registers and tracks shared memory segments to ensure they are cleaned up
on exit, crash, or when explicitly requested.
"""

import atexit
import logging
import signal
import sys
from multiprocessing import shared_memory

logger = logging.getLogger("neuros.vision.cleanup")

_registered_shm_names: set[str] = set()


def register_shm(name: str) -> None:
    """Register a shared memory name for automatic cleanup."""
    _registered_shm_names.add(name)
    logger.debug(f"Registered SHM for cleanup: {name}")


def unregister_shm(name: str) -> None:
    """Unregister a shared memory name."""
    if name in _registered_shm_names:
        _registered_shm_names.remove(name)


def cleanup_all_shm() -> None:
    """Attempt to close and unlink all registered shared memory blocks."""
    for name in list(_registered_shm_names):
        try:
            shm = shared_memory.SharedMemory(name=name)
            shm.close()
            shm.unlink()
            logger.info(f"Cleaned up SHM: {name}")
        except FileNotFoundError:
            pass  # Already unlinked
        except Exception as e:
            logger.error(f"Error cleaning up SHM {name}: {e}")
        finally:
            unregister_shm(name)

def _signal_handler(signum, frame):
    """Handle termination signals to clean up SHM."""
    logger.warning(f"Received signal {signum}. Cleaning up SHM...")
    cleanup_all_shm()
    sys.exit(1)

# Register cleanup on normal exit
atexit.register(cleanup_all_shm)

# Register cleanup on crash/termination (only in main thread)
try:
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
except ValueError:
    # Not in main thread, signal handlers can't be set
    pass
