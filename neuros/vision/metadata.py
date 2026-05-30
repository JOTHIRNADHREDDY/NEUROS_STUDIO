"""
NEUROS Vision Metadata

Structures for vision processing results.
"""

from dataclasses import dataclass, field
from typing import Any

@dataclass
class BoundingBox:
    x_min: float
    y_min: float
    x_max: float
    y_max: float

@dataclass
class Detection:
    label: str
    confidence: float
    bbox: BoundingBox

@dataclass
class VisionMetadata:
    frame_id: int
    camera_id: str
    detections: list[Detection] = field(default_factory=list)
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "camera_id": self.camera_id,
            "latency_ms": self.latency_ms,
            "detections": [
                {
                    "label": d.label,
                    "confidence": d.confidence,
                    "bbox": [d.bbox.x_min, d.bbox.y_min, d.bbox.x_max, d.bbox.y_max]
                }
                for d in self.detections
            ]
        }
