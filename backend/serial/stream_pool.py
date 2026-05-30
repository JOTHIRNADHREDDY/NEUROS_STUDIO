import serial
import asyncio
import logging
from typing import Dict, Any

logger = logging.getLogger("neuros.serial.pool")

class SerialStreamPool:
    def __init__(self, event_bus):
        self.bus = event_bus
        self.active_streams: Dict[str, Any] = {}
        
    async def connect(self, port: str, baudrate: int = 115200) -> bool:
        """Connect to a serial port and start reading in the background."""
        if port in self.active_streams:
            logger.warning(f"Port {port} is already connected.")
            return True
            
        try:
            # We use a non-blocking asyncio thread or a separate thread for serial read
            ser = serial.Serial(port, baudrate, timeout=1)
            self.active_streams[port] = {
                "serial": ser,
                "task": asyncio.create_task(self._read_loop(port, ser))
            }
            logger.info(f"Connected to serial port {port} at {baudrate} baud.")
            await self.bus.publish("serial.connected", {"port": port})
            return True
        except Exception as e:
            logger.error(f"Failed to connect to {port}: {e}")
            return False

    async def disconnect(self, port: str):
        if port in self.active_streams:
            stream = self.active_streams[port]
            stream["task"].cancel()
            stream["serial"].close()
            del self.active_streams[port]
            logger.info(f"Disconnected from serial port {port}.")
            await self.bus.publish("serial.disconnected", {"port": port})

    async def _read_loop(self, port: str, ser: serial.Serial):
        try:
            while True:
                if ser.in_waiting > 0:
                    data = ser.readline().decode('utf-8', errors='ignore').strip()
                    if data:
                        # Publish the raw data to the event bus
                        await self.bus.publish(f"serial.data.{port}", {"port": port, "data": data})
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error reading from {port}: {e}")
            await self.disconnect(port)

    async def write(self, port: str, data: str):
        if port in self.active_streams:
            ser = self.active_streams[port]["serial"]
            try:
                # Add newline if needed based on typical serial devices (Arduino, ROS Agent)
                payload = f"{data}\n".encode('utf-8')
                ser.write(payload)
                logger.debug(f"Wrote to {port}: {data}")
            except Exception as e:
                logger.error(f"Failed to write to {port}: {e}")
        else:
            logger.warning(f"Cannot write to {port}, not connected.")
