"""NEUROS V3 — Memory System.

Stores critical long-term state that the AI needs to make robust
decisions across restarts. Specifically: Error, Deployment, Hardware,
and Skill memories. All complex episodic/cognitive memories are removed.
"""

from typing import Any, Dict, List
import logging
import sqlite3
import json

logger = logging.getLogger(__name__)

class MemoryManager:
    """Manages Error, Deployment, Hardware, and Skill memory stores."""

    def __init__(self, db_path: str = "memory.db") -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS error_memory (
                    error_id TEXT PRIMARY KEY,
                    fix TEXT,
                    success_count INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS deployment_memory (
                    deployment_id TEXT PRIMARY KEY,
                    status TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hardware_memory (
                    device_id TEXT PRIMARY KEY,
                    config_json TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS skill_memory (
                    skill_name TEXT PRIMARY KEY,
                    success_rate REAL DEFAULT 0.0,
                    total_executions INTEGER DEFAULT 0
                )
            """)

    # --- Error Memory ---
    def store_error_fix(self, error: str, fix: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO error_memory (error_id, fix, success_count)
                VALUES (?, ?, 1)
                ON CONFLICT(error_id) DO UPDATE SET 
                fix=excluded.fix, success_count=success_count+1
            """, (error, fix))
            
    def get_error_fix(self, error: str) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT fix FROM error_memory WHERE error_id = ?", (error,)).fetchone()
            return row[0] if row else None

    # --- Deployment Memory ---
    def record_deployment(self, deployment_id: str, status: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO deployment_memory (deployment_id, status)
                VALUES (?, ?)
            """, (deployment_id, status))

    # --- Hardware Memory ---
    def store_hardware_config(self, device_id: str, config: Dict[str, Any]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO hardware_memory (device_id, config_json)
                VALUES (?, ?)
            """, (device_id, json.dumps(config)))
            
    def get_hardware_config(self, device_id: str) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT config_json FROM hardware_memory WHERE device_id = ?", (device_id,)).fetchone()
            return json.loads(row[0]) if row else {}

    # --- Skill Memory ---
    def update_skill_stats(self, skill_name: str, success: bool) -> None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT success_rate, total_executions FROM skill_memory WHERE skill_name = ?", (skill_name,)).fetchone()
            if row:
                rate, total = row
                total += 1
                rate = ((rate * (total - 1)) + (1.0 if success else 0.0)) / total
                conn.execute("UPDATE skill_memory SET success_rate = ?, total_executions = ? WHERE skill_name = ?", (rate, total, skill_name))
            else:
                conn.execute("INSERT INTO skill_memory (skill_name, success_rate, total_executions) VALUES (?, ?, ?)", 
                             (skill_name, 1.0 if success else 0.0, 1))
