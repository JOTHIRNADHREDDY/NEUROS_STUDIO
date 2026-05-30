"""NEUROS V3.1 — Event Analytics.

Analyzes past events, failure patterns, and prepares data for AI learning.
"""

import logging
from typing import Dict, Any, List
from .store import EventStore

logger = logging.getLogger(__name__)

class EventAnalytics:
    """Analyzes stored events to detect patterns and generate reports."""

    def __init__(self, store: EventStore):
        self.store = store

    def analyze_errors(self, robot_id: str = None) -> Dict[str, Any]:
        """Aggregate errors to find common failure patterns."""
        errors = self.store.get_events(robot_id=robot_id, event_type="ERROR", limit=1000)
        
        # Simple count analysis
        error_counts = {}
        for err in errors:
            msg = err["payload"].get("error", "Unknown")
            error_counts[msg] = error_counts.get(msg, 0) + 1
            
        logger.info("Analyzed %d errors", len(errors))
        return {
            "total_errors": len(errors),
            "common_failures": error_counts
        }
