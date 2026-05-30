"""
NEUROS V2 — Camera Event Schema

Emitted by the vision pipeline when a frame is captured and (optionally)
processed through a detection model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from neuros.schemas.events.base import BaseEvent, _default_event_id, _default_timestamp


@dataclass
class CameraEvent(BaseEvent):
    """A single camera frame capture and its detection results.

    Attributes
    ----------
    camera_id:
        Logical identifier for the camera source (e.g. ``"front_rgb"``).
    frame_id:
        Monotonically-increasing frame counter.
    width:
        Frame width in pixels.
    height:
        Frame height in pixels.
    format:
        Pixel format or codec (e.g. ``"RGB8"``, ``"JPEG"``, ``"H264"``).
    detections:
        List of detection dicts, each containing at minimum
        ``{"label": str, "confidence": float, "bbox": [x, y, w, h]}``.
        Empty when no detector is attached.
    """

    # -- BaseEvent overrides --
    event_id: str = field(default_factory=_default_event_id)
    timestamp: float = field(default_factory=_default_timestamp)
    event_type: str = field(default="CameraEvent", init=True)
    source: str = "vision_pipeline"

    # -- Domain fields --
    camera_id: str = ""
    frame_id: int = 0
    width: int = 640
    height: int = 480
    format: str = "RGB8"
    detections: list[dict[str, Any]] = field(default_factory=list)
