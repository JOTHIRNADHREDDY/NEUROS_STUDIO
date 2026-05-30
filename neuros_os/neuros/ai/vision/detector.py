"""
neuros.ai.vision.detector
==========================
VisionAI — Phase 3 computer vision pipeline.

Provides object detection, tracking, and classification.
Integrates with the ModelRegistry for hot-swappable models.

Subscribed:  /robot/vision/camera/<name>/frame
Published:   /robot/ai/vision/detections
             /robot/ai/vision/tracked
             /robot/ai/vision/closest_object

Detection output per object
----------------------------
  {
    "class":      str,        # e.g. "person", "chair"
    "confidence": float,      # 0.0 – 1.0
    "bbox":       [x1,y1,x2,y2],  # pixels
    "centre":     [cx, cy],
    "distance_m": float|null, # if depth available
    "track_id":   int|null,   # if tracker active
  }
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from neuros.nodes.base import Node, NodePriority

if TYPE_CHECKING:
    from neuros.ai.models.registry import ModelRegistry

logger = logging.getLogger("neuros.ai.vision")


@dataclass
class Detection:
    """Single object detection result."""
    class_name:  str
    confidence:  float
    bbox:        List[float]         # [x1, y1, x2, y2] pixels
    track_id:    Optional[int]       = None
    distance_m:  Optional[float]     = None
    timestamp:   float               = field(default_factory=time.monotonic)

    @property
    def centre(self) -> tuple:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    @property
    def area(self) -> float:
        x1, y1, x2, y2 = self.bbox
        return (x2 - x1) * (y2 - y1)

    def to_dict(self) -> dict:
        return {
            "class":      self.class_name,
            "confidence": round(self.confidence, 3),
            "bbox":       [round(v, 1) for v in self.bbox],
            "centre":     [round(v, 1) for v in self.centre],
            "track_id":   self.track_id,
            "distance_m": self.distance_m,
        }


class VisionAI(Node):
    """
    Vision AI node — object detection and tracking.

    Parameters
    ----------
    name           : node identifier
    camera_name    : camera node to subscribe to
    model_registry : ModelRegistry instance with a registered detector
    model_name     : name of the registered model (default "detector")
    conf_threshold : minimum confidence to report (default 0.5)
    hz             : inference rate (default 10 Hz)
    track          : enable simple centroid tracker (default False)

    Example
    -------
        registry = ModelRegistry()
        registry.register("detector", "yolov8n.pt", runtime="yolo")

        vision = VisionAI("vision", camera_name="front_cam",
                          model_registry=registry, hz=10)
        robot.add_node(vision)
    """

    def __init__(
        self,
        name:           str,
        *,
        camera_name:    str            = "front_cam",
        model_registry: Optional["ModelRegistry"] = None,
        model_name:     str            = "detector",
        conf_threshold: float          = 0.5,
        hz:             float          = 10.0,
        track:          bool           = False,
        priority:       NodePriority   = NodePriority.HIGH,
    ) -> None:
        super().__init__(name, hz=hz, priority=priority)
        self._camera     = camera_name
        self._registry   = model_registry
        self._model_name = model_name
        self._conf_thr   = conf_threshold
        self._track      = track

        self._latest_frame: Optional[Any] = None
        self._frame_id:     int            = 0
        self._detections:   List[Detection] = []

        # Simple centroid tracker state
        self._track_objects: Dict[int, dict] = {}
        self._next_track_id: int             = 0

        # Stats
        self._infer_count = 0
        self._avg_ms      = 0.0

    def configure(self) -> None:
        if self._registry is None:
            from neuros.ai.models.registry import ModelRegistry
            self._registry = ModelRegistry()
            self._registry.register(self._model_name, "", runtime="stub")
        logger.info("[VISION] '%s' camera=%s model=%s conf=%.2f track=%s",
                    self.name, self._camera, self._model_name,
                    self._conf_thr, self._track)

    def on_activate(self) -> None:
        self.subscribe(
            f"/robot/vision/camera/{self._camera}/frame",
            self._on_frame,
        )

    def _on_frame(self, msg) -> None:
        fid = msg.data.get("_frame_ref")
        if fid is None:
            return
        # Retrieve frame from FrameStore
        try:
            from neuros.nodes.vision.camera import _FRAME_STORE
            frame = _FRAME_STORE.get(fid)
            if frame is not None:
                self._latest_frame = frame
                self._frame_id     = msg.data.get("frame_id", fid)
        except Exception:
            pass

    def tick(self) -> None:
        if self._latest_frame is None:
            return

        t0    = time.monotonic()
        frame = self._latest_frame

        result = self._registry.infer(self._model_name, frame)
        lat_ms = (time.monotonic() - t0) * 1000
        self._infer_count += 1
        self._avg_ms       = (self._avg_ms * (self._infer_count - 1) + lat_ms) / self._infer_count

        # Filter by confidence
        raw_dets = [d for d in result.detections
                    if d.get("confidence", 0) >= self._conf_thr]

        # Convert to Detection objects
        detections = [
            Detection(
                class_name = d["class"],
                confidence = d["confidence"],
                bbox       = d["bbox"],
            )
            for d in raw_dets
        ]

        # Centroid tracking
        if self._track:
            detections = self._update_tracker(detections)

        self._detections = detections

        # Publish
        self.publish("/robot/ai/vision/detections", {
            "frame_id":   self._frame_id,
            "count":      len(detections),
            "detections": [d.to_dict() for d in detections],
            "latency_ms": round(lat_ms, 2),
        })

        # Publish closest object (useful for avoidance / interaction)
        if detections:
            # Largest bbox by area ≈ closest
            closest = max(detections, key=lambda d: d.area)
            self.publish("/robot/ai/vision/closest_object", {
                **closest.to_dict(),
                "frame_id": self._frame_id,
            })

    def _update_tracker(self, detections: List[Detection]) -> List[Detection]:
        """Very simple centroid-based tracker (Hungarian not used in Phase 3)."""
        max_dist_sq = 100.0 ** 2   # pixels

        matched_ids = set()
        for det in detections:
            cx, cy    = det.centre
            best_id   = None
            best_dist = max_dist_sq

            for tid, tracked in self._track_objects.items():
                if tid in matched_ids:
                    continue
                dx    = cx - tracked["cx"]
                dy    = cy - tracked["cy"]
                dist2 = dx * dx + dy * dy
                if dist2 < best_dist:
                    best_dist = dist2
                    best_id   = tid

            if best_id is not None:
                det.track_id = best_id
                matched_ids.add(best_id)
                self._track_objects[best_id].update({"cx": cx, "cy": cy})
            else:
                det.track_id = self._next_track_id
                self._track_objects[self._next_track_id] = {"cx": cx, "cy": cy}
                self._next_track_id += 1

        # Evict stale tracks (not seen this frame)
        stale = [tid for tid in self._track_objects if tid not in matched_ids]
        for tid in stale[:4]:   # remove up to 4 stale tracks per frame
            del self._track_objects[tid]

        return detections

    @property
    def latest_detections(self) -> List[Detection]:
        return list(self._detections)
