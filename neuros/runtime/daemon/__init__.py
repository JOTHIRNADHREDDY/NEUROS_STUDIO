"""
NEUROS Runtime Daemon

The Daemon is the top-level orchestration layer for the Robot.
It wires together the Event Bus, Execution Manager, Skills, and HAL.
"""

import asyncio
import logging
import signal
import sys
from typing import Optional

from neuros.runtime.state.machine import StateMachine, RuntimeState

logger = logging.getLogger("neuros.runtime.daemon")


class RuntimeDaemon:
    """
    Manages the lifecycle of the NEUROS runtime services.
    """

    def __init__(self) -> None:
        self.state_machine = StateMachine()
        self._loop = asyncio.get_event_loop()
        self._shutdown_event = asyncio.Event()

    def start(self) -> None:
        """Starts the daemon blocking execution."""
        logger.info("Starting NEUROS Runtime Daemon...")
        
        # Setup signal handlers for graceful shutdown
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                self._loop.add_signal_handler(sig, self._signal_handler)
            except NotImplementedError:
                pass # Windows fallback

        self.state_machine.transition_to(RuntimeState.BOOTING)
        
        # TODO: Boot sequence (load config, connect HAL, start bus)
        
        self.state_machine.transition_to(RuntimeState.IDLE, reason="Boot sequence complete")
        logger.info("Daemon is ACTIVE and waiting for missions.")

        try:
            self._loop.run_until_complete(self._shutdown_event.wait())
        except KeyboardInterrupt:
            self._signal_handler()
        finally:
            self.shutdown()

    def _signal_handler(self) -> None:
        logger.warning("Received termination signal. Initiating graceful shutdown...")
        self.state_machine.transition_to(RuntimeState.SHUTDOWN, reason="Signal received")
        self._shutdown_event.set()

    def shutdown(self) -> None:
        """Gracefully shuts down all services."""
        logger.info("Shutting down NEUROS Runtime Daemon...")
        # TODO: Cleanup tasks, stop ExecutionManager, close HAL
        logger.info("Shutdown complete.")
