import logging
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from orchestrator.task_scheduler import TaskScheduler
from runtime.ide_runtime.builder import IDEBuilder
from main import task_scheduler, event_bus

logger = logging.getLogger("neuros.api.ide")
router = APIRouter()

class CompileRequest(BaseModel):
    project_path: str
    board: str

@router.post("/compile")
async def compile_project(req: CompileRequest):
    """
    Trigger an isolated IDE compile job.
    """
    logger.info(f"Received compile request for {req.project_path}")
    
    # Instantiate the builder
    builder = IDEBuilder(event_bus)
    
    # Submit job to the orchestrator (runs in background)
    await task_scheduler.submit_job(
        f"compile_{req.board}",
        builder.compile_project(req.project_path, req.board)
    )
    
    return {"status": "queued", "message": "Compilation job scheduled."}
