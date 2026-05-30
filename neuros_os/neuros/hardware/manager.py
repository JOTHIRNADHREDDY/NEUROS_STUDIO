"""
NEUROS OS — Library Manager
Discovers, installs, and manages libraries compatible with your installed hardware.
"""

import json
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from neuros.hardware.boards import (
    TIER_BASIC, TIER_INTER, TIER_ADVANCED, TIER_EXPERT, TIER_CRITICAL,
)

# ── Library storage ───────────────────────────────────────────────
LIB_REGISTRY_PATH = Path.home() / ".neuros" / "libraries.json"

# ── Library categories ────────────────────────────────────────────
CATEGORIES = [
    "All",
    "Motors & Actuators",
    "Sensors & IMU",
    "Communication",
    "Displays",
    "Navigation & SLAM",
    "Computer Vision",
    "AI / ML",
    "Power Management",
    "Audio",
    "ROS2 Bridge",
    "NEUROS Native",
    "Utilities",
]

@dataclass
class LibraryDef:
    name:          str
    author:        str
    category:      str
    description:   str
    version:       str
    pip_package:   str                   # pip install name (empty = not pip)
    compatible_families: list       # board families: Arduino, ESP, Raspberry Pi, etc.
    compatible_boards:   list = field(default_factory=list)       # specific boards (empty = all in family)
    min_tier:      str = TIER_BASIC
    homepage:      str = ""
    example:       str = ""
    tags:          list = field(default_factory=list)
    installed:     bool = False
    installed_ver: str  = ""

    def is_compatible_with(self, board_family: str, board_name: str = "") -> bool:
        """Check if this library works with the given board."""
        fam_ok = any(
            f.lower() in board_family.lower() or board_family.lower() in f.lower()
            for f in self.compatible_families
        ) or "all" in [f.lower() for f in self.compatible_families]

        if not fam_ok:
            return False

        if self.compatible_boards and board_name:
            return any(b.lower() in board_name.lower() for b in self.compatible_boards)

        return True

    def to_dict(self) -> dict:
        return asdict(self)


# ── Full library registry ─────────────────────────────────────────
LIBRARY_REGISTRY: list[LibraryDef] = [

    # ── MOTORS & ACTUATORS ────────────────────────────────────────
    LibraryDef(
        name="pyserial", author="Chris Liechti",
        category="Communication",
        description="Serial port communication for Python. Core NEUROS dependency for all USB-connected boards.",
        version="3.5", pip_package="pyserial",
        compatible_families=["All"],
        min_tier=TIER_BASIC,
        example="import serial\nser = serial.Serial('/dev/ttyUSB0', 115200)\nser.write(b'Hello')",
        tags=["serial","uart","usb"],
    ),
    LibraryDef(
        name="NEUROS Motor Node", author="NEUROS Team",
        category="NEUROS Native",
        description="High-level motor control node for Neural Bus. PID + encoder feedback + fault detection. Works on any board with PWM.",
        version="0.2.1", pip_package="neuros-motor",
        compatible_families=["Arduino","ESP","Raspberry Pi","Teensy","STM32"],
        min_tier=TIER_BASIC,
        example="from neuros import MotorNode\nm = MotorNode(pwm_pin=9, dir_pin=8)\nm.set_speed(0.75)  # 75%\nm.on_fault(lambda: print('fault!'))",
        tags=["motor","pwm","pid","actuator"],
    ),
    LibraryDef(
        name="NEUROS Servo Node", author="NEUROS Team",
        category="NEUROS Native",
        description="RC servo control with position, speed, and torque profiles. Auto-calibration.",
        version="0.2.0", pip_package="neuros-servo",
        compatible_families=["Arduino","ESP","Raspberry Pi","Teensy"],
        min_tier=TIER_BASIC,
        example="from neuros import ServoNode\ns = ServoNode(pin=9)\ns.set_angle(90)\ns.sweep(0, 180, speed=0.5)",
        tags=["servo","rc","position"],
    ),
    LibraryDef(
        name="RPi.GPIO", author="Ben Croston",
        category="Motors & Actuators",
        description="Python GPIO library for Raspberry Pi. Control pins, read sensors, software PWM.",
        version="0.7.1", pip_package="RPi.GPIO",
        compatible_families=["Raspberry Pi"],
        compatible_boards=["Raspberry Pi 3B+","Raspberry Pi 4B","Raspberry Pi 5","Raspberry Pi Zero W"],
        min_tier=TIER_INTER,
        example="import RPi.GPIO as GPIO\nGPIO.setmode(GPIO.BCM)\nGPIO.setup(18, GPIO.OUT)\nGPIO.output(18, GPIO.HIGH)",
        tags=["gpio","pi","digital","pwm"],
    ),
    LibraryDef(
        name="gpiozero", author="Ben Nuttall",
        category="Motors & Actuators",
        description="Higher-level GPIO library for Raspberry Pi. LED, Button, Motor, Buzzer objects.",
        version="2.0.1", pip_package="gpiozero",
        compatible_families=["Raspberry Pi"],
        min_tier=TIER_INTER,
        example="from gpiozero import LED, Button\nled = LED(17)\nbtn = Button(2)\nbtn.when_pressed = led.on\nbtn.when_released = led.off",
        tags=["gpio","pi","led","button","motor"],
    ),
    LibraryDef(
        name="pigpio", author="joan2937",
        category="Motors & Actuators",
        description="Hardware PWM + precise timing on Raspberry Pi. Essential for servos and stepper motors.",
        version="1.78", pip_package="pigpio",
        compatible_families=["Raspberry Pi"],
        min_tier=TIER_INTER,
        example="import pigpio\npi = pigpio.pi()\npi.set_servo_pulsewidth(18, 1500)  # center",
        tags=["pwm","servo","hardware","stepper"],
    ),
    LibraryDef(
        name="adafruit-circuitpython-motor", author="Adafruit",
        category="Motors & Actuators",
        description="DC + stepper motor control. Works with Adafruit Motor HATs and FeatherWings.",
        version="3.4.8", pip_package="adafruit-circuitpython-motor",
        compatible_families=["Raspberry Pi","Adafruit"],
        min_tier=TIER_INTER,
        example="import board\nfrom adafruit_motor import motor\ndc = motor.DCMotor(pwm_a, pwm_b)\ndc.throttle = 0.8",
        tags=["motor","stepper","dc","adafruit"],
    ),

    # ── SENSORS & IMU ─────────────────────────────────────────────
    LibraryDef(
        name="smbus2", author="Karl-Petter Lindegaard",
        category="Sensors & IMU",
        description="I²C/SMBus library for Python. Read any I²C sensor directly from Raspberry Pi or Jetson.",
        version="0.4.3", pip_package="smbus2",
        compatible_families=["Raspberry Pi","Jetson","BeagleBone"],
        min_tier=TIER_INTER,
        example="from smbus2 import SMBus\nbus = SMBus(1)\nbyte = bus.read_byte_data(0x68, 0x75)  # MPU6050 WHO_AM_I",
        tags=["i2c","sensor","smbus"],
    ),
    LibraryDef(
        name="mpu6050-raspberrypi", author="m-rtijn",
        category="Sensors & IMU",
        description="MPU-6050 6-axis IMU — 3-axis gyroscope + 3-axis accelerometer for Pi.",
        version="1.1.0", pip_package="mpu6050-raspberrypi",
        compatible_families=["Raspberry Pi","Jetson"],
        min_tier=TIER_INTER,
        example="from mpu6050 import mpu6050\nsensor = mpu6050(0x68)\naccel = sensor.get_accel_data()\ngyro  = sensor.get_gyro_data()",
        tags=["imu","accelerometer","gyroscope","mpu6050"],
    ),
    LibraryDef(
        name="adafruit-circuitpython-bno055", author="Adafruit",
        category="Sensors & IMU",
        description="BNO055 9-DOF absolute orientation IMU. Fused quaternion + Euler angles.",
        version="5.4.5", pip_package="adafruit-circuitpython-bno055",
        compatible_families=["Raspberry Pi","Adafruit","ESP"],
        min_tier=TIER_BASIC,
        example="import board, busio\nfrom adafruit_bno055 import BNO055_I2C\ni2c = busio.I2C(board.SCL, board.SDA)\nsensor = BNO055_I2C(i2c)\nprint(sensor.euler)",
        tags=["imu","bno055","orientation","fusion"],
    ),
    LibraryDef(
        name="adafruit-circuitpython-bme280", author="Adafruit",
        category="Sensors & IMU",
        description="BME280 temperature, humidity, and pressure sensor.",
        version="2.6.4", pip_package="adafruit-circuitpython-bme280",
        compatible_families=["Raspberry Pi","Adafruit","ESP","Arduino"],
        min_tier=TIER_BASIC,
        example="import board\nfrom adafruit_bme280 import basic as adafruit_bme280\ni2c = board.I2C()\nbme = adafruit_bme280.Adafruit_BME280_I2C(i2c)\nprint(bme.temperature, bme.humidity)",
        tags=["bme280","temperature","humidity","pressure","weather"],
    ),
    LibraryDef(
        name="adafruit-circuitpython-vl53l0x", author="Adafruit",
        category="Sensors & IMU",
        description="VL53L0X time-of-flight distance sensor. 2cm–2m range, accurate to ±3%.",
        version="3.6.9", pip_package="adafruit-circuitpython-vl53l0x",
        compatible_families=["Raspberry Pi","Adafruit","ESP"],
        min_tier=TIER_BASIC,
        example="import board\nfrom adafruit_vl53l0x import VL53L0X\nvl = VL53L0X(board.I2C())\nprint(vl.range, 'mm')",
        tags=["tof","distance","lidar","obstacle"],
    ),
    LibraryDef(
        name="adafruit-circuitpython-lsm9ds1", author="Adafruit",
        category="Sensors & IMU",
        description="LSM9DS1 9-DOF IMU — accel + gyro + magnetometer in one chip.",
        version="2.0.4", pip_package="adafruit-circuitpython-lsm9ds1",
        compatible_families=["Raspberry Pi","Adafruit"],
        min_tier=TIER_INTER,
        example="import board, busio\nfrom adafruit_lsm9ds1 import LSM9DS1_I2C\ni2c = busio.I2C(board.SCL, board.SDA)\nsensor = LSM9DS1_I2C(i2c)\nprint(sensor.acceleration)",
        tags=["imu","9dof","accelerometer","magnetometer"],
    ),
    LibraryDef(
        name="pylidar2", author="Slamtec",
        category="Sensors & IMU",
        description="RPLIDAR A1/A2/A3 Python driver. 2D point cloud scanning for SLAM.",
        version="0.1.3", pip_package="pylidar2",
        compatible_families=["Raspberry Pi","Jetson"],
        min_tier=TIER_INTER,
        example="from pylidar2 import PyRPlidar\nlidar = PyRPlidar(port='/dev/ttyUSB0')\nlidar.connect()\nfor scan in lidar.start_scan():\n    print(scan.angle, scan.distance)",
        tags=["lidar","slam","rplidar","2d","scan"],
    ),

    # ── COMMUNICATION ─────────────────────────────────────────────
    LibraryDef(
        name="bleak", author="Henrik Blidh",
        category="Communication",
        description="Cross-platform Bluetooth Low Energy (BLE) library for Python.",
        version="0.21.1", pip_package="bleak",
        compatible_families=["Raspberry Pi","Jetson","All"],
        min_tier=TIER_INTER,
        example="import asyncio\nfrom bleak import BleakScanner\nasync def main():\n    devices = await BleakScanner.discover()\n    for d in devices: print(d)\nasyncio.run(main())",
        tags=["bluetooth","ble","wireless","communication"],
    ),
    LibraryDef(
        name="paho-mqtt", author="Eclipse Foundation",
        category="Communication",
        description="MQTT client for Python. Publish/subscribe messaging for robot fleets.",
        version="1.6.1", pip_package="paho-mqtt",
        compatible_families=["Raspberry Pi","Jetson","ESP","All"],
        min_tier=TIER_INTER,
        example="import paho.mqtt.client as mqtt\nclient = mqtt.Client()\nclient.connect('broker.local')\nclient.publish('neuros/sensor', '42')",
        tags=["mqtt","iot","fleet","messaging","pub-sub"],
    ),
    LibraryDef(
        name="pyzmq", author="PyZMQ Authors",
        category="Communication",
        description="ZeroMQ for Python. High-speed inter-process messaging. Core NEUROS Neural Bus transport.",
        version="25.1.2", pip_package="pyzmq",
        compatible_families=["Raspberry Pi","Jetson","All"],
        min_tier=TIER_INTER,
        example="import zmq\nctx = zmq.Context()\nsock = ctx.socket(zmq.PUB)\nsock.bind('tcp://*:5555')\nsock.send_string('neuros/cmd drive forward')",
        tags=["zmq","zeromq","ipc","neural-bus","messaging"],
    ),
    LibraryDef(
        name="websockets", author="Aymeric Augustin",
        category="Communication",
        description="WebSocket server/client. Used by NEUROS web UI to talk to robot in real time.",
        version="12.0", pip_package="websockets",
        compatible_families=["Raspberry Pi","Jetson","All"],
        min_tier=TIER_INTER,
        example="import asyncio, websockets\nasync def handler(ws):\n    async for msg in ws:\n        await ws.send(f'echo: {msg}')\nasyncio.run(websockets.serve(handler, '0.0.0.0', 8765))",
        tags=["websocket","web","realtime","ui"],
    ),
    LibraryDef(
        name="pymodbus", author="Riptide Systems",
        category="Communication",
        description="Full Modbus RTU/TCP implementation. Connect industrial PLCs and sensors.",
        version="3.6.3", pip_package="pymodbus",
        compatible_families=["Raspberry Pi","Jetson","All"],
        min_tier=TIER_EXPERT,
        example="from pymodbus.client import ModbusSerialClient\nclient = ModbusSerialClient('COM3', baudrate=9600)\nclient.connect()\nresult = client.read_holding_registers(address=1, count=10)",
        tags=["modbus","industrial","plc","rtu","tcp"],
    ),
    LibraryDef(
        name="python-can", author="Harri Kiiskinen",
        category="Communication",
        description="CAN bus interface for Python. Control industrial robots, automotive ECUs.",
        version="4.3.1", pip_package="python-can",
        compatible_families=["Raspberry Pi","Jetson","BeagleBone"],
        min_tier=TIER_EXPERT,
        example="import can\nbus = can.Bus(interface='socketcan', channel='can0', bitrate=500000)\nmsg = can.Message(arbitration_id=0x123, data=[0,1,2,3])\nbus.send(msg)",
        tags=["can","canbus","industrial","automotive"],
    ),

    # ── DISPLAYS ──────────────────────────────────────────────────
    LibraryDef(
        name="adafruit-circuitpython-ssd1306", author="Adafruit",
        category="Displays",
        description="SSD1306 OLED display (128x64 / 128x32). Draw text, shapes, and images.",
        version="2.12.14", pip_package="adafruit-circuitpython-ssd1306",
        compatible_families=["Raspberry Pi","Adafruit","ESP"],
        min_tier=TIER_BASIC,
        example="import board\nfrom adafruit_ssd1306 import SSD1306_I2C\ndisplay = SSD1306_I2C(128, 64, board.I2C())\ndisplay.fill(0)\ndisplay.text('NEUROS', 0, 0, 1)\ndisplay.show()",
        tags=["oled","display","ssd1306","i2c"],
    ),
    LibraryDef(
        name="luma.oled", author="Richard Hull",
        category="Displays",
        description="OLED driver for Pi. Supports SSD1306, SH1106, SSD1331. Draws PIL images.",
        version="3.13.0", pip_package="luma.oled",
        compatible_families=["Raspberry Pi","Jetson"],
        min_tier=TIER_INTER,
        example="from luma.core.interface.serial import i2c\nfrom luma.oled.device import ssd1306\nfrom luma.core.render import canvas\nserial = i2c(port=1, address=0x3C)\ndevice = ssd1306(serial)\nwith canvas(device) as draw:\n    draw.text((10,10), 'NEUROS', fill='white')",
        tags=["oled","display","pi","pil","image"],
    ),

    # ── NAVIGATION & SLAM ─────────────────────────────────────────
    LibraryDef(
        name="nav2-msgs", author="ROS2 Nav2 Team",
        category="Navigation & SLAM",
        description="ROS2 Nav2 message types. Required for NEUROS ROS2 navigation bridge.",
        version="1.3.0", pip_package="nav2-msgs",
        compatible_families=["Raspberry Pi","Jetson"],
        min_tier=TIER_ADVANCED,
        example="from nav2_msgs.action import NavigateToPose\nfrom geometry_msgs.msg import PoseStamped",
        tags=["ros2","nav2","navigation","slam"],
    ),
    LibraryDef(
        name="NEUROS Nav Node", author="NEUROS Team",
        category="NEUROS Native",
        description="Pure-Python pathfinding + obstacle avoidance. No ROS2 needed. A*, Dijkstra, DWA.",
        version="0.1.5", pip_package="neuros-nav",
        compatible_families=["Raspberry Pi","Jetson","All"],
        min_tier=TIER_INTER,
        example="from neuros.nav import Navigator\nnav = Navigator(map_file='floor.yaml')\nnav.set_goal(x=2.5, y=1.0)\npath = nav.plan()\nnav.execute(path)",
        tags=["navigation","pathfinding","astar","obstacle"],
    ),

    # ── COMPUTER VISION ───────────────────────────────────────────
    LibraryDef(
        name="opencv-python", author="OpenCV Team",
        category="Computer Vision",
        description="Complete computer vision. Object detection, lane detection, face recognition, optical flow.",
        version="4.8.1.78", pip_package="opencv-python",
        compatible_families=["Raspberry Pi","Jetson","All"],
        min_tier=TIER_INTER,
        example="import cv2\ncap = cv2.VideoCapture(0)\nret, frame = cap.read()\ngray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)\ncv2.imwrite('frame.jpg', gray)",
        tags=["vision","camera","opencv","detection","tracking"],
    ),
    LibraryDef(
        name="ultralytics", author="Ultralytics",
        category="Computer Vision",
        description="YOLOv8 — real-time object detection, segmentation, and pose estimation.",
        version="8.1.27", pip_package="ultralytics",
        compatible_families=["Raspberry Pi","Jetson"],
        compatible_boards=["Raspberry Pi 4B","Raspberry Pi 5","Jetson Nano",
                           "Jetson Xavier NX","Jetson AGX Orin"],
        min_tier=TIER_INTER,
        example="from ultralytics import YOLO\nmodel = YOLO('yolov8n.pt')\nresults = model('robot_view.jpg')\nfor box in results[0].boxes:\n    print(box.cls, box.conf)",
        tags=["yolo","detection","segmentation","pose","realtime"],
    ),
    LibraryDef(
        name="picamera2", author="Raspberry Pi Foundation",
        category="Computer Vision",
        description="Official Python camera library for Raspberry Pi (all models). Replaces picamera.",
        version="0.3.19", pip_package="picamera2",
        compatible_families=["Raspberry Pi"],
        min_tier=TIER_INTER,
        example="from picamera2 import Picamera2\ncam = Picamera2()\ncam.start()\nframe = cam.capture_array()\ncam.stop()",
        tags=["camera","pi","video","stream","capture"],
    ),
    LibraryDef(
        name="pyrealsense2", author="Intel",
        category="Computer Vision",
        description="Intel RealSense depth cameras. RGB-D frames, point clouds, SLAM input.",
        version="2.54.1.5216", pip_package="pyrealsense2",
        compatible_families=["Raspberry Pi","Jetson","All"],
        min_tier=TIER_ADVANCED,
        example="import pyrealsense2 as rs\npipeline = rs.pipeline()\nconfig = rs.config()\nconfig.enable_stream(rs.stream.depth)\npipeline.start(config)",
        tags=["depth","realsense","rgbd","pointcloud","intel"],
    ),

    # ── AI / ML ───────────────────────────────────────────────────
    LibraryDef(
        name="tflite-runtime", author="Google",
        category="AI / ML",
        description="TensorFlow Lite for microcontrollers and edge boards. Run models on-device.",
        version="2.14.0", pip_package="tflite-runtime",
        compatible_families=["Raspberry Pi","Jetson"],
        min_tier=TIER_INTER,
        example="import tflite_runtime.interpreter as tflite\ninterp = tflite.Interpreter('model.tflite')\ninterp.allocate_tensors()\ninterp.invoke()",
        tags=["tflite","ml","inference","edge","quantized"],
    ),
    LibraryDef(
        name="torch", author="Meta AI (PyTorch)",
        category="AI / ML",
        description="PyTorch deep learning. Full model training + inference. CUDA on Jetson.",
        version="2.2.0", pip_package="torch",
        compatible_families=["Jetson","All"],
        compatible_boards=["Jetson Nano","Jetson Xavier NX","Jetson AGX Orin"],
        min_tier=TIER_ADVANCED,
        example="import torch\nmodel = torch.load('robot_policy.pt')\nobs = torch.tensor(state)\naction = model(obs)",
        tags=["pytorch","deep-learning","gpu","cuda","rl"],
    ),
    LibraryDef(
        name="stable-baselines3", author="DLR-RM",
        category="AI / ML",
        description="Reinforcement learning algorithms: PPO, SAC, DQN, TD3. Train robot policies.",
        version="2.2.1", pip_package="stable-baselines3",
        compatible_families=["Raspberry Pi","Jetson","All"],
        min_tier=TIER_ADVANCED,
        example="from stable_baselines3 import PPO\nmodel = PPO('MlpPolicy', env)\nmodel.learn(total_timesteps=10_000)\nmodel.save('neuros_policy')",
        tags=["rl","reinforcement","ppo","sac","dqn","training"],
    ),
    LibraryDef(
        name="openai", author="OpenAI",
        category="AI / ML",
        description="OpenAI Python client. LLM-driven robot control via GPT-4o and vision models.",
        version="1.12.0", pip_package="openai",
        compatible_families=["Raspberry Pi","Jetson","All"],
        min_tier=TIER_INTER,
        example="from openai import OpenAI\nclient = OpenAI()\nresp = client.chat.completions.create(\n    model='gpt-4o',\n    messages=[{'role':'user','content':'navigate to the chair'}]\n)\nprint(resp.choices[0].message.content)",
        tags=["llm","gpt","vision","nlp","language"],
    ),
    LibraryDef(
        name="anthropic", author="Anthropic",
        category="AI / ML",
        description="Anthropic Python SDK. Use Claude for plain-English robot control and reasoning.",
        version="0.20.0", pip_package="anthropic",
        compatible_families=["All"],
        min_tier=TIER_INTER,
        example="import anthropic\nclient = anthropic.Anthropic()\nmsg = client.messages.create(\n    model='claude-sonnet-4-5',\n    max_tokens=256,\n    messages=[{'role':'user','content':'pick up the red block'}]\n)",
        tags=["claude","llm","anthropic","nlp","language"],
    ),

    # ── ROS2 BRIDGE ───────────────────────────────────────────────
    LibraryDef(
        name="rclpy", author="ROS2 Team",
        category="ROS2 Bridge",
        description="ROS2 Python client library. Required for NEUROS↔ROS2 bridge layer.",
        version="5.3.3", pip_package="rclpy",
        compatible_families=["Raspberry Pi","Jetson"],
        min_tier=TIER_ADVANCED,
        example="import rclpy\nfrom rclpy.node import Node\nrclpy.init()\nnode = Node('neuros_bridge')\nrclpy.spin(node)",
        tags=["ros2","rclpy","bridge","dds","topics"],
    ),
    LibraryDef(
        name="NEUROS ROS2 Bridge", author="NEUROS Team",
        category="ROS2 Bridge",
        description="Zero-config bridge between NEUROS Neural Bus and ROS2 DDS. Wrap existing nodes instantly.",
        version="0.3.0", pip_package="neuros-ros2",
        compatible_families=["Raspberry Pi","Jetson"],
        min_tier=TIER_ADVANCED,
        example="from neuros.bridge.ros2 import ROS2Bridge\nbr = ROS2Bridge()\nbr.map_topic('/cmd_vel', 'neuros/drive')\nbr.map_topic('/scan',    'neuros/lidar')\nbr.start()",
        tags=["ros2","bridge","migration","dds","wrap"],
    ),

    # ── POWER MANAGEMENT ──────────────────────────────────────────
    LibraryDef(
        name="adafruit-circuitpython-ina219", author="Adafruit",
        category="Power Management",
        description="INA219 current/voltage/power monitor. Track battery health and motor draw.",
        version="3.4.24", pip_package="adafruit-circuitpython-ina219",
        compatible_families=["Raspberry Pi","Adafruit","ESP"],
        min_tier=TIER_BASIC,
        example="import board\nfrom adafruit_ina219 import INA219\nina = INA219(board.I2C())\nprint(ina.bus_voltage, 'V')\nprint(ina.current, 'mA')",
        tags=["power","current","battery","ina219","monitor"],
    ),

    # ── UTILITIES ─────────────────────────────────────────────────
    LibraryDef(
        name="rich", author="Will McGuire",
        category="Utilities",
        description="Beautiful terminal output. Used throughout NEUROS CLI for logs and dashboards.",
        version="13.7.0", pip_package="rich",
        compatible_families=["All"],
        min_tier=TIER_BASIC,
        example="from rich.console import Console\nfrom rich.table import Table\nconsole = Console()\nconsole.print('[bold cyan]NEUROS[/bold cyan] booting...')",
        tags=["cli","terminal","logging","ui","dashboard"],
    ),
    LibraryDef(
        name="click", author="Pallets Projects",
        category="Utilities",
        description="CLI framework used by NEUROS CLI. Subcommands, options, argument parsing.",
        version="8.1.7", pip_package="click",
        compatible_families=["All"],
        min_tier=TIER_BASIC,
        example="import click\n@click.command()\n@click.option('--port', default='/dev/ttyUSB0')\ndef run(port):\n    click.echo(f'Connecting: {port}')",
        tags=["cli","commands","argument","options"],
    ),
    LibraryDef(
        name="numpy", author="NumPy Developers",
        category="Utilities",
        description="Numerical computing for Python. Required by almost every AI/robotics library.",
        version="1.26.4", pip_package="numpy",
        compatible_families=["All"],
        min_tier=TIER_BASIC,
        example="import numpy as np\npose = np.array([x, y, theta])\nrotation = np.array([[cos,-sin],[sin,cos]])",
        tags=["math","array","matrix","compute","numpy"],
    ),
    LibraryDef(
        name="scipy", author="SciPy Developers",
        category="Utilities",
        description="Scientific computing. Signal processing, Kalman filters, optimization for robotics.",
        version="1.12.0", pip_package="scipy",
        compatible_families=["All"],
        min_tier=TIER_INTER,
        example="from scipy.signal import butter, filtfilt\nb, a = butter(3, 0.05)\nfiltered = filtfilt(b, a, sensor_data)",
        tags=["kalman","filter","signal","optimization","scipy"],
    ),
]


# ── Library Manager class ────────────────────────────────────────

class LibraryManager:
    """
    Manages the NEUROS library ecosystem.
    Handles install/uninstall, compatibility filtering, and persistence.
    """

    def __init__(self, registry_path: Path = LIB_REGISTRY_PATH):
        self.registry_path = registry_path
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._installed: dict[str, str] = {}   # name → installed version
        self._load_installed()
        self._sync_installed_flags()

    # ── Persistence ─────────────────────────────────────────────

    def _load_installed(self):
        if self.registry_path.exists():
            try:
                self._installed = json.loads(self.registry_path.read_text())
            except Exception:
                self._installed = {}

    def _save_installed(self):
        self.registry_path.write_text(json.dumps(self._installed, indent=2))

    def _sync_installed_flags(self):
        for lib in LIBRARY_REGISTRY:
            lib.installed     = lib.name in self._installed
            lib.installed_ver = self._installed.get(lib.name, "")

    # ── Query ────────────────────────────────────────────────────

    def all_libs(self) -> list[LibraryDef]:
        return LIBRARY_REGISTRY

    def by_category(self, category: str) -> list[LibraryDef]:
        if category == "All":
            return LIBRARY_REGISTRY
        return [l for l in LIBRARY_REGISTRY if l.category == category]

    def installed_libs(self) -> list[LibraryDef]:
        return [l for l in LIBRARY_REGISTRY if l.installed]

    def search(self, query: str) -> list[LibraryDef]:
        q = query.lower()
        return [l for l in LIBRARY_REGISTRY
                if q in l.name.lower()
                or q in l.description.lower()
                or any(q in t for t in l.tags)]

    def compatible_with_hardware(self, hw_list: list) -> list[LibraryDef]:
        """Filter libraries that work with any device in hw_list."""
        result = []
        for lib in LIBRARY_REGISTRY:
            for hw in hw_list:
                family = getattr(hw, 'chip', '') or ''
                name   = getattr(hw, 'name', '') or ''
                # infer family from name
                if 'Arduino'  in name: family = 'Arduino'
                elif 'ESP'    in name: family = 'ESP'
                elif 'Pi'     in name: family = 'Raspberry Pi'
                elif 'Jetson' in name: family = 'Jetson'
                elif 'STM32'  in name: family = 'STM32'
                elif 'Teensy' in name: family = 'Teensy'
                elif 'Adafruit' in name: family = 'Adafruit'
                if lib.is_compatible_with(family, name):
                    result.append(lib)
                    break
        return result

    # ── Install / Uninstall ──────────────────────────────────────

    def install(self, lib_name: str, console=None) -> bool:
        """pip install the library. Returns True on success."""
        lib = self._get(lib_name)
        if not lib:
            return False
        if not lib.pip_package:
            if console:
                console.print(f"[yellow]'{lib_name}' is not pip-installable.[/yellow]")
            return False

        cmd = [sys.executable, "-m", "pip", "install",
               f"{lib.pip_package}=={lib.version}", "--break-system-packages", "-q"]

        if console:
            console.print(f"[dim]→ pip install {lib.pip_package}=={lib.version}[/dim]")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                self._installed[lib_name] = lib.version
                self._save_installed()
                self._sync_installed_flags()
                return True
            else:
                if console:
                    console.print(f"[red]pip error:[/red] {result.stderr[:200]}")
                return False
        except subprocess.TimeoutExpired:
            if console:
                console.print("[red]Install timed out.[/red]")
            return False

    def uninstall(self, lib_name: str, console=None) -> bool:
        lib = self._get(lib_name)
        if not lib or not lib.pip_package:
            return False
        cmd = [sys.executable, "-m", "pip", "uninstall", lib.pip_package, "-y",
               "--break-system-packages"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                self._installed.pop(lib_name, None)
                self._save_installed()
                self._sync_installed_flags()
                return True
        except Exception:
            pass
        return False

    def mark_installed(self, lib_name: str, version: str = ""):
        """Mark a library as installed without pip (e.g. manually or system-installed)."""
        lib = self._get(lib_name)
        if lib:
            version = version or lib.version
            self._installed[lib_name] = version
            self._save_installed()
            self._sync_installed_flags()

    def _get(self, name: str) -> Optional[LibraryDef]:
        return next((l for l in LIBRARY_REGISTRY if l.name == name), None)

    def get(self, name: str) -> Optional[LibraryDef]:
        return self._get(name)
