from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from ..engine import Base

class ProjectModel(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    path = Column(String, unique=True, nullable=False)
    board = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class TelemetryLogModel(Base):
    __tablename__ = "telemetry_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, index=True)
    level = Column(String)
    message = Column(String)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
