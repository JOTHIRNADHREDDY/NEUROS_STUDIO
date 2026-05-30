"""
neuros.nodes.vision.camera
===========================
Camera Node — Phase 2, Domain B.

Captures frames from USB camera / Pi Camera / MIPI CSI camera
and publishes them to the Neural Bus.

Topics published
----------------
  /robot/vision/camera/<name>/frame    raw frame metadata (not pixel data)
  /robot/vision/camera/<name>/info     camera info (resolution, fps, latency)
  /robot/vision/camera/<name>/detect   detection results (if detector attached)
  /robot/vision/camera/<name>/jpeg     JPEG-encoded bytes (for streaming)

Frame payload
-------------
  {
    "width": 640, "height": 480,
    "channels": 3, "encoding": "bgr8",
    "frame_id": 12345,
    "latency_ms": 3.2,
    "_frame_ref": <id>     ← internal ID to retrieve from shared memory
  }

Shared frame store
------------------
  Raw NumPy arrays are stored in a thread-local FrameStore (not serialised
  onto the bus). Subscribers use frame["_frame_ref"] to retrieve from store.
  This avoids copying 640×480×3 bytes (~900KB) through the bus on every frame.

Detector pipeline (Phase 2)
----------------------------
  Attach a detector with camera_node.attach_detector(YOLODetector(...))
  Detections are published to /robot/vision/camera/<name>/detect.

Phase 3 will add:
  LLM-driven scene understanding
  Semantic segmentation
  Depth estimation from stereo
"""

from __future__ import annotations

import logging
import time
import threading
from typing import Any, Callable, Dict, List, Optional

from neuros.nodes.base import Node, NodePriority

logger = logging.getLogger("neuros.nodes.vision.camera")


class FrameStore:
    """Thread-safe store for raw NumPy frames, keyed by sequential ID."""
    def __init__(self, max_size: int = 5) -> None:
        self._store:   Dict[int, Any] = {}
        self._max     = max_size
        self._counter = 0
        self._lock    = threading.Lock()

    def put(self, frame) -> int:
        with self._lock:
            self._counter += 1
            fid = self._counter
            self._store[fid] = frame
            # Evict oldest
            while len(self._store) > self._max:
                oldest = min(self._store)
                del self._store[oldest]
            return fid

    def get(self, fid: int):
        with self._lock:
            return self._store.get(fid)


# Global frame store (one per process)
_FRAME_STORE = FrameStore(max_size=10)


class SyntheticFrame:
    """Small NumPy-like frame used when optional array libraries are absent."""

    def __init__(self, width: int, height: int, channels: int = 3) -> None:
        self.shape = (height, width, channels)

    def __len__(self) -> int:
        return self.shape[0]


class CameraNode(Node):
    """
    Camera capture node.

    Parameters
    ----------
    name          : node identifier
    camera_id     : OpenCV camera index (0 = first USB cam) or device path
    width, height : capture resolution (default 640×480)
    hz            : target frame rate (default 30 fps)
    encode_jpeg   : also publish JPEG bytes for streaming (default False)
    detector      : optional detector callable(frame) → list[Detection]
    flip          : 0=none, 1=vertical, 2=horizontal, -1=both

    Example
    -------
        cam = CameraNode("front_cam", camera_id=0, width=640, height=480, hz=30)
        robot.add_node(cam)

        # Get latest frame
        @robot.subscribe("/robot/vision/camera/front_cam/frame")
        def on_frame(msg):
            fid   = msg.data["_frame_ref"]
            frame = cam.get_frame(fid)   # numpy array
            # ... process frame
    """

    def __init__(
        self,
        name:         str,
        *,
        camera_id:    Any          = 0,
        width:        int          = 640,
        height:       int          = 480,
        hz:           float        = 30.0,
        encode_jpeg:  bool         = False,
        detector:     Optional[Callable] = None,
        flip:         int          = 0,
        priority:     NodePriority = NodePriority.HIGH,
    ) -> None:
        super().__init__(name, hz=hz, priority=priority)
        self._camera_id   = camera_id
        self._width       = width
        self._height      = height
        self._encode_jpeg = encode_jpeg
        self._detector    = detector
        self._flip        = flip

        self._cap         = None   # cv2.VideoCapture
        self._frame_count = 0
        self._last_frame_ts: float = 0.0
        self._latency_ms: float    = 0.0

        # Latest frame accessible without bus
        self._latest_fid: Optional[int] = None

    def configure(self) -> None:
        try:
            import cv2
            self._cap = cv2.VideoCapture(self._camera_id)
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self._width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
            self._cap.set(cv2.CAP_PROP_FPS,          self.hz)
            if not self._cap.isOpened():
                logger.warning(
                    "[CAM] '%s' camera_id=%s could not open — "
                    "falling back to synthetic frames",
                    self.name, self._camera_id,
                )
                self._cap = None
            else:
                actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                logger.info("[CAM] '%s' opened %dx%d @ %.0ffps",
                            self.name, actual_w, actual_h, self.hz)
        except ImportError:
            logger.warning(
                "[CAM] OpenCV not installed — synthetic frames only. "
                "Install: pip install opencv-python"
            )
            self._cap = None

    def tick(self) -> None:
        t0 = time.monotonic()

        frame = self._capture_frame()
        if frame is None:
            return

        # Apply flip
        if self._flip != 0:
            try:
                import cv2
                frame = cv2.flip(frame, self._flip)
            except Exception:
                pass

        # Store frame
        fid = _FRAME_STORE.put(frame)
        self._latest_fid  = fid
        self._frame_count += 1
        self._latency_ms  = (time.monotonic() - t0) * 1000

        h, w = frame.shape[:2] if hasattr(frame, "shape") else (self._height, self._width)
        ch   = frame.shape[2]  if (hasattr(frame, "shape") and len(frame.shape) > 2) else 3

        payload = {
            "width":      w,
            "height":     h,
            "channels":   ch,
            "encoding":   "bgr8",
            "frame_id":   self._frame_count,
            "latency_ms": round(self._latency_ms, 2),
            "_frame_ref": fid,
        }

        self.publish(f"/robot/vision/camera/{self.name}/frame", payload)

        # Run detector
        if self._detector:
            try:
                detections = self._detector(frame)
                self.publish(f"/robot/vision/camera/{self.name}/detect", {
                    "frame_id":   self._frame_count,
                    "detections": detections,
                })
            except Exception as e:
                logger.error("[CAM] detector error: %s", e)

        # JPEG encoding for streaming
        if self._encode_jpeg:
            self._publish_jpeg(frame, fid)

        # Camera info (every 10th frame)
        if self._frame_count % 10 == 0:
            self.publish(f"/robot/vision/camera/{self.name}/info", {
                "width":      self._width,
                "height":     self._height,
                "hz":         self.hz,
                "frames":     self._frame_count,
                "latency_ms": round(self._latency_ms, 2),
            })

    def _capture_frame(self):
        if self._cap is not None:
            try:
                ret, frame = self._cap.read()
                if ret:
                    return frame
            except Exception as e:
                logger.error("[CAM] capture error: %s", e)
        # Synthetic frame (gradient noise for testing)
        try:
            import numpy as np
            rng = np.random.default_rng(self._frame_count)
            return rng.integers(0, 256, (self._height, self._width, 3), dtype=np.uint8)
        except ImportError:
            return SyntheticFrame(self._width, self._height, 3)

    def _publish_jpeg(self, frame, fid: int) -> None:
        try:
            import cv2
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            self.publish(f"/robot/vision/camera/{self.name}/jpeg", {
                "frame_id": fid,
                "bytes":    buf.tobytes(),
                "encoding": "jpeg",
            })
        except Exception:
            pass

    def get_frame(self, fid: Optional[int] = None):
        """Retrieve a frame by ID from the store. If fid=None, returns latest."""
        fid = fid or self._latest_fid
        return _FRAME_STORE.get(fid) if fid else None

    def attach_detector(self, detector: Callable) -> None:
        """Attach a callable detector: detector(frame) → list of detections."""
        self._detector = detector

    def destroy(self) -> None:
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
        super().destroy()
