# NEUROS OS — Phase 2: Linux RT + ROS2 Bridge + Navigation + Fleet

> **One OS. Every Robot. Zero Exceptions.**  
> Phase 2 of 4 — Domain B: Linux RT / ROS2 / Jetson / Navigation / Fleet

---

## Phase 2 at a Glance

```
Phase 1 (Domain A) ✅  Arduino + Pi + Simulator + Basic nodes
Phase 2 (Domain B) ✅  Linux RT + ROS2 Bridge + Jetson + Navigation + Fleet
Phase 3            🔲  Real LLM + Auto node generation (Month 4-6)
Phase 4            🔲  Industrial + QNX + Certified (Month 6-10)
```

**New in Phase 2:**
- **Real-Time Kernel** — PREEMPT-RT scheduler with SCHED_FIFO, CPU pinning, mlockall
- **Hardware** — RaspberryPiHAL (GPIO/I2C/PWM/SPI/UART) + JetsonHAL (GPU/CUDA)
- **ROS2 Bridge** — zero-migration: wraps existing ROS2 nodes, mirrors topics bidirectionally
- **DDS/Zenoh Bridge** — cross-process and cross-machine Neural Bus transparency
- **Navigation stack** — Odometry + Obstacle Avoidance + Waypoint Navigator (pure-pursuit)
- **Vision** — CameraNode (OpenCV) + LiDARNode (RPLiDAR)
- **Fleet** — FleetManager + FleetAgent for multi-robot coordination
- **RT Monitor** — live terminal dashboard + HTTP JSON endpoint
- **Process Isolation** — per-node-group subprocess management with auto-restart

---

## Complete Architecture (Phase 1 + Phase 2)

```
╔══════════════════════════════════════════════════════════════════════════╗
║   L0  DEVELOPER EXPERIENCE                                               ║
║   ┌─────────────┬─────────────┬──────────────┬───────────┬────────────┐ ║
║   │Beginner Mode│ Python Mode │  IDE/Pro Mode │Expert Mode│Certified   │ ║
║   │Plain English│ pip install │  CLI + Canvas │C++/Rust   │DO-178C     │ ║
║   │No coding    │ Notebooks   │  Code gen     │ROS2 bridge│Phase 4     │ ║
║   └─────────────┴─────────────┴──────────────┴───────────┴────────────┘ ║
╠══════════════════════════════════════════════════════════════════════════╣
║   L1  APPLICATION LAYER                                                  ║
║   LED blink → Drive forward → AI Models → Mission Logic → Industrial    ║
╠══════════════════════════════════════════════════════════════════════════╣
║   L2  DOMAIN PLUGINS · PERCEPTION · PLANNING · CONTROL                   ║
║   ┌────────────┬──────────────┬─────────────┬────────────────────────┐  ║
║   │All Domains │  Perception  │  Planning   │       Control          │  ║
║   │Basic/STEM  │  Camera/YOLO │  Nav2/Path  │  GPIO→PID→Hard RT      │  ║
║   │UAV/Marine  │  LiDAR Fuse  │  MoveIt     │  Manual/Auto/Actuator  │  ║
║   │Medical/    │  Depth/Force │  RL Engine  │  Safety Critical       │  ║
║   │Space/IRB   │  Thermal/IMU │  Multi-robot│  (Phase 4)             │  ║
║   └────────────┴──────────────┴─────────────┴────────────────────────┘  ║
╠══════════════════════════════════════════════════════════════════════════╣
║   L3  AI CORE LAYER  ◄── Phase 3 activates real LLM here                ║
║   ┌──────────────┬────────────┬──────────────┬───────────────────────┐  ║
║   │LLM Orchestr. │  RL Engine │ Model Registry│    Auto-Config        │  ║
║   │"blink led"   │  PPO/SAC   │ YOLO/ONNX    │  Auto-detect HW       │  ║
║   │→ code (stub) │  sim→real  │ TensorRT     │  Self-healing nodes   │  ║
║   └──────────────┴────────────┴──────────────┴───────────────────────┘  ║
╠══════════════════════════════════════════════════════════════════════════╣
║   L4  UNIFIED MIDDLEWARE — NEURAL BUS                                    ║
║   ┌──────────┬──────────┬───────────┬──────────┬──────────────────────┐ ║
║   │ Pub/Sub  │ Services │  RT DDS   │ Security │  Cross-process Comm  │ ║
║   │ Wildcard │ Req/Resp │ Soft→Hard │ SROS2    │  Zenoh P2P  ← NEW   │ ║
║   │ "#" glob │ Timeout  │ QoS       │ TLS      │  ROS2 Bridge ← NEW  │ ║
║   └──────────┴──────────┴───────────┴──────────┴──────────────────────┘ ║
╠══════════════════════════════════════════════════════════════════════════╣
║   L5  DATA & STORAGE                                                     ║
║   1KB chip → SD card → Sensor Bags → Mission History → Cloud sync       ║
╠══════════════════════════════════════════════════════════════════════════╣
║   L6  UNIVERSAL HAL                                                      ║
║   ┌───────────┬───────────┬──────────────┬────────────┬───────────────┐ ║
║   │ArduinoHAL │    NEW    │     NEW      │    NEW     │   NEW         │ ║
║   │NSP serial │ RpiHAL    │  JetsonHAL   │ LinuxRTHAL │ SimulatorHAL  │ ║
║   │Phase 1 ✅ │GPIO/I2C/  │  Jetson.GPIO │(Phase 2+)  │ Full SW sim   │ ║
║   │           │PWM/SPI    │  CUDA/TensorRT│            │ Phase 1 ✅   │ ║
║   │           │UART ✅    │  GPU Memory  │            │               │ ║
║   └───────────┴───────────┴──────────────┴────────────┴───────────────┘ ║
║   Auto-detect: Jetson → RPi → Arduino → Simulator                       ║
╠══════════════════════════════════════════════════════════════════════════╣
║   L7  REAL-TIME MONITORING  ← NEW Phase 2                                ║
║   RTMonitor: terminal dashboard + HTTP JSON API                          ║
║   LatencyMonitor: per-task µs histogram, P50/P95/P99/P999               ║
║   RTScheduler metrics: overrun count, avg/max latency                   ║
╠══════════════════════════════════════════════════════════════════════════╣
║   L8  SIMULATION ENGINE + DIGITAL TWIN                                   ║
║   Physics(2D→3D) · Virtual sensors · Environments · HIL testing         ║
╠══════════════════════════════════════════════════════════════════════════╣
║   K   NEUROS KERNEL  (always running)                                    ║
║   ┌──────────────────────────────────────────────────────────────────┐  ║
║   │ Node lifecycle · Watchdog · Emergency Stop · Resource Allocator  │  ║
║   │ RTScheduler (SCHED_FIFO bands) ← NEW  ·  ProcessIsolator ← NEW  │  ║
║   │ CPU Affinity ← NEW  ·  MemoryLocker (mlockall) ← NEW            │  ║
║   └──────────────────────────────────────────────────────────────────┘  ║
╠══════════════════════════════════════════════════════════════════════════╣
║   BRIDGES  (Phase 2 NEW)                                                 ║
║   ROS2Bridge: rclpy bidirectional topic mirror, node executor wrapping   ║
║   ZenohBridge: cross-process / cross-machine Neural Bus transparency     ║
╠══════════════════════════════════════════════════════════════════════════╣
║   FLEET  (Phase 2 NEW)                                                   ║
║   FleetManager: multi-robot discovery, health monitor, task assignment   ║
║   FleetAgent: per-robot registration, heartbeat, task handler            ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## Hardware Matrix (Phase 1 + 2)

| Board | HAL Driver | Domain | I2C | PWM | UART | GPU | Status |
|-------|-----------|--------|-----|-----|------|-----|--------|
| Arduino (all) | ArduinoHAL | A | ✅ (v2) | ✅ | ✅ | — | ✅ Phase 1 |
| Raspberry Pi 3/4/5 | RaspberryPiHAL | B | ✅ smbus2 | ✅ sw | ✅ | — | ✅ Phase 2 |
| Jetson Nano | JetsonHAL | B | ✅ smbus2 | ✅ sw | ✅ | ✅ | ✅ Phase 2 |
| Jetson AGX Orin | JetsonHAL | B | ✅ | ✅ | ✅ | ✅ 32GB | ✅ Phase 2 |
| Simulator | SimulatorHAL | A/B | ✅ | ✅ | ✅ | — | ✅ Phase 1 |
| Any Linux RT | LinuxRTHAL | B | 🔲 | 🔲 | 🔲 | — | Phase 2+ |
| QNX Neutrino | QNXCertHAL | C | 🔲 | 🔲 | 🔲 | — | Phase 4 |

---

## Node Inventory (Phase 1 + 2)

### Sensor Nodes
| Node | Phase | Topics Published |
|------|-------|-----------------|
| `GPIOSensorNode` | 1 | `/robot/sensor/<name>` |
| `IMUNode` | 1 | `/robot/sensor/imu/{accel,gyro,orientation,full}` |
| `UltrasonicNode` | 1 | `/robot/sensor/ultrasonic/<name>` |
| `LineFollowerNode` | 1 | `/robot/sensor/line/{raw,error,detected}` |
| `TemperatureNode` | 1 | `/robot/sensor/temperature/<name>` |
| `EncoderNode` | 1 | `/robot/sensor/encoder/<name>` |
| `BatteryMonitorNode` | 1 | `/robot/sensor/battery`, `/robot/system/battery_alert` |
| `CameraNode` | **2** | `/robot/vision/camera/<name>/{frame,info,detect,jpeg}` |
| `LiDARNode` | **2** | `/robot/sensor/lidar/<name>/{scan,closest,sectors,status}` |

### Actuator Nodes
| Node | Phase | Topics Subscribed |
|------|-------|------------------|
| `MotorNode` | 1 | `/robot/cmd/motor/<name>`, `/robot/cmd/stop` |
| `ServoNode` | 1 | `/robot/cmd/servo/<name>` |
| `LEDNode` | 1 | `/robot/cmd/led/<name>` |
| `BuzzerNode` | 1 | `/robot/cmd/buzzer/<name>` |

### Navigation Nodes (Phase 2)
| Node | Topics In | Topics Out |
|------|-----------|-----------|
| `OdometryNode` | encoder + IMU | `/robot/nav/odom/{pose,twist}` |
| `ObstacleAvoidanceNode` | LiDAR sectors + sonar | `/robot/cmd/velocity`, `/robot/nav/obstacle/status` |
| `WaypointNavigatorNode` | odom pose + goal | `/robot/cmd/velocity`, `/robot/nav/waypoint/status` |

### System Nodes
| Node | Phase | Function |
|------|-------|---------|
| `SafetySupervisor` | 1 | Battery + node crash + E-stop chain |
| `FleetAgent` | **2** | Robot registration + heartbeat + task handler |

---

## RT Scheduler Bands (Phase 2)

```
Band        Hz range    SCHED_FIFO priority    Typical tasks
─────────────────────────────────────────────────────────────
1000-∞      ≥1000 Hz    80                     IMU, encoder, motor PID
100-999     100–999 Hz  60                     Camera, LiDAR, odometry
10-99       10–99 Hz    40                     Navigation, planning
0-9         <10 Hz      20                     Battery, telemetry, fleet

Fallback (non-RT kernel): SCHED_OTHER (CFS) with warning
```

---

## Quick-Start

```bash
# Install
pip install neuros            # zero mandatory dependencies
pip install neuros[arduino]   # + pyserial for Arduino
pip install neuros[all]       # + numpy, pyserial

# Run examples
PYTHONPATH=. python examples/example_04_autonomous_rover.py
PYTHONPATH=. python examples/example_04_autonomous_rover.py --monitor
PYTHONPATH=. python examples/example_05_fleet.py

# Tests
PYTHONPATH=. python -m pytest tests/ -v    # 139/139 green
```

---

## Minimal Phase 2 Robot

```python
from neuros import Robot, spin, RTMonitor
from neuros.nodes.navigation import OdometryNode, WaypointNavigatorNode
from neuros.nodes.vision import LiDARNode
from neuros.nodes import EncoderNode, MotorNode
from neuros.safety import SafetySupervisor

robot = Robot("rover", board="rpi")   # or "simulator"

robot.add_node(SafetySupervisor())
robot.add_node(LiDARNode("lidar", mode="simulate"))
robot.add_node(EncoderNode("enc_left",  pin_a=17, pin_b=27, hz=500))
robot.add_node(EncoderNode("enc_right", pin_a=22, pin_b=10, hz=500))
robot.add_node(OdometryNode("odom", wheel_base_m=0.15))
robot.add_node(WaypointNavigatorNode("nav"))
robot.add_node(MotorNode("motor_l", pin_en=12, pin_in1=23, pin_in2=24))
robot.add_node(MotorNode("motor_r", pin_en=13, pin_in1=25, pin_in2=8))

robot.start()

# Queue a patrol mission
nav = robot._nodes[list(robot._nodes)[6]]   # WaypointNavigatorNode
nav.add_waypoint(2.0, 0.0)
nav.add_waypoint(2.0, 2.0)
nav.add_waypoint(0.0, 0.0)

# Live dashboard
RTMonitor(robot, refresh_hz=4, http_port=8765).start()

spin(robot)
```

---

## ROS2 Bridge (zero migration)

```python
from neuros.bridge.ros2 import ROS2Bridge

bridge = ROS2Bridge(robot)
bridge.mirror_topic("/scan",    direction="ros2→neuros")   # LiDAR from ROS2
bridge.mirror_topic("/cmd_vel", direction="neuros→ros2")   # velocity to Nav2
bridge.mirror_topic("/tf",      direction="ros2→neuros")   # transforms
bridge.start()
# All existing ROS2 nodes see NEUROS as a peer — zero code changes
```

---

## Fleet Coordination

```python
from neuros import FleetManager, NeuralBus

fleet = FleetManager(shared_bus)
fleet.start()

# Assign task to a specific robot
fleet.assign_task("rover_a", {"mission": "patrol_zone_1"})

# Emergency stop all robots instantly
fleet.emergency_stop_all("coordinator command")

# Monitor
print(fleet.summary())
# → {"total": 3, "online": 3, "robots": [...]}
```

---

## Domain Isolation Model

```
Domain A (Phase 1)          Domain B (Phase 2)          Domain C (Phase 4)
────────────────────         ─────────────────────        ───────────────────
Zephyr / MCU                 Linux RT (PREEMPT-RT)        QNX Neutrino 7.x
Arduino / ESP32              Raspberry Pi / Jetson         Safety-critical
SCHED_OTHER (CFS)            SCHED_FIFO (bands)           Adaptive partitions
Soft RT ~5ms jitter          Soft RT <500µs jitter        Hard RT <10µs
Single process               Multi-process isolated        Hardware partitioned
threading.Thread             ProcessIsolator              QNX pulse scheduler
SimulatorHAL / ArduinoHAL   RpiHAL / JetsonHAL           QNXCertHAL
No certification             Development/production        DO-178C / IEC 62304
```

---

*NEUROS OS v0.2.0-phase2 · Domain B · "One OS. Every Robot."*
