"""
example_06_ai_robot.py
=======================
NEUROS OS Phase 3 — Full AI Robot

All AI layers active:
  LLMOrchestrator   → parse natural language commands (stub/Anthropic/OpenAI/Ollama)
  MissionPlanner    → multi-step mission from one sentence
  NodeCodegen       → generate new nodes at runtime from description
  AnomalyDetector   → monitor all sensor streams
  AutoConfig        → hardware-aware parameter tuning
  VoiceInterface    → voice commands (stub mode → stdin)

Run:
    python examples/example_06_ai_robot.py
    python examples/example_06_ai_robot.py --provider anthropic
    python examples/example_06_ai_robot.py --provider ollama
"""

import argparse, logging, threading, sys, time

parser = argparse.ArgumentParser(description="NEUROS Phase 3 — AI Robot")
parser.add_argument("--provider",  default="auto",       help="LLM provider: auto/stub/anthropic/openai/ollama")
parser.add_argument("--board",     default="simulator")
parser.add_argument("--monitor",   action="store_true")
parser.add_argument("--voice",     action="store_true",  help="Enable voice interface (stdin stub)")
parser.add_argument("--log",       default="WARNING")
args = parser.parse_args()

logging.basicConfig(level=getattr(logging, args.log.upper(), logging.WARNING),
                    format="%(asctime)s %(name)s %(message)s", datefmt="%H:%M:%S")

from neuros import (Robot, spin, RTMonitor,
                    LLMOrchestrator, MissionPlanner, NodeCodegen,
                    AnomalyDetector, AutoConfig, VoiceInterface,
                    FleetAgent)
from neuros.safety import SafetySupervisor
from neuros.nodes  import (IMUNode, EncoderNode, BatteryMonitorNode,
                            MotorNode, LEDNode, BuzzerNode)
from neuros.nodes.vision     import LiDARNode
from neuros.nodes.navigation import OdometryNode, ObstacleAvoidanceNode, WaypointNavigatorNode
from neuros.ai.models.registry import ModelRegistry

# ── Build robot ──────────────────────────────────────────────────────────────
robot = Robot(name="ai_robot", board=args.board, kernel_hz=500)

robot.add_node(SafetySupervisor(battery_crit_v=6.0))
robot.add_node(IMUNode("imu",    hz=50))
robot.add_node(LiDARNode("lidar", mode="simulate", hz=10))
robot.add_node(EncoderNode("enc_left",  pin_a=17, pin_b=27, hz=200))
robot.add_node(EncoderNode("enc_right", pin_a=22, pin_b=10, hz=200))
robot.add_node(BatteryMonitorNode("battery", pin=26, profile="lipo_2s",
                                  divider_ratio=4.0, hz=0.5))
robot.add_node(OdometryNode("odom", wheel_base_m=0.15, hz=50))
robot.add_node(ObstacleAvoidanceNode("obstacle_avoidance", lidar_name="lidar", hz=10))
nav = WaypointNavigatorNode("nav", hz=10)
robot.add_node(nav)
robot.add_node(MotorNode("motor_left",  pin_en=12, pin_in1=23, pin_in2=24))
robot.add_node(MotorNode("motor_right", pin_en=13, pin_in1=25, pin_in2=8))
robot.add_node(LEDNode("status_led", pin=4, mode="pwm"))
robot.add_node(BuzzerNode("buzzer",   pin=18, passive=False))
robot.add_node(FleetAgent(robot, robot_id="ai_robot_01", hz=1))

robot.start()

# ── Velocity bridge ─────────────────────────────────────────────────────────
def on_vel(msg):
    v, w = float(msg.data.get("linear",0)), float(msg.data.get("angular",0))
    WB = 0.15
    l, r = v - w*WB/2, v + w*WB/2
    m = max(abs(l), abs(r), 0.001)
    if m > 0.5: l, r = l/m*0.5, r/m*0.5
    robot.publish("cmd/motor/motor_left",  {"speed": l/0.5})
    robot.publish("cmd/motor/motor_right", {"speed": r/0.5})
robot.subscribe("/robot/cmd/velocity", on_vel)

# ── Model registry ───────────────────────────────────────────────────────────
registry = ModelRegistry()
registry.register("detector", "", runtime="stub")

# ── LLM orchestrator ─────────────────────────────────────────────────────────
llm = LLMOrchestrator(provider=args.provider, robot=robot)

# ── Mission planner ──────────────────────────────────────────────────────────
planner = MissionPlanner(llm)

# ── Node code generator ───────────────────────────────────────────────────────
codegen = NodeCodegen(llm)

# ── Anomaly detector ─────────────────────────────────────────────────────────
anomaly = AnomalyDetector(robot, z_threshold=4.0, silence_s=10.0)
anomaly.on_anomaly(lambda e:
    print(f"\n  ⚠  ANOMALY [{e.severity.upper()}] {e.type} on {e.topic}: {e.detail}"))
anomaly.start()

# ── AutoConfig ────────────────────────────────────────────────────────────────
autoconf = AutoConfig(robot, llm=llm)
suggestions = autoconf.analyse()
applied = autoconf.apply_all(suggestions)
if applied:
    print(f"  ⚙  AutoConfig applied {applied} parameter adjustments")

# ── Voice interface ───────────────────────────────────────────────────────────
voice = VoiceInterface(robot, llm, wake_word="neuros", stt_backend="stub")
if args.voice:
    voice.start()

# ── Monitor ───────────────────────────────────────────────────────────────────
if args.monitor:
    RTMonitor(robot, refresh_hz=2, compact=True).start()

# ── Inject simulated LiDAR obstacle ──────────────────────────────────────────
lidar_node = next((n for n in robot._nodes.values() if n.name == "lidar"), None)
if lidar_node:
    lidar_node.inject_obstacle(0, 2.5)

robot.publish("cmd/buzzer/buzzer",  {"pattern": "startup"})
robot.publish("cmd/led/status_led", {"pattern": "pulse", "hz": 1})

# ── Chat loop ─────────────────────────────────────────────────────────────────
BANNER = """
╔═══════════════════════════════════════════════════════════════╗
║  NEUROS OS Phase 3 — AI Robot (All Layers Active)            ║
║  Provider : {provider:<12}  Board : {board}
║  Commands: natural language or:                              ║
║    mission: <description>   → run multi-step mission          ║
║    codegen: <description>   → generate + install new node     ║
║    autoconf                 → analyse + apply config          ║
║    anomaly                  → show anomaly summary            ║
║    quit                     → exit                            ║
╚═══════════════════════════════════════════════════════════════╝
"""
print(BANNER.format(provider=args.provider, board=args.board))

def chat_loop():
    while True:
        try:
            text = input("  NEUROS> ").strip()
        except (EOFError, KeyboardInterrupt):
            robot.stop(); sys.exit(0)
        if not text:
            continue
        if text.lower() in ("quit","exit","q"):
            robot.stop(); sys.exit(0)

        if text.lower().startswith("mission:"):
            desc    = text[8:].strip()
            graph   = planner.plan(desc)
            print(f"\n  📋 Mission planned ({len(graph)} steps):")
            print("  " + graph.summary().replace("\n", "\n  "))
            planner.execute(graph, robot)

        elif text.lower().startswith("codegen:"):
            desc = text[8:].strip()
            print(f"  🔧 Generating node: {desc}")
            gen  = codegen.generate(desc)
            if gen.success:
                node = gen.node_class(gen.node_name, hz=5.0)
                robot.add_node(node)
                print(f"  ✅ Installed: {gen.class_name}")
            else:
                print(f"  ❌ Error: {gen.error}")

        elif text.lower() == "autoconf":
            s = autoconf.analyse()
            n = autoconf.apply_all(s)
            print(f"  ⚙  Applied {n}/{len(s)} config suggestions")

        elif text.lower() == "anomaly":
            summ = anomaly.summary()
            print(f"  🔍 Anomaly summary: {summ}")
            for ev in anomaly.recent_events[-5:]:
                print(f"     [{ev.severity}] {ev.type} {ev.topic}: {ev.detail}")

        else:
            intent = llm.parse(text)
            if intent.is_valid():
                print(f"  → {intent.action} {intent.params} ({intent.provider}, {intent.latency_ms:.0f}ms)")
                llm.execute_on(robot, text)
            else:
                print("  ❓ Unknown command. Try: 'patrol the room', 'blink led', 'stop'")

thread = threading.Thread(target=chat_loop, daemon=True)
thread.start()
spin(robot)
