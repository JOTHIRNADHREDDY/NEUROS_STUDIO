import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn import Config, Server

from events.bus import EventBus
from orchestrator.task_scheduler import TaskScheduler
from state.runtime_state import GlobalState
from pty.terminal_manager import TerminalManager
from ros.graph_engine import ROSGraphEngine

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("neuros.backend")

# Global instances of core services
event_bus = EventBus()
global_state = GlobalState()
task_scheduler = TaskScheduler(event_bus)
terminal_manager = TerminalManager(event_bus)
ros_engine = ROSGraphEngine(event_bus, global_state)


from database.engine import Base, engine
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Database
    logger.info("Initializing SQLite database...")
    Base.metadata.create_all(bind=engine)

    # Startup tasks: Init subsystems, start background workers
    logger.info("Initializing NEUROS OS Backend Runtime...")
    
    # Start the event bus processor
    event_bus.start()
    
    # Start the orchestrator background workers
    task_scheduler.start()
    
    # Start ROS monitoring engine
    ros_engine.start()

    logger.info("NEUROS OS Backend Running.")
    yield
    
    # Shutdown tasks: Clean up processes, disconnect devices
    logger.info("Shutting down NEUROS OS Backend...")
    ros_engine.stop()
    task_scheduler.stop()
    terminal_manager.stop_all()
    event_bus.stop()


app = FastAPI(
    title="NEUROS OS Backend",
    description="Robotics Runtime Operating System Infrastructure",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok", "subsystems": {
        "event_bus": event_bus.is_running(),
        "task_scheduler": task_scheduler.is_running(),
        "ros_engine": ros_engine.is_running()
    }}


from api.ws_manager import ws_manager
from api.ros_api import router as ros_router
from api.ide_api import router as ide_router
from api.ai_api import router as ai_router
from api.files_api import router as files_router, folders_router

app.state.bus = event_bus
app.state.global_state = global_state
app.state.terminal_manager = terminal_manager
app.state.workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

# Register API routers
app.include_router(ros_router, prefix="/api/ros")
app.include_router(ide_router, prefix="/api/ide")
app.include_router(ai_router, prefix="/api/ai")
app.include_router(files_router, prefix="/api/files")
app.include_router(folders_router, prefix="/api/folders")

from fastapi import WebSocket, WebSocketDisconnect

async def _terminal_websocket(websocket: WebSocket, session_name: str, command: list[str] | None = None):
    await websocket.accept()
    shell_command = command or (["cmd.exe"] if os.name == "nt" else [os.environ.get("SHELL", "/bin/bash")])
    process = await asyncio.create_subprocess_exec(
        *shell_command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=app.state.workspace_root,
    )
    logger.info("Terminal session %s started with pid %s", session_name, process.pid)
    await websocket.send_text(f"\x1b[36m{session_name} connected. pid={process.pid}\x1b[0m\r\n")

    async def stream_output():
        assert process.stdout is not None
        while True:
            chunk = await process.stdout.read(1024)
            if not chunk:
                break
            await websocket.send_text(chunk.decode(errors="replace"))

    output_task = asyncio.create_task(stream_output())

    try:
        while True:
            data = await websocket.receive_text()
            if process.stdin and process.returncode is None:
                process.stdin.write(data.encode())
                await process.stdin.drain()
    except WebSocketDisconnect:
        logger.info("Terminal websocket %s disconnected", session_name)
    finally:
        output_task.cancel()
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=2)
            except asyncio.TimeoutError:
                process.kill()
        logger.info("Terminal session %s stopped", session_name)


@app.websocket("/api/ide/pty")
async def ide_pty_endpoint(websocket: WebSocket):
    await _terminal_websocket(websocket, "NEUROS Studio PTY")


@app.websocket("/api/ide/serial_pty")
async def ide_serial_pty_endpoint(websocket: WebSocket):
    await _terminal_websocket(websocket, "NEUROS Serial PTY")


@app.websocket("/api/ros/pty")
async def ros_pty_endpoint(websocket: WebSocket):
    await _terminal_websocket(websocket, "NEUROS ROS Console")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming WS messages if needed
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

if __name__ == "__main__":
    config = Config(app=app, host="0.0.0.0", port=8000, log_level="info")
    server = Server(config)
    asyncio.run(server.serve())
