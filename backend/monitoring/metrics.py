import psutil
import logging
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session
from database.models.models import TelemetryLogModel
from database.engine import SessionLocal

logger = logging.getLogger("neuros.monitoring")

class DiagnosticsEngine:
    def __init__(self, event_bus):
        self.bus = event_bus

    async def get_system_metrics(self) -> Dict[str, Any]:
        """Fetch host system CPU, RAM, and disk utilization."""
        cpu = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        metrics = {
            "cpu_percent": cpu,
            "ram_percent": memory.percent,
            "disk_percent": disk.percent,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.bus.publish("monitoring.metrics", metrics)
        return metrics

    async def log_telemetry(self, source: str, level: str, message: str):
        """Persist a critical telemetry event to the SQLite database."""
        db: Session = SessionLocal()
        try:
            log_entry = TelemetryLogModel(
                source=source,
                level=level,
                message=message
            )
            db.add(log_entry)
            db.commit()
            logger.debug(f"Telemetry logged: [{level}] {source}: {message}")
        except Exception as e:
            logger.error(f"Failed to persist telemetry log: {e}")
            db.rollback()
        finally:
            db.close()
