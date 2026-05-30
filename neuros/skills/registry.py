"""NEUROS V3.1 — Skill Registry.

Tracks installed reusable robotics skills in the system.
"""

import sqlite3
import logging
from typing import Dict, Any, List
import json

logger = logging.getLogger(__name__)

class SkillRegistry:
    """Manages the database of installed skills."""

    def __init__(self, db_path: str = "skills.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS skills (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE,
                    version TEXT,
                    description TEXT,
                    author TEXT,
                    status TEXT,
                    required_capabilities TEXT
                )
            """)

    def register_skill(self, skill_data: Dict[str, Any]) -> None:
        """Register a new skill into the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO skills 
                (id, name, version, description, author, status, required_capabilities)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                skill_data.get("name"),  # Using name as simple ID for now
                skill_data.get("name"),
                skill_data.get("version", "1.0.0"),
                skill_data.get("description", ""),
                skill_data.get("author", "unknown"),
                "active",
                json.dumps(skill_data.get("required_capabilities", []))
            ))
            logger.info("Registered skill: %s v%s", skill_data.get("name"), skill_data.get("version"))

    def get_all_skills(self) -> List[Dict[str, Any]]:
        """Fetch all installed skills."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM skills").fetchall()
            return [
                {
                    "id": r[0], "name": r[1], "version": r[2], 
                    "description": r[3], "author": r[4], 
                    "status": r[5], "required_capabilities": json.loads(r[6])
                }
                for r in rows
            ]
