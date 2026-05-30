"""
NEUROS Vision Worker

Runs in a separate process to perform heavy inference (e.g., YOLO) without
blocking the main asyncio loop. Reads from Shared Memory.
"""

import logging
import multiprocessing as mp
import time
from typing import Any

from neuros.vision.frame_buffer import SharedFrameBuffer
from neuros.vision.metadata import VisionMetadata, Detection, BoundingBox
from neuros.vision.cleanup import cleanup_all_shm

logger = logging.getLogger("neuros.vision.worker")

def vision_worker_loop(
    stop_event: mp.Event,
    buffer_name: str,
    shape: tuple,
    metadata_queue: mp.Queue,
    fps: int = 10
):
    """
    Main loop for the isolated vision process.
    """
    import numpy as np # Ensure numpy is imported in the new process context
    
    # Configure logging for the worker process
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    logger.info("Vision Worker Process started.")

    frame_buffer = SharedFrameBuffer(name=buffer_name, shape=shape, dtype=np.uint8)
    
    try:
        frame_buffer.attach()
    except Exception as e:
        logger.error("Vision worker failed to attach to Shared Memory: %s", e)
        return

    frame_id = 0
    interval = 1.0 / fps

    try:
        while not stop_event.is_set():
            start_time = time.time()
            
            try:
                # 1. Read frame from shared memory
                frame = frame_buffer.read()
                
                # 2. Run Inference (Mocked for MVP)
                # In real system: results = yolo_model(frame)
                time.sleep(0.05) # Simulate processing time
                
                # Create mock detection
                detections = [
                    Detection(
                        label="bottle",
                        confidence=0.95,
                        bbox=BoundingBox(0.1, 0.1, 0.2, 0.4)
                    )
                ]
                
                # 3. Create metadata and put on queue
                latency_ms = (time.time() - start_time) * 1000
                metadata = VisionMetadata(
                    frame_id=frame_id,
                    camera_id="main",
                    detections=detections,
                    latency_ms=latency_ms
                )
                
                # Use non-blocking put to avoid worker stalling if main process is slow
                try:
                    metadata_queue.put_nowait(metadata.to_dict())
                except Exception:
                    pass
                    
                frame_id += 1

            except Exception as e:
                logger.error("Error in vision worker loop: %s", e)
                
            # Enforce FPS
            elapsed = time.time() - start_time
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    finally:
        logger.info("Vision Worker Process stopping. Cleaning up resources.")
        frame_buffer.cleanup()
        cleanup_all_shm()
