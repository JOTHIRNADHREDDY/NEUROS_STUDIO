"""NEUROS V3 — Telemetry Platform.

Stores time-series data like battery, CPU, RAM, Network, and Sensor Data.
Currently uses SQLite/DuckDB interface.
"""

import logging
import sqlite3
import time

logger = logging.getLogger(__name__)

class TelemetryStorage:
    """Stores high-frequency telemetry in a time-series friendly format."""

    def __init__(self, db_path: str = "telemetry.duckdb") -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        # Mocking DuckDB with SQLite for MVP compatibility
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    device_id TEXT,
                    timestamp REAL,
                    metric_name TEXT,
                    value REAL
                )
            """)

    def insert_metric(self, device_id: str, metric_name: str, value: float) -> None:
        """Insert a single telemetry metric."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO metrics (device_id, timestamp, metric_name, value) VALUES (?, ?, ?, ?)",
                    (device_id, time.time(), metric_name, value)
                )
        except Exception as e:
            logger.error("Telemetry insert failed: %s", e)
