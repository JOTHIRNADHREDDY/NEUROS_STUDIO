"""NEUROS V3 — Mock Sensors.

Simulates physical sensors for testing the Skill and Workflow engines.
"""

import logging

logger = logging.getLogger(__name__)

class MockCamera:
    """Simulates a camera returning fake frames."""
    
    def get_frame(self) -> bytes:
        logger.debug("MockCamera: Capturing frame...")
        return b"fake_jpeg_data"

class MockLidar:
    """Simulates a 2D LiDAR scanner."""
    
    def get_scan(self) -> list[float]:
        logger.debug("MockLidar: Scanning...")
        return [1.0] * 360  # 1 meter clearance in all directions
