import asyncio
import logging
from typing import Callable, Dict, List, Any

logger = logging.getLogger("neuros.events")

class EventBus:
    """
    Central Event Bus for NEUROS OS.
    Handles pub/sub messaging asynchronously across the backend.
    """
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._queue = asyncio.Queue()
        self._running = False
        self._task = None

    def subscribe(self, topic: str, callback: Callable):
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(callback)
        logger.debug(f"Subscribed to topic: {topic}")

    async def publish(self, topic: str, data: Any):
        """Asynchronously publish an event to the queue."""
        await self._queue.put((topic, data))

    def publish_sync(self, topic: str, data: Any):
        """Synchronously publish an event (useful for non-async contexts)."""
        try:
            self._queue.put_nowait((topic, data))
        except asyncio.QueueFull:
            logger.warning(f"Event bus queue full, dropped message on topic: {topic}")

    def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._process_events())
            logger.info("Event Bus started.")

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("Event Bus stopped.")

    def is_running(self):
        return self._running

    async def _process_events(self):
        try:
            while self._running:
                topic, data = await self._queue.get()
                
                # Match exact topics
                handlers = self._subscribers.get(topic, [])
                
                # Match wildcard topics (e.g., 'telemetry.*')
                for sub_topic, sub_handlers in self._subscribers.items():
                    if sub_topic.endswith("*") and topic.startswith(sub_topic[:-1]):
                        handlers.extend(sub_handlers)

                for handler in handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(data)
                        else:
                            handler(data)
                    except Exception as e:
                        logger.error(f"Error in event handler for {topic}: {e}")
                
                self._queue.task_done()
        except asyncio.CancelledError:
            pass
