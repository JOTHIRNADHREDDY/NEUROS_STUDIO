"""
example_03_ai_robot.py
=======================
NEUROS OS — Example 3: AI-Controlled Robot (Phase 1 Stub)

Demonstrates the LLM Orchestrator (Phase 1 rule-based stub).
Type natural language commands at the prompt:
    > blink the led at 2 hz
    > move forward
    > stop
    > status

In Phase 3, these commands will call a real LLM and dynamically
generate new nodes. The interface is already wired.

Architecture (all layers active)
---------------------------------
  L0  Developer Experience   ← AI chat prompt + decorator API
  L3  AI Core                ← LLMOrchestrator (stub)
  L4  Neural Bus             ← all messages routed through
  L6  HAL                    ← SimulatorHAL (or Arduino)
  K   Kernel                 ← watchdog + scheduler running
  ─────────────────────────────────────────────────────
  Nodes:
    SafetySupervisor  — always-on guard
    IMUNode           — orientation data
    LEDNode           — status feedback
    BuzzerNode        — audio alerts
    MotorNode × 2     — differential drive

Run:
    python examples/example_03_ai_robot.py
"""

import threading
import logging
import sys

from neuros import Robot, spin
from neuros.nodes import IMUNode, LEDNode, BuzzerNode, MotorNode, NodePriority
from neuros.safety import SafetySupervisor
from neuros.ai import LLMOrchestrator

log = logging.getLogger("ai_robot")


# ── Build robot ─────────────────────────────────────────────────────────────
robot = Robot(name="ai_robot", board="simulator", kernel_hz=500)

robot.add_node(SafetySupervisor(battery_crit_v=3.0))
robot.add_node(IMUNode("imu", hz=50))
robot.add_node(LEDNode("status", pin=13, mode="pwm"))
robot.add_node(BuzzerNode("buzzer", pin=8, passive=False))
robot.add_node(MotorNode("motor_left",  pin_en=5,  pin_in1=6,  pin_in2=7))
robot.add_node(MotorNode("motor_right", pin_en=10, pin_in1=11, pin_in2=12))

robot.pin("STATUS_LED", pin=13, mode="output")
robot.start()


# ── AI Orchestrator ─────────────────────────────────────────────────────────
llm = LLMOrchestrator()

# Subscribe to all bus messages for logging
def on_any(msg):
    if "/system" in msg.topic or "/actuator" in msg.topic:
        log.debug("BUS  %-40s %s", msg.topic, msg.data)

robot.subscribe("#", on_any)


# ── Terminal chat loop (runs in background thread) ──────────────────────────
def chat_loop():
    print("""
╔══════════════════════════════════════════════════════╗
║  NEUROS OS — Example 3: AI-Controlled Robot          ║
║  Type natural language commands, or 'quit' to exit  ║
╚══════════════════════════════════════════════════════╝

  Try:
    > blink the led at 2 hz
    > move forward
    > turn left
    > stop
    > status
    > quit
""")
    while True:
        try:
            text = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            robot.stop()
            sys.exit(0)

        if not text:
            continue
        if text.lower() in ("quit", "exit", "q"):
            print("  Shutting down...")
            robot.stop()
            sys.exit(0)

        # Send to LLM orchestrator
        intent = llm.parse(text)
        if intent and intent.confidence > 0:
            print(f"  ✅ Intent: [{intent.action}] params={intent.params}")
            llm.execute_on(robot, text)
        else:
            print(f"  ❓ Unknown command. Try: 'blink led', 'move forward', 'stop', 'status'")


chat_thread = threading.Thread(target=chat_loop, daemon=True)
chat_thread.start()

spin(robot)
