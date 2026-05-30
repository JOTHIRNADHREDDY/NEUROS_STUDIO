"""
NEUROS Vision Frame Buffer

Manages shared memory for passing heavy image frames between the main process
and the vision worker process without serialization overhead.
"""

import logging
from multiprocessing import shared_memory
import numpy as np
from typing import Tuple

logger = logging.getLogger("neuros.vision.frame_buffer")

class SharedFrameBuffer:
    def __init__(self, name: str, shape: Tuple[int, int, int], dtype: np.dtype = np.uint8):
        self.name = name
        self.shape = shape
        self.dtype = dtype
        self.size = int(np.prod(shape) * dtype.itemsize)
        self._shm: shared_memory.SharedMemory | None = None
        self._array: np.ndarray | None = None

    def create(self) -> None:
        """Create the shared memory block (called by main process)."""
        try:
            self._shm = shared_memory.SharedMemory(name=self.name, create=True, size=self.size)
            self._array = np.ndarray(self.shape, dtype=self.dtype, buffer=self._shm.buf)
            register_shm(self.name)
            logger.info("Created SharedFrameBuffer '%s' (size=%d)", self.name, self.size)
        except FileExistsError:
            logger.warning("SharedMemory '%s' already exists. Attaching instead.", self.name)
            self.attach()

    def attach(self) -> None:
        """Attach to an existing shared memory block (called by worker process)."""
        self._shm = shared_memory.SharedMemory(name=self.name, create=False)
        self._array = np.ndarray(self.shape, dtype=self.dtype, buffer=self._shm.buf)
        register_shm(self.name)

    def write(self, frame: np.ndarray) -> None:
        """Write a frame to shared memory."""
        if self._array is None:
            raise RuntimeError("SharedFrameBuffer not initialized.")
        if frame.shape != self.shape:
            raise ValueError(f"Frame shape {frame.shape} does not match buffer shape {self.shape}")
        
        np.copyto(self._array, frame)

    def read(self) -> np.ndarray:
        """Read a frame from shared memory (returns a copy to avoid concurrency issues)."""
        if self._array is None:
            raise RuntimeError("SharedFrameBuffer not initialized.")
        return self._array.copy()

    def cleanup(self) -> None:
        """Close and unlink shared memory."""
        if self._shm:
            try:
                self._shm.close()
                self._shm.unlink()
                logger.info("Unlinked SharedFrameBuffer '%s'", self.name)
            except FileNotFoundError:
                pass
            finally:
                unregister_shm(self.name)
            self._shm = None
            self._array = None

