import logging
from typing import List
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("neuros.api.ws")

class WebSocketManager:
    """
    Manages active WebSocket connections to the frontend.
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("New WebSocket connection established.")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info("WebSocket connection closed.")

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")

ws_manager = WebSocketManager()
