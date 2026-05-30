"""NEUROS V3.1 — Workflow Registry.

Stores the no-code automation rules (Trigger -> Condition -> Action).
"""

import sqlite3
import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class WorkflowRegistry:
    """Manages workflows in the database."""

    def __init__(self, db_path: str = "workflows.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    enabled BOOLEAN,
                    robot_id TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_steps (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT,
                    type TEXT,
                    config TEXT,
                    step_order INTEGER,
                    FOREIGN KEY(workflow_id) REFERENCES workflows(id)
                )
            """)

    def save_workflow(self, workflow_id: str, name: str, robot_id: str, steps: List[Dict[str, Any]]) -> None:
        """Save a new workflow."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO workflows (id, name, enabled, robot_id) VALUES (?, ?, ?, ?)",
                         (workflow_id, name, True, robot_id))
            
            conn.execute("DELETE FROM workflow_steps WHERE workflow_id = ?", (workflow_id,))
            for i, step in enumerate(steps):
                conn.execute(
                    "INSERT INTO workflow_steps (id, workflow_id, type, config, step_order) VALUES (?, ?, ?, ?, ?)",
                    (f"{workflow_id}_step_{i}", workflow_id, step["type"], json.dumps(step["config"]), i)
                )
        logger.info("Saved workflow %r for robot %r", name, robot_id)

    def get_enabled_workflows(self) -> List[Dict[str, Any]]:
        """Fetch all enabled workflows."""
        workflows = []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT id, name, robot_id FROM workflows WHERE enabled = 1").fetchall()
            for r in rows:
                wf_id, name, robot_id = r
                steps_rows = conn.execute("SELECT type, config FROM workflow_steps WHERE workflow_id = ? ORDER BY step_order", (wf_id,)).fetchall()
                steps = [{"type": sr[0], "config": json.loads(sr[1])} for sr in steps_rows]
                workflows.append({
                    "id": wf_id,
                    "name": name,
                    "robot_id": robot_id,
                    "steps": steps
                })
        return workflows
