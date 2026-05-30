"""
neuros.fleet
=============
Fleet Manager — Phase 2, Domain B.

Manages a fleet of NEUROS robots:
  • Auto-discovery of robots on the local network (Zenoh peer mode)
  • Centralised status aggregation
  • Task distribution and assignment
  • Fleet-wide emergency stop
  • Health monitoring across all robots

Architecture
------------
  FleetManager runs on a coordinator machine (laptop / server).
  Each robot runs a FleetAgent that registers itself and streams
  heartbeats + status to the coordinator.

  Coordinator                        Robot A         Robot B
  ┌──────────────┐  Zenoh/DDS       ┌─────────────┐  ┌─────────────┐
  │ FleetManager │◄─────────────────►│ FleetAgent  │  │ FleetAgent  │
  │              │                  │ robot_a     │  │ robot_b     │
  │ - discovery  │                  │ hz=1 HB     │  │ hz=1 HB     │
  │ - status agg │                  └─────────────┘  └─────────────┘
  │ - task dist  │
  │ - E-stop     │
  └──────────────┘

Topics (fleet namespace)
-------------------------
  /fleet/discovery/<robot_id>/register    robot → coordinator
  /fleet/discovery/<robot_id>/heartbeat   robot → coordinator (1 Hz)
  /fleet/<robot_id>/status                robot → coordinator
  /fleet/task/<robot_id>/assign           coordinator → robot
  /fleet/estop                            coordinator → ALL robots (broadcast)
  /fleet/summary                          coordinator → any subscriber

Usage — coordinator side
-------------------------
    fleet = FleetManager(bus)
    fleet.start()
    print(fleet.summary())
    fleet.assign_task("robot_a", {"mission": "patrol_zone_1"})
    fleet.emergency_stop_all("coordinator command")

Usage — robot side
------------------
    agent = FleetAgent(robot, robot_id="robot_a")
    robot.add_node(agent)
"""
from __future__ import annotations
import logging, time, threading
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from neuros.api.robot import Robot
    from neuros.bus.bus   import NeuralBus

logger = logging.getLogger("neuros.fleet")


# ── Robot record kept by coordinator ──────────────────────────────────────
@dataclass
class RobotRecord:
    robot_id:       str
    last_seen:      float = field(default_factory=time.monotonic)
    status:         dict  = field(default_factory=dict)
    tasks_assigned: int   = 0
    online:         bool  = True
    board_info:     dict  = field(default_factory=dict)

    @property
    def age_s(self) -> float:
        return time.monotonic() - self.last_seen

    def to_dict(self) -> dict:
        return {
            "robot_id":       self.robot_id,
            "online":         self.online,
            "age_s":          round(self.age_s, 1),
            "tasks_assigned": self.tasks_assigned,
            "status":         self.status,
        }


# ══════════════════════════════════════════════════════════════════════════
class FleetManager:
    """
    Fleet coordinator — runs on a central machine, not on the robots.

    Parameters
    ----------
    bus              : NeuralBus instance (local or Zenoh-bridged)
    heartbeat_timeout: seconds before a robot is marked offline (default 5)
    """

    SUMMARY_HZ = 1.0   # publish fleet summary at this rate

    def __init__(
        self,
        bus,
        *,
        heartbeat_timeout: float = 5.0,
    ) -> None:
        self._bus      = bus
        self._hb_tmo   = heartbeat_timeout
        self._robots:  Dict[str, RobotRecord] = {}
        self._lock     = threading.Lock()
        self._running  = False
        self._thread:  Optional[threading.Thread] = None
        self._task_callbacks: List[Callable] = []

    def start(self) -> None:
        # Subscribe to fleet topics
        self._bus.subscribe("/fleet/discovery/+/register",  self._on_register)
        self._bus.subscribe("/fleet/discovery/+/heartbeat", self._on_heartbeat)
        self._bus.subscribe("/fleet/+/status",              self._on_status)

        self._running = True
        self._thread  = threading.Thread(
            target=self._monitor_loop, name="fleet-monitor", daemon=True,
        )
        self._thread.start()
        logger.info("[FLEET] coordinator started | timeout=%.1fs", self._hb_tmo)

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("[FLEET] coordinator stopped | robots seen=%d", len(self._robots))

    # ── Inbound handlers ───────────────────────────────────────────────────
    def _on_register(self, msg) -> None:
        robot_id = msg.data.get("robot_id", msg.source_id or "unknown")
        with self._lock:
            if robot_id not in self._robots:
                logger.info("[FLEET] new robot registered: %s", robot_id)
            self._robots[robot_id] = RobotRecord(
                robot_id   = robot_id,
                board_info = msg.data.get("board_info", {}),
            )

    def _on_heartbeat(self, msg) -> None:
        robot_id = msg.data.get("robot_id", "unknown")
        with self._lock:
            if robot_id in self._robots:
                self._robots[robot_id].last_seen = time.monotonic()
                self._robots[robot_id].online    = True

    def _on_status(self, msg) -> None:
        robot_id = msg.data.get("robot_id", "unknown")
        with self._lock:
            if robot_id in self._robots:
                self._robots[robot_id].status    = msg.data
                self._robots[robot_id].last_seen = time.monotonic()

    # ── Commands ────────────────────────────────────────────────────────────
    def assign_task(self, robot_id: str, task: dict) -> bool:
        from neuros.bus.message import Message
        with self._lock:
            rec = self._robots.get(robot_id)
        if rec is None or not rec.online:
            logger.warning("[FLEET] assign_task: robot '%s' not online", robot_id)
            return False
        self._bus.publish(Message(
            topic=f"/fleet/task/{robot_id}/assign",
            data={"robot_id": robot_id, "task": task},
        ))
        with self._lock:
            self._robots[robot_id].tasks_assigned += 1
        logger.info("[FLEET] task assigned to '%s': %s", robot_id, task)
        return True

    def emergency_stop_all(self, reason: str = "fleet command") -> None:
        from neuros.bus.message import Message, MessageType
        self._bus.publish(Message(
            topic="/fleet/estop",
            data={"reason": reason},
            msg_type=MessageType.EMERGENCY,
        ))
        logger.critical("[FLEET] FLEET-WIDE E-STOP: %s", reason)

    def broadcast(self, topic: str, data: dict) -> None:
        from neuros.bus.message import Message
        self._bus.publish(Message(topic=f"/fleet/{topic}", data=data))

    # ── Monitor loop ────────────────────────────────────────────────────────
    def _monitor_loop(self) -> None:
        period = 1.0 / self.SUMMARY_HZ
        while self._running:
            with self._lock:
                for rec in self._robots.values():
                    if rec.online and rec.age_s > self._hb_tmo:
                        rec.online = False
                        logger.warning("[FLEET] robot '%s' went OFFLINE (timeout)", rec.robot_id)
            # Publish summary
            from neuros.bus.message import Message
            self._bus.publish(Message(
                topic="/fleet/summary",
                data=self.summary(),
            ))
            time.sleep(period)

    # ── Introspection ────────────────────────────────────────────────────────
    def summary(self) -> dict:
        with self._lock:
            robots = [r.to_dict() for r in self._robots.values()]
        return {
            "total":   len(robots),
            "online":  sum(1 for r in robots if r["online"]),
            "offline": sum(1 for r in robots if not r["online"]),
            "robots":  robots,
        }

    @property
    def robot_ids(self) -> List[str]:
        with self._lock:
            return list(self._robots.keys())


# ══════════════════════════════════════════════════════════════════════════
class FleetAgent(  # also a NEUROS Node
    __import__("neuros.nodes.base", fromlist=["Node"]).Node
):
    """
    Fleet agent — runs ON each robot, registers with coordinator.

    Parameters
    ----------
    robot      : the Robot instance this agent belongs to
    robot_id   : unique identifier (default: robot.name)
    hz         : heartbeat rate (default 1 Hz)
    """

    def __init__(self, robot, *, robot_id: str = "", hz: float = 1.0) -> None:
        from neuros.nodes.base import NodePriority
        super().__init__("fleet_agent", hz=hz, priority=NodePriority.LOW)
        self._robot    = robot
        self._robot_id = robot_id or robot.name
        self._task_handler: Optional[Callable] = None

    def configure(self) -> None:
        logger.info("[FLEET-AGENT] '%s' configured", self._robot_id)

    def on_activate(self) -> None:
        # Listen for tasks and fleet-wide E-stop
        self.subscribe(f"/fleet/task/{self._robot_id}/assign", self._on_task)
        self.subscribe("/fleet/estop", self._on_fleet_estop)
        # Register with coordinator
        self._register()

    def tick(self) -> None:
        # Send heartbeat
        self.publish(f"/fleet/discovery/{self._robot_id}/heartbeat", {
            "robot_id": self._robot_id,
            "stamp":    time.monotonic(),
        })
        # Stream status
        self.publish(f"/fleet/{self._robot_id}/status", {
            "robot_id": self._robot_id,
            "uptime_s": round(self._robot._kernel.uptime_s, 1)
                        if self._robot._kernel else 0,
            "nodes":    self._robot._kernel.node_count
                        if self._robot._kernel else 0,
        })

    def _register(self) -> None:
        hal_info = {}
        if self._robot._hal:
            try:
                hal_info = self._robot._hal.board_info()
            except Exception:
                pass
        self.publish(f"/fleet/discovery/{self._robot_id}/register", {
            "robot_id":   self._robot_id,
            "board_info": hal_info,
        })

    def _on_task(self, msg) -> None:
        task = msg.data.get("task", {})
        logger.info("[FLEET-AGENT] received task: %s", task)
        if self._task_handler:
            try:
                self._task_handler(task)
            except Exception as e:
                logger.error("[FLEET-AGENT] task handler error: %s", e)

    def _on_fleet_estop(self, msg) -> None:
        reason = msg.data.get("reason", "fleet command")
        logger.critical("[FLEET-AGENT] FLEET E-STOP received: %s", reason)
        if self._robot._kernel:
            self._robot._kernel.emergency_stop(f"FLEET: {reason}")

    def on_task_received(self, handler: Callable[[dict], None]) -> None:
        """Register a callback for incoming task assignments."""
        self._task_handler = handler
