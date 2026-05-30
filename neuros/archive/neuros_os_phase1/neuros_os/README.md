# NEUROS OS — Phase 1: Basic Robot Support

> **One OS. Every Robot. Zero Exceptions.**  
> Phase 1 of 4 — Domain A: Zephyr / Arduino / Simulator

---

## What is NEUROS OS?

NEUROS is a universal robot operating system that runs on every robot —
from a $3 Arduino blinking an LED to a surgical robot in an operating theatre.

**Phase 1** delivers the foundation: a working kernel, pub/sub bus, hardware
abstraction layer, and Python API that any beginner can use on day one.

```
pip install neuros
```

---

## 30-Second Quickstart

```python
from neuros import Robot, spin

robot = Robot(name="blinker", board="simulator")
robot.start()

robot.pin("LED", pin=13, mode="output")

@robot.every(hz=1)
def blink():
    robot.toggle("LED")
    print("blink!")

spin(robot)   # Ctrl+C to stop
```

---

## Architecture: 10 Layers + Kernel

```
L0  Developer Experience    ← You are here (Python API, decorator mode)
L1  Application Layer       ← Mission logic, task execution
L2  Domain Plugins          ← Perception, planning, control
L3  AI Core                 ← LLM orchestrator (Phase 3 activates this)
L4  Neural Bus              ← Pub/sub backbone (NeuralBus)
L5  Data Layer              ← Logs, bags, model store
L6  Universal HAL           ← Hardware abstraction (THIS PHASE)
L7  Real-Time Monitoring    ← Axis viewer, frame counter
L8  Simulation Engine       ← Digital twin (SimulatorHAL)
────────────────────────────
 K  NEUROS Kernel           ← Heartbeat, watchdog, scheduler (THIS PHASE)
```

---

## Phase 1 Deliverables

| Component          | Status | Notes |
|--------------------|--------|-------|
| `Kernel`           | ✅     | Node lifecycle, watchdog, emergency stop |
| `NeuralBus`        | ✅     | Pub/sub, wildcards, service calls, QoS |
| `Scheduler`        | ✅     | Priority-based, overrun detection |
| `Watchdog`         | ✅     | Software watchdog, auto-restart |
| `SimulatorHAL`     | ✅     | Full software HAL, noise injection, write log |
| `ArduinoHAL`       | ✅     | NSP serial protocol (needs firmware) |
| `Node` base class  | ✅     | Full lifecycle, pub/sub helpers |
| Python API         | ✅     | `Robot`, decorator `@every`, pin shortcuts |
| CLI                | ✅     | `neuros init`, `run`, `status`, `doctor` |
| LLM stub           | ✅     | Rule-based intent parser, wired for Phase 3 |
| Tests              | ✅     | 48/48 passing |
| `pip install`      | ✅     | `pyproject.toml`, zero mandatory deps |

---

## Three-Domain Architecture

```
Domain A  ─ Zephyr / MCU / Arduino      ← Phase 1 (this build)
Domain B  ─ Linux RT + ROS2             ← Phase 2 (Month 2–4)
Domain C  ─ QNX Certified               ← Phase 4+ (Year 2)
```

The kernel, bus, and node APIs are domain-agnostic.
Plug in Domain B (ROS2 bridge) without changing any node code.

---

## Hardware Support (Phase 1)

| Board class        | HAL driver       | Status |
|--------------------|------------------|--------|
| Development / CI   | SimulatorHAL     | ✅ works anywhere |
| Arduino (all)      | ArduinoHAL       | ✅ needs pyserial + firmware |
| Raspberry Pi       | RaspberryPiHAL   | 🔲 Phase 2 |
| Jetson Nano/Orin   | JetsonHAL        | 🔲 Phase 2 |
| ROS2 robots        | ROS2Bridge       | 🔲 Phase 2 |

Auto-detection order: RPi.GPIO → Arduino serial scan → SimulatorHAL.

---

## Node API (Power User)

```python
from neuros import Robot, Node, spin, NodePriority

class MotorNode(Node):
    def configure(self):
        self.hal.pin("MOTOR_EN",  board_pin=8,  mode="output")
        self.hal.pin("MOTOR_PWM", board_pin=9,  mode="pwm")

    def on_activate(self):
        self.subscribe("/robot/cmd/velocity", self.on_cmd)

    def on_cmd(self, msg):
        speed = msg.data.get("linear", 0.0)
        self.hal.pwm_write(9, abs(speed))
        self.hal.write("MOTOR_EN", int(speed > 0))

    def tick(self):
        self.publish("/robot/status/motor", {"running": True})

robot = Robot("rover", board="arduino", port="/dev/ttyUSB0")
robot.add_node(MotorNode("motor", hz=100, priority=NodePriority.HIGH))
robot.start()
spin(robot)
```

---

## Neural Bus

```python
from neuros import NeuralBus, Message

bus = NeuralBus()

# Exact topic
bus.subscribe("/robot/sensor/imu", on_imu)

# Wildcard — any sensor
bus.subscribe("/robot/sensor/*", on_any_sensor)

# Everything — logger / monitor
bus.subscribe("#", on_everything)

# Publish
bus.publish(Message(topic="/robot/sensor/imu", data={"ax": 0.1, "gz": 0.0}))
```

---

## CLI

```bash
# Create a new robot project
neuros init my-robot
cd my-robot
python robot.py

# Check system
neuros doctor
neuros status
neuros version
```

---

## Running the Tests

```bash
git clone https://github.com/neuros-os/neuros
cd neuros
PYTHONPATH=. python -m pytest tests/ -v
# → 48 passed in 1.08s
```

---

## Phase Roadmap

| Phase | Timeline  | Domain | What ships |
|-------|-----------|--------|------------|
| **1** | **M1–2**  | **A**  | **Kernel + Bus + HAL + Python API** ← YOU ARE HERE |
| 2     | M2–4      | B      | ROS2 bridge, Linux RT, RPi HAL |
| 3     | M4–6      | A+B    | Real LLM, auto node generation |
| 4     | M6–10     | A+B+C  | Industrial + QNX + Universal HAL |
| 5     | Y2+       | All    | Medical / Space certification (DO-178C) |

---

## Design Principles

1. **Zero mandatory dependencies** — runs on any Python 3.9+ with no installs
2. **Beginner-first** — decorator API requires zero OS knowledge
3. **Expert-ready** — full C++/Rust API in Phase 4, same concepts throughout
4. **Hardware-agnostic** — swap Arduino → Pi → GPU cluster, node code unchanged
5. **AI-native** — LLM orchestrator is a first-class layer, not a plugin
6. **Domain-isolated** — Zephyr / Linux RT / QNX never share memory (Phase 4)
7. **Test-driven** — 48 tests on day one, CI from commit one

---

*NEUROS OS v0.1.0-phase1 · Domain A · "One OS. Every Robot."*
