"""NEUROS OS v0.3.0-phase3"""
__version__ = "0.3.0-phase3"

# Phase 1 core
from neuros.api.robot   import Robot
from neuros.bus.bus     import NeuralBus
from neuros.kernel.core import Kernel
from neuros.nodes.base  import Node, NodeState, NodePriority
from neuros.bus.message import Message, Topic

# Phase 2
from neuros.bridge.ros2 import ROS2Bridge
from neuros.bridge.dds  import ZenohBridge
from neuros.kernel.rt   import RTScheduler, LatencyMonitor
from neuros.fleet       import FleetManager, FleetAgent
from neuros.monitor     import RTMonitor

# Phase 3 AI Core
from neuros.ai.llm.orchestrator  import LLMOrchestrator, Intent, LLMProvider
from neuros.ai.planner.mission   import MissionPlanner, MissionGraph, MissionNode
from neuros.ai.codegen.generator import NodeCodegen, GeneratedNode
from neuros.ai.models.registry   import ModelRegistry, InferenceResult
from neuros.ai.rl.engine         import RLEngine, RLPolicy, RLEnvironment
from neuros.ai.vision.detector   import VisionAI, Detection
from neuros.ai.voice.interface   import VoiceInterface
from neuros.ai.autoconfig        import AutoConfig, ParameterTuner
from neuros.ai.anomaly           import AnomalyDetector, AnomalyEvent

def spin(robot, *, hz=100):
    robot.spin(hz=hz)
