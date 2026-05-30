import logging
from fastapi import APIRouter

from runtime.ros_runtime.isolator import ROSIsolator
from main import global_state

logger = logging.getLogger("neuros.api.ros")
router = APIRouter()
ros_isolator = ROSIsolator()

@router.post("/launch_core")
async def launch_core():
    """
    Launch ROS Core in the isolated runtime.
    """
    logger.info("Received request to launch ROS Core.")
    success = await ros_isolator.launch_core()
    
    if success:
        global_state.update_ros("core_running", True)
        return {"status": "success", "message": "ROS Core launched."}
    return {"status": "error", "message": "Failed to launch ROS Core."}

@router.post("/stop_core")
async def stop_core():
    logger.info("Received request to stop ROS Core.")
    await ros_isolator.stop_core()
    global_state.update_ros("core_running", False)
    return {"status": "success", "message": "ROS Core stopped."}
