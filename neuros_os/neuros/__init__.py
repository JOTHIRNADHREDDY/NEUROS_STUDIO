"""
NEUROS OS — Universal Robot Operating System
"One OS. Every Robot. Zero Exceptions."

Architecture: 3-Domain model
  Domain A — Zephyr / MCU / Arduino
  Domain B — Linux RT / ROS2 / Jetson
  Domain C — QNX Certified (Phase 4+)

10-Layer Stack:
  L0  Developer Experience   — Python API, decorator mode, plain English
  L1  Application Layer      — Mission logic, task execution
  L2  Domain Plugins         — Perception, planning, control
  L3  AI Core                — LLM orchestrator, RL engine, code generation
  L4  Neural Bus             — Pub/sub backbone (NeuralBus, DDS/Zenoh)
  L5  Data Layer             — Logs, bags, model store
  L6  Universal HAL          — Arduino / RPi / Jetson / Simulator
  L7  Real-Time Monitoring   — Dashboard, latency histograms, HTTP API
  L8  Simulation Engine      — Digital twin, physics, virtual sensors
   K  NEUROS Kernel          — Heartbeat, watchdog, scheduler, RT bands

Public surface:
    from neuros import Robot, Node, Message, spin
    from neuros import NeuralBus, Kernel
    from neuros import ROS2Bridge, ZenohBridge
    from neuros import FleetManager, FleetAgent, RTMonitor
    from neuros import LLMOrchestrator, MissionPlanner, RLEngine
"""

__version__ = "3.0.0"
__author__  = "NEUROS OS Team"

# ── Phase 1 Core ──────────────────────────────────────────────────────────
from neuros.api.robot   import Robot                            # noqa: F401
from neuros.bus.bus     import NeuralBus                        # noqa: F401
from neuros.kernel.core import Kernel                           # noqa: F401
from neuros.nodes.base  import Node, NodeState, NodePriority    # noqa: F401
from neuros.bus.message import Message, Topic                   # noqa: F401

# ── Phase 2: Linux RT + ROS2 + Fleet ──────────────────────────────────────
from neuros.bridge.ros2 import ROS2Bridge                       # noqa: F401
from neuros.bridge.dds  import ZenohBridge                      # noqa: F401
from neuros.kernel.rt   import RTScheduler, LatencyMonitor      # noqa: F401
from neuros.fleet       import FleetManager, FleetAgent         # noqa: F401
from neuros.monitor     import RTMonitor                        # noqa: F401

# ── Phase 2: Developer Experience ─────────────────────────────────────────
from neuros.launch      import LaunchConfig, LaunchRunner       # noqa: F401
from neuros.params      import ParameterManager, ParamGroup     # noqa: F401
from neuros.bags        import BagRecorder, BagPlayer, BagAnalyzer  # noqa: F401
from neuros.inspector   import Inspector                        # noqa: F401

# ── Phase 3: AI Core ─────────────────────────────────────────────────────
from neuros.ai.llm.orchestrator  import LLMOrchestrator, Intent, LLMProvider   # noqa: F401
from neuros.ai.planner.mission   import MissionPlanner, MissionGraph, MissionNode  # noqa: F401
from neuros.ai.codegen.generator import NodeCodegen, GeneratedNode              # noqa: F401
from neuros.ai.models.registry   import ModelRegistry, InferenceResult          # noqa: F401
from neuros.ai.rl.engine         import RLEngine, RLPolicy, RLEnvironment       # noqa: F401
from neuros.ai.vision.detector   import VisionAI, Detection                     # noqa: F401
from neuros.ai.voice.interface   import VoiceInterface                          # noqa: F401
from neuros.ai.autoconfig        import AutoConfig, ParameterTuner              # noqa: F401
from neuros.ai.anomaly           import AnomalyDetector, AnomalyEvent           # noqa: F401
from neuros.ai.watchdog          import NodeWatchdog, RestartPolicy             # noqa: F401
from neuros.ai.hwdetect          import HardwareDetector, DetectedBoard         # noqa: F401


# ── Convenience ───────────────────────────────────────────────────────────
def spin(robot: "Robot", *, hz: int = 100) -> None:
    """Block and run the robot event loop at the given rate."""
    robot.spin(hz=hz)
