"""NEUROS V3.1 — Event Sourcing Store.

Provides the universal event database schema for all system actions.
Replaces the old Audit Trail.
"""

import sqlite3
import json
import logging
import time
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class EventStore:
    """SQLite-backed event store for all system activities."""

    def __init__(self, db_path: str = "events.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    event_type TEXT,
                    robot_id TEXT,
                    payload TEXT
                )
            """)

    def append(self, event_type: str, robot_id: str, payload: Dict[str, Any]) -> int:
        """Append a new event to the store."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO events (timestamp, event_type, robot_id, payload) VALUES (?, ?, ?, ?)",
                (time.time(), event_type, robot_id, json.dumps(payload))
            )
            return cursor.lastrowid

    def get_events(self, robot_id: str = None, event_type: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve events, optionally filtered by robot or type."""
        query = "SELECT id, timestamp, event_type, robot_id, payload FROM events WHERE 1=1"
        params = []
        if robot_id:
            query += " AND robot_id = ?"
            params.append(robot_id)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        
        query += " ORDER BY timestamp ASC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                {
                    "id": row[0],
                    "timestamp": row[1],
                    "type": row[2],
                    "robot_id": row[3],
                    "payload": json.loads(row[4])
                }
                for row in rows
            ]
