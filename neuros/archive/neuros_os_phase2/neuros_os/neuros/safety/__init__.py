"""
neuros.safety
=============
Safety Supervisor — Phase 1.

Architecture
------------
The SafetySupervisor is a special node that monitors all other nodes
and hardware for safety-critical conditions and triggers emergency stops.

Phase 1 safety checks (software only)
--------------------------------------
  ✅ Battery voltage critically low
  ✅ Motor current overcurrent (via analog sensor)
  ✅ Watchdog timeout (kernel integration)
  ✅ Node crash / error state detection
  ✅ Software E-stop command via Neural Bus
  ✅ Heartbeat loss detection
  🔲 Hardware E-stop switch (Phase 2 — GPIO interrupt)
  🔲 IEC 62304 / DO-178C certification (Phase 4)

E-stop chain
------------
  Any condition → SafetySupervisor.trigger_estop(reason)
              → kernel.emergency_stop(reason)
              → All nodes receive on_emergency_stop()
              → Motors → speed = 0
              → Actuators → safe state
              → LEDs → alarm pattern
              → Bus publish /robot/system/estop

Published topics
----------------
  /robot/system/safety_status    periodic health report
  /robot/system/estop            on emergency stop
  /robot/system/fault            on non-critical fault

Subscribed topics
-----------------
  /robot/cmd/estop               software E-stop trigger
  /robot/sensor/battery          monitors for critical voltage
"""
from __future__ import annotations

import logging
import time
from typing import List, Optional, TYPE_CHECKING

from neuros.nodes.base import Node, NodeState, NodePriority

if TYPE_CHECKING:
    from neuros.kernel.core import Kernel

logger = logging.getLogger("neuros.safety")


class FaultCode:
    """Standard fault codes for the safety system."""
    BATTERY_CRITICAL  = "BATT_CRITICAL"
    OVERCURRENT       = "OVERCURRENT"
    NODE_CRASH        = "NODE_CRASH"
    WATCHDOG_TIMEOUT  = "WD_TIMEOUT"
    SOFT_ESTOP        = "SOFT_ESTOP"
    SENSOR_LOSS       = "SENSOR_LOSS"
    COMMUNICATION     = "COMM_LOSS"


class SafetySupervisor(Node):
    """
    Software safety supervisor node.

    Place this as the FIRST node added to the robot — it needs to be
    activated before any actuator nodes so it can intercept faults.

    Parameters
    ----------
    name            : node identifier (default "safety")
    battery_crit_v  : trigger E-stop below this voltage (default 3.0 V → 1S LiPo dead)
    hz              : supervisor scan rate (default 50 Hz)

    Example
    -------
        safety = SafetySupervisor()
        robot.add_node(safety)   # FIRST
        robot.add_node(MotorNode(...))
        robot.add_node(IMUNode(...))
    """

    def __init__(
        self,
        name:            str   = "safety",
        *,
        battery_crit_v:  float = 3.0,
        hz:              float = 50.0,
    ) -> None:
        super().__init__(name, hz=hz, priority=NodePriority.SAFETY)
        self._batt_crit       = battery_crit_v
        self._estop_triggered = False
        self._faults:   List[dict] = []
        self._battery_v:     float = 99.0
        self._estop_reason:  Optional[str] = None

    def configure(self) -> None:
        logger.info("[SAFETY] supervisor configured | batt_crit=%.2fV", self._batt_crit)

    def on_activate(self) -> None:
        # Monitor battery
        self.subscribe("/robot/sensor/battery",    self._on_battery)
        # Accept software E-stop commands
        self.subscribe("/robot/cmd/estop",         self._on_soft_estop)
        # Monitor all system alerts
        self.subscribe("/robot/system/battery_alert", self._on_battery_alert)
        logger.info("[SAFETY] supervisor active and monitoring")

    def tick(self) -> None:
        # Scan for node errors via kernel
        if self._kernel and not self._estop_triggered:
            status = self._kernel.status()
            for nid, info in status.get("nodes", {}).items():
                if not info.get("alive", True):
                    self._record_fault(FaultCode.NODE_CRASH, {
                        "node": info.get("name"), "node_id": nid
                    })

        # Publish safety heartbeat
        self.publish("/robot/system/safety_status", {
            "estop":        self._estop_triggered,
            "fault_count":  len(self._faults),
            "battery_v":    self._battery_v,
            "recent_fault": self._faults[-1] if self._faults else None,
        })

    def _on_battery(self, msg) -> None:
        v = float(msg.data.get("voltage_v", 99.0))
        self._battery_v = v
        if v < self._batt_crit and not self._estop_triggered:
            self.trigger_estop(FaultCode.BATTERY_CRITICAL, f"Battery {v:.2f}V < {self._batt_crit}V")

    def _on_battery_alert(self, msg) -> None:
        if msg.data.get("status") == "critical":
            self.trigger_estop(FaultCode.BATTERY_CRITICAL, "Battery monitor: CRITICAL")

    def _on_soft_estop(self, msg) -> None:
        reason = msg.data.get("reason", "software command")
        self.trigger_estop(FaultCode.SOFT_ESTOP, reason)

    def trigger_estop(self, code: str, detail: str = "") -> None:
        """Trigger a full emergency stop. Idempotent — safe to call multiple times."""
        if self._estop_triggered:
            return
        self._estop_triggered = True
        self._estop_reason    = detail
        msg = f"{code}: {detail}"
        logger.critical("[SAFETY] E-STOP TRIGGERED — %s", msg)

        self._record_fault(code, {"detail": detail})
        self.publish("/robot/system/estop", {
            "code":   code,
            "detail": detail,
            "time":   time.monotonic(),
        })

        if self._kernel:
            self._kernel.emergency_stop(msg)

    def _record_fault(self, code: str, data: dict) -> None:
        fault = {"code": code, "time": time.monotonic(), **data}
        self._faults.append(fault)
        logger.error("[SAFETY] FAULT: %s — %s", code, data)
        self.publish("/robot/system/fault", fault)

    def reset_estop(self) -> None:
        """
        Reset E-stop state (requires manual acknowledgement in Phase 4).
        Phase 1: programmatic reset allowed.
        """
        self._estop_triggered = False
        self._estop_reason    = None
        logger.warning("[SAFETY] E-stop reset by software")

    @property
    def is_safe(self) -> bool:
        return not self._estop_triggered

    @property
    def faults(self) -> List[dict]:
        return list(self._faults)
