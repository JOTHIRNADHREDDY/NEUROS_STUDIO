import asyncio
import logging
from events.bus import EventBus

logger = logging.getLogger("neuros.orchestrator")

class TaskScheduler:
    """
    Job orchestration and queue management.
    Ensures that tasks like compilation or long-running AI requests don't block the main event loop.
    """
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._running = False
        self._worker_tasks = []
        self._job_queue = asyncio.Queue()

    def start(self, workers: int = 3):
        if not self._running:
            self._running = True
            for i in range(workers):
                task = asyncio.create_task(self._worker(i))
                self._worker_tasks.append(task)
            logger.info(f"Task Scheduler started with {workers} workers.")

    def stop(self):
        self._running = False
        for task in self._worker_tasks:
            task.cancel()
        self._worker_tasks.clear()
        logger.info("Task Scheduler stopped.")

    def is_running(self):
        return self._running

    async def submit_job(self, job_name: str, coroutine):
        """Submit an async job to be executed by the worker pool."""
        await self._job_queue.put((job_name, coroutine))
        logger.debug(f"Job submitted: {job_name}")

    async def _worker(self, worker_id: int):
        try:
            while self._running:
                job_name, coroutine = await self._job_queue.get()
                logger.info(f"[Worker-{worker_id}] Starting job: {job_name}")
                
                # Notify start
                await self.event_bus.publish(f"job.started.{job_name}", {"worker": worker_id})
                
                try:
                    # Execute job
                    await coroutine
                    logger.info(f"[Worker-{worker_id}] Completed job: {job_name}")
                    await self.event_bus.publish(f"job.completed.{job_name}", {"status": "success"})
                except Exception as e:
                    logger.error(f"[Worker-{worker_id}] Failed job {job_name}: {e}")
                    await self.event_bus.publish(f"job.failed.{job_name}", {"status": "error", "message": str(e)})
                finally:
                    self._job_queue.task_done()
        except asyncio.CancelledError:
            pass
