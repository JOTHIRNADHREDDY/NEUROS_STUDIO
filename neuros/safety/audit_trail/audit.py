"""NEUROS V3 — Audit Trail.

Stores user commands, AI reasoning summaries, tool calls,
and execution results.
"""

from typing import Any, Dict
import logging
import sqlite3
import json
import time

logger = logging.getLogger(__name__)

class AuditTrail:
    """Records all system executions into a local SQLite database."""

    def __init__(self, db_path: str = "audit.db") -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the audit table."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    user_command TEXT,
                    ai_reasoning TEXT,
                    tool_call TEXT,
                    tool_args TEXT,
                    execution_result TEXT
                )
            """)

    def record_execution(self, 
                         user_command: str, 
                         ai_reasoning: str, 
                         tool_call: str, 
                         tool_args: Dict[str, Any], 
                         result: Any) -> None:
        """Log an execution event to the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO audit_log 
                    (timestamp, user_command, ai_reasoning, tool_call, tool_args, execution_result)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    time.time(),
                    user_command,
                    ai_reasoning,
                    tool_call,
                    json.dumps(tool_args),
                    json.dumps(result)
                ))
            logger.info("Audit log recorded for tool %r", tool_call)
        except Exception as e:
            logger.error("Failed to record audit trail: %s", e)
