# NEUROS — AI Middleware for Robotics

> **The easiest way to build AI-powered robots.**

---

## What is NEUROS?

NEUROS is **AI Middleware for Robotics** that sits above your existing OS and frameworks (Linux, ROS2, Zephyr, ESP-IDF) and provides AI orchestration, unified robot APIs, skill execution, and safety validation.

```bash
pip install neuros
```

**NEUROS does NOT replace** Linux, ROS2, or Zephyr.
**NEUROS enhances them** with AI agents, a unified skill engine, and great DX.

---

## 30-Second Quickstart

```python
from neuros import Robot

robot = Robot(name="rover", board="simulator")
robot.start()

robot.move_forward(speed=0.5, duration_s=2.0)
robot.navigate_to("kitchen")
robot.detect_object("red bottle")
robot.stop()
```

---

## Architecture

```
User
 ↓
Studio (Web IDE)
 ↓
LLM / Natural Language
 ↓
Planner Agent
 ↓
Skill Engine
 ↓
Execution Manager
 ↓
Safety Sandbox + Validator
 ↓
Universal HAL
 ↓
ROS2 / ESP32 / Arduino / Raspberry Pi / Jetson
```

---

## Core Principles

1. **AI Middleware, not an OS** — sits above Linux/ROS2/Zephyr
2. **Python never controls PWM** — sends high-level commands, hardware executes
3. **Skills are the only hardware interface** — no direct motor access
4. **Safety-first** — every command passes through Sandbox → Validator
5. **Zero mandatory dependencies** — `pip install neuros` just works
6. **Capability-aware** — robots declare what they can do
7. **Plugin-extensible** — add YOLO, Whisper, Isaac via manifest.yaml

---

## Monorepo Structure

```
neuros/
├── sdk/            # pip install neuros (Robot class, CLI, decorators)
├── runtime/        # Robot daemon (Execution Manager, Lifecycle, API)
├── bus/            # Neural Bus (Pub/Sub event routing)
├── bridge/         # ROS2 Bridge (enhance, don't replace)
├── hal/            # Universal HAL (ESP32, Arduino, Pi, Jetson, Simulator)
├── devices/        # Device Registry (YAML-based hardware definitions)
├── capabilities/   # Capability System (mobility, vision, manipulation...)
├── skills/         # Skill Engine (v1/v2 versioned skills)
├── safety/         # Safety Layer (Validator, Watchdog, E-Stop, Sandbox)
├── agents/         # AI Agents (Planner, Robotics, Vision, Memory, Code)
├── memory/         # Memory System (short-term, long-term, episodic)
├── plugins/        # Plugin System (manifest-based extensions)
├── config/         # Unified Configuration (YAML)
├── schemas/        # Event Schemas (typed events, no raw dicts)
├── observability/  # Metrics, Traces, Structured Logs
├── studio/         # NEUROS Studio (Next.js Web IDE)
├── data/           # SQLite databases
├── tests/          # Test suite
└── archive/        # Old phase code (preserved, not active)
```

---

## Capability System

```python
if robot.has_capability("manipulation"):
    robot.pick_object("red bottle")
```

| Robot Type | Mobility | Navigation | Vision | Manipulation | Speech |
|-----------|----------|------------|--------|-------------|--------|
| Rover     | ✅       | ✅         | ✅     | ❌          | ❌     |
| Arm       | ❌       | ❌         | ✅     | ✅          | ❌     |
| Drone     | ✅       | ✅         | ✅     | ❌          | ❌     |
| Humanoid  | ✅       | ✅         | ✅     | ✅          | ✅     |

---

## Skills (v1)

| Category      | Skills                          |
|---------------|---------------------------------|
| Mobility      | Move, Stop, Turn, Reverse       |
| Navigation    | NavigateTo, Explore, FollowPath |
| Vision        | DetectObject, TrackObject, Scan |
| Manipulation  | Pick, Place, Grip, Release      |
| Diagnostics   | SystemCheck, SelfTest           |

---

## Safety Layer

Every command passes through:

```
Skill → Sandbox → Validator → HAL
```

**Validator checks:** PWM limits, speed limits, voltage, temperature, workspace bounds, joint limits.

**Emergency Stop** bypasses everything — directly stops all actuators.

---

## ROS2 Strategy

NEUROS **enhances** ROS2, never replaces it.

```python
robot.navigate_to("kitchen")
# → NEUROS translates → ROS2 Nav2 action goal
```

---

## Natural Language Control

```python
import asyncio

async def main():
    robot = Robot(name="rover", board="simulator")
    robot.start()
    result = await robot.execute("Find the red bottle in the kitchen")
    print(result)

asyncio.run(main())
```

---

## Quick Install

```bash
pip install neuros               # zero dependencies
pip install neuros[arduino]      # + pyserial
pip install neuros[rpi]          # + RPi.GPIO
pip install neuros[ai]           # + openai
pip install neuros[runtime]      # + FastAPI, SQLAlchemy, etc.
pip install neuros[all]          # everything
```

---

## MVP Success Criteria

- ✅ Control ESP32 / Pi / Jetson robots
- ✅ Execute AI-generated missions
- ✅ Bridge to ROS2
- ✅ Enforce safety limits
- ✅ Provide visual debugging (Studio)
- ✅ Run end-to-end without cloud dependency

---

*NEUROS v2.0.0-alpha · "AI Middleware for Robotics"*
