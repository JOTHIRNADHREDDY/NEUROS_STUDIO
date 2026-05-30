"""NEUROS V3.1 — Workflow Triggers.

Events that initiate a workflow.
"""

import logging

logger = logging.getLogger(__name__)

class Trigger:
    """Base class for all triggers."""
    def evaluate(self, event_type: str, payload: dict) -> bool:
        raise NotImplementedError

class BatteryLowTrigger(Trigger):
    def __init__(self, threshold: float):
        self.threshold = threshold

    def evaluate(self, event_type: str, payload: dict) -> bool:
        if event_type == "TELEMETRY" and "battery" in payload:
            return payload["battery"] < self.threshold
        return False

class ObjectDetectedTrigger(Trigger):
    def __init__(self, object_class: str):
        self.object_class = object_class

    def evaluate(self, event_type: str, payload: dict) -> bool:
        if event_type == "VISION" and "detected_objects" in payload:
            return self.object_class in payload["detected_objects"]
        return False
