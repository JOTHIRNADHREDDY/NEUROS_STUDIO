"""
NEUROS OS — Universal Robot Operating System
Phase 1: Basic Robot Support (Domain A — Arduino + Pi)

Architecture: 3-Domain model
  Domain A — Zephyr / MCU / Arduino   (this phase)
  Domain B — Linux RT / ROS2          (Phase 2)
  Domain C — QNX Certified            (Phase 4+)

Public surface — everything a Phase-1 developer needs:

    from neuros import Robot, Node, Message, spin
    from neuros import GPIO, Serial, Sensor, Motor
    from neuros.kernel import Kernel
    from neuros.bus import NeuralBus
"""

__version__ = "0.1.0-phase1"
__author__  = "NEUROS OS Team"
__domain__  = "A"   # active domain this build targets

# ── Public API re-exports ──────────────────────────────────────────────────
from neuros.api.robot   import Robot          # noqa: F401  main entry point
from neuros.bus.bus     import NeuralBus      # noqa: F401  pub/sub backbone
from neuros.kernel.core import Kernel         # noqa: F401  the heartbeat
from neuros.nodes.base  import Node, NodeState, NodePriority  # noqa: F401
from neuros.bus.message import Message, Topic  # noqa: F401

# ── Convenience factory ────────────────────────────────────────────────────
def spin(robot: "Robot", *, hz: int = 100) -> None:
    """Block and run the robot event loop at the given rate."""
    robot.spin(hz=hz)
