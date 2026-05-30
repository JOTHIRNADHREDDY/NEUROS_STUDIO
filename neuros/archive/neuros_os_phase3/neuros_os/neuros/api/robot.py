"""
neuros.api.robot
================
Robot — the primary user-facing class in NEUROS OS.

This is what a beginner types after `pip install neuros`:

    from neuros import Robot

    robot = Robot(name="my-first-bot", board="simulator")
    robot.start()

    @robot.every(hz=1)
    def blink():
        robot.toggle("LED")

    robot.spin()

Or for a power user:

    from neuros import Robot
    from neuros.nodes.base import Node

    class NavigatorNode(Node):
        def tick(self):
            ...

    robot = Robot(name="rover", board="arduino", port="/dev/ttyUSB0")
    robot.add_node(NavigatorNode("nav", hz=100))
    robot.start()
    robot.spin()

Architecture role
-----------------
Robot is a thin orchestration shell that wires together:
  • Kernel        — node lifecycle + watchdog
  • NeuralBus     — pub/sub backbone
  • HAL           — hardware abstraction
  • Scheduler     — tick dispatch

It also provides the beginner-friendly decorator API (`@robot.every`)
so that non-developers can describe behaviour in plain functions
without knowing what a Node is.
"""

from __future__ import annotations

import atexit
import logging
import signal
import sys
import time
from typing import Callable, Dict, List, Optional

from neuros.kernel.core    import Kernel, Domain
from neuros.kernel.scheduler import Scheduler
from neuros.bus.bus        import NeuralBus
from neuros.bus.message    import Message, MessageType
from neuros.hal.detect     import auto_detect_hal
from neuros.nodes.base     import Node, NodeState, NodePriority

logger = logging.getLogger("neuros.robot")


class _CallbackNode(Node):
    """
    Internal adapter that wraps a plain Python function as a NEUROS Node.
    Used by the @robot.every() decorator for beginner-mode usage.
    """
    def __init__(self, name: str, fn: Callable, *, hz: float = 10.0) -> None:
        super().__init__(name, hz=hz)
        self._fn = fn

    def configure(self) -> None:
        pass

    def tick(self) -> None:
        self._fn()


class Robot:
    """
    NEUROS Robot — the main entry point.

    Parameters
    ----------
    name         : robot identifier (used in logging and bus namespace)
    board        : hardware target: "arduino" | "rpi" | "simulator" (default)
    port         : serial port for Arduino (e.g. "/dev/ttyUSB0")
    baud         : serial baud rate (default 115200)
    domain       : kernel domain: Domain.A (default) | Domain.B | Domain.C
    kernel_hz    : kernel watchdog poll rate (default 1000 Hz)
    log_level    : logging level (default logging.INFO)

    Quick-start examples
    --------------------
    Beginner (decorator API):
        robot = Robot("blinker", board="simulator")
        robot.start()

        @robot.every(hz=1)
        def blink():
            robot.toggle("LED")

        robot.spin()   # blocks forever, Ctrl+C to stop

    Advanced (node API):
        robot = Robot("rover", board="arduino", port="/dev/ttyUSB0")
        robot.add_node(MyNode("navigator", hz=100))
        robot.start()
        robot.spin()
    """

    def __init__(
        self,
        name:       str            = "neuros-robot",
        *,
        board:      Optional[str]  = None,
        port:       Optional[str]  = None,
        baud:       int            = 115_200,
        domain:     Domain         = Domain.A,
        kernel_hz:  int            = 1_000,
        log_level:  int            = logging.INFO,
    ) -> None:
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
            datefmt="%H:%M:%S",
        )
        self.name   = name
        self._board = board
        self._port  = port
        self._baud  = baud

        # Core components
        self._kernel    = Kernel(domain=domain, kernel_hz=kernel_hz, name=f"{name}-kernel")
        self._bus       = NeuralBus()
        self._scheduler = Scheduler(driver_hz=10_000)
        self._hal       = None    # lazily initialised on start()

        self._nodes:     Dict[str, Node] = {}
        self._started:   bool            = False
        self._emergency: bool            = False

        # Register E-stop signal handlers
        self._kernel.on_emergency(self._on_emergency)
        atexit.register(self.stop)

        logger.info("[ROBOT] '%s' created | domain=%s board=%s", name, domain.value, board or "auto")

    # ── Hardware ───────────────────────────────────────────────────────────
    @property
    def hal(self):
        if self._hal is None:
            raise RuntimeError("Robot not started. Call robot.start() first.")
        return self._hal

    # ── Node management ────────────────────────────────────────────────────
    def add_node(self, node: Node, *, autostart: bool = True) -> "Robot":
        """
        Register a node with this robot.

        If `autostart=True` and the robot is already running, the node
        will be immediately configured and activated.
        Returns `self` for fluent chaining.
        """
        # Wire the node into kernel / bus / hal
        node._bus = self._bus
        node._hal = self._hal

        node_id = self._kernel.register(node)
        self._nodes[node_id] = node

        if autostart and self._started:
            self._activate_node(node)

        logger.debug("[ROBOT] added node='%s' id=%s", node.name, node_id)
        return self

    def remove_node(self, node: Node) -> None:
        for nid, n in list(self._nodes.items()):
            if n is node:
                node.destroy()
                self._kernel.unregister(nid)
                del self._nodes[nid]
                self._scheduler.remove(nid)
                return

    # ── Decorator API (beginner-friendly) ──────────────────────────────────
    def every(self, *, hz: float = 1.0, name: Optional[str] = None):
        """
        Decorator: run a function at the given rate.

        Usage:
            @robot.every(hz=10)
            def update_leds():
                ...
        """
        def decorator(fn: Callable) -> Callable:
            node_name = name or fn.__name__
            node = _CallbackNode(node_name, fn, hz=hz)
            self.add_node(node)
            return fn
        return decorator

    # ── GPIO shortcuts (beginner API) ──────────────────────────────────────
    def pin(self, name: str, *, pin: int, mode="output") -> None:
        """Configure a named GPIO pin."""
        from neuros.hal.base import PinMode
        mode_map = {
            "output":     PinMode.OUTPUT,
            "input":      PinMode.INPUT,
            "pullup":     PinMode.INPUT_PULLUP,
            "pulldown":   PinMode.INPUT_PULLDOWN,
            "pwm":        PinMode.PWM,
            "analog_in":  PinMode.ANALOG_IN,
            "analog_out": PinMode.ANALOG_OUT,
        }
        self.hal.pin(name, board_pin=pin, mode=mode_map.get(mode, PinMode.OUTPUT))

    def write(self, name: str, value) -> None:
        """Write a value to a named pin."""
        self.hal.write(name, value)

    def read(self, name: str):
        """Read a value from a named pin."""
        return self.hal.read(name)

    def toggle(self, name: str) -> None:
        """Toggle a digital pin."""
        self.hal.toggle(name)

    # ── Pub/sub shortcuts ─────────────────────────────────────────────────
    def publish(self, topic: str, data) -> None:
        self._bus.publish(Message(topic=f"/{self.name}/{topic}", data=data))

    def subscribe(self, topic: str, callback: Callable[[Message], None]) -> None:
        self._bus.subscribe(f"/{self.name}/{topic}", callback)

    # ── Lifecycle ──────────────────────────────────────────────────────────
    def start(self) -> "Robot":
        """
        Initialise hardware, start kernel and scheduler, activate all nodes.
        Returns `self` for fluent chaining.
        """
        if self._started:
            logger.warning("[ROBOT] already started")
            return self

        logger.info("[ROBOT] starting '%s'", self.name)

        # 1. Initialise HAL
        self._hal = auto_detect_hal(
            board=self._board,
            port=self._port,
            baud=self._baud,
        )
        logger.info("[ROBOT] HAL: %s", self._hal)

        # 2. Wire HAL into already-registered nodes
        for node in self._nodes.values():
            node._hal = self._hal
            node._bus = self._bus

        # 3. Start kernel + scheduler
        self._kernel.start()
        self._scheduler.start()

        # 4. Configure + activate all nodes
        for node in self._nodes.values():
            self._activate_node(node)

        self._started = True

        # 5. Trap Ctrl+C
        signal.signal(signal.SIGINT, self._sigint_handler)

        logger.info("[ROBOT] '%s' running | nodes=%d", self.name, len(self._nodes))
        return self

    def stop(self) -> None:
        """Gracefully shut down the robot."""
        if not self._started:
            return
        logger.info("[ROBOT] stopping '%s'", self.name)
        self._scheduler.stop()
        self._kernel.shutdown()
        if self._hal:
            self._hal.disconnect()
        self._started = False
        logger.info("[ROBOT] stopped")

    def spin(self, *, hz: int = 100) -> None:
        """
        Block the calling thread and run the robot.
        Press Ctrl+C to stop.
        """
        if not self._started:
            self.start()

        period = 1.0 / hz
        logger.info("[ROBOT] spinning at %d Hz — Ctrl+C to stop", hz)
        try:
            while self._started and not self._emergency:
                time.sleep(period)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    # ── Status / introspection ─────────────────────────────────────────────
    def status(self) -> dict:
        """Return a full status snapshot of the robot and all nodes."""
        kernel_status = self._kernel.status()
        return {
            "robot":    self.name,
            "started":  self._started,
            "board":    repr(self._hal) if self._hal else "none",
            "bus":      repr(self._bus),
            **kernel_status,
        }

    def __repr__(self) -> str:
        return (
            f"<Robot name={self.name!r} started={self._started} "
            f"nodes={len(self._nodes)} board={self._board or 'auto'}>"
        )

    # ── Internal helpers ───────────────────────────────────────────────────
    def _activate_node(self, node: Node) -> None:
        node._bus = self._bus
        node._hal = self._hal
        node._configure()
        node._activate()
        # Register in scheduler
        self._scheduler.add(
            node.name,
            node._tick,
            hz=node.hz,
            priority=int(node.priority),
        )
        logger.debug("[ROBOT] activated node='%s' hz=%.1f", node.name, node.hz)

    def _on_emergency(self, reason: str) -> None:
        logger.critical("[ROBOT] EMERGENCY STOP: %s", reason)
        self._emergency = True

    def _sigint_handler(self, sig, frame) -> None:
        logger.info("[ROBOT] Ctrl+C — stopping")
        self.stop()
        sys.exit(0)
