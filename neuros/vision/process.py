"""
NEUROS Vision Process Manager

Manages the lifecycle of the multiprocessing Vision Worker and bridges
metadata back into the asyncio event loop and Neural Bus.
"""

import asyncio
import logging
import multiprocessing as mp
import numpy as np
from typing import Any

from neuros.vision.frame_buffer import SharedFrameBuffer
from neuros.vision.worker import vision_worker_loop

logger = logging.getLogger("neuros.vision.process")

class VisionProcessManager:
    def __init__(self, bus_publish: Any = None):
        self._bus_publish = bus_publish
        self._shape = (480, 640, 3)
        self._dtype = np.uint8
        self._buffer_name = "neuros_vision_shm"
        
        self._frame_buffer = SharedFrameBuffer(self._buffer_name, self._shape, self._dtype)
        self._metadata_queue = mp.Queue(maxsize=100)
        self._stop_event = mp.Event()
        
        self._worker_process: mp.Process | None = None
        self._monitor_task: asyncio.Task | None = None
        self._running = False

    def start(self):
        if self._running:
            return
            
        self._running = True
        self._frame_buffer.create()
        self._stop_event.clear()
        
        self._worker_process = mp.Process(
            target=vision_worker_loop,
            args=(self._stop_event, self._buffer_name, self._shape, self._metadata_queue)
        )
        self._worker_process.start()
        
        self._monitor_task = asyncio.create_task(self._metadata_monitor_loop())
        logger.info("Vision Process Manager started.")

    async def stop(self):
        self._running = False
        self._stop_event.set()
        
        try:
            if self._monitor_task:
                self._monitor_task.cancel()
                
            if self._worker_process:
                self._worker_process.join(timeout=2.0)
                if self._worker_process.is_alive():
                    self._worker_process.terminate()
        finally:
            self._frame_buffer.cleanup()
            from neuros.vision.cleanup import cleanup_all_shm
            cleanup_all_shm()
            logger.info("Vision Process Manager stopped.")

    def push_frame(self, frame: np.ndarray) -> None:
        """Push a frame to shared memory (typically called by camera ingest)."""
        if self._running:
            try:
                self._frame_buffer.write(frame)
            except Exception as e:
                logger.error("Failed to push frame to shared memory: %s", e)

    async def _metadata_monitor_loop(self):
        """Reads metadata from the queue and publishes to the Neural Bus."""
        while self._running:
            try:
                # Use executor to avoid blocking the event loop on queue.get
                loop = asyncio.get_running_loop()
                metadata_dict = await loop.run_in_executor(None, self._metadata_queue.get, True, 0.5)
                
                if self._bus_publish:
                    from neuros.schemas.events.vision import VisionEvent
                    # Just passing the dict for now, but should ideally convert to VisionEvent
                    self._bus_publish("/robot/vision/detections", metadata_dict)
                    
            except Exception as e:
                # Expected when queue is empty (TimeoutError from queue.get)
                if not isinstance(e, mp.queues.Empty):
                    await asyncio.sleep(0.1)
                continue
