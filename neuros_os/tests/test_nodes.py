"""
tests/test_nodes.py
===================
Node-level tests for all Phase 1 sensor and actuator nodes.
Uses SimulatorHAL throughout — no hardware needed.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from neuros import Robot, NeuralBus
from neuros.hal.drivers.simulator import SimulatorHAL
from neuros.hal.base import PinState, PinMode
from neuros.nodes.sensor.gpio_sensor   import GPIOSensorNode
from neuros.nodes.sensor.imu           import IMUNode
from neuros.nodes.sensor.ultrasonic    import UltrasonicNode
from neuros.nodes.sensor.line_follower import LineFollowerNode
from neuros.nodes.sensor.temperature   import TemperatureNode
from neuros.nodes.sensor.encoder       import EncoderNode
from neuros.nodes.sensor.battery       import BatteryMonitorNode
from neuros.nodes.actuator.motor  import MotorNode
from neuros.nodes.actuator.servo  import ServoNode
from neuros.nodes.actuator.led    import LEDNode
from neuros.nodes.actuator.buzzer import BuzzerNode
from neuros.safety import SafetySupervisor, FaultCode


# ── Helpers ──────────────────────────────────────────────────────────────────
def make_env():
    hal = SimulatorHAL(seed=0)
    hal.connect()
    bus = NeuralBus()
    return hal, bus

def wire(node, hal, bus):
    node._hal = hal
    node._bus = bus
    node._configure()
    node._activate()
    return node


# ══ SENSOR NODES ════════════════════════════════════════════════════════════

class TestGPIOSensor:
    def test_reads_digital_high(self):
        hal, bus = make_env()
        hal.inject_pin_read(4, PinState.HIGH)
        node = wire(GPIOSensorNode("btn", board_pin=4, mode="input", hz=50), hal, bus)
        received = []
        bus.subscribe("/robot/sensor/btn", received.append)
        node._tick()
        assert len(received) == 1
        assert received[0].data["value"] == PinState.HIGH.value

    def test_threshold_debounce(self):
        hal, bus = make_env()
        hal.inject_pin_read(5, 0.50)
        node = wire(GPIOSensorNode("pot", board_pin=5, mode="analog_in",
                                   hz=50, threshold=0.1), hal, bus)
        received = []
        bus.subscribe("/robot/sensor/pot", received.append)
        node._tick()   # first tick always publishes
        hal.inject_pin_read(5, 0.52)   # delta < threshold → suppress
        node._tick()
        assert len(received) == 1      # no second publish

    def test_last_value_accessible(self):
        hal, bus = make_env()
        hal.inject_pin_read(6, PinState.LOW)
        node = wire(GPIOSensorNode("sw", board_pin=6, mode="input", hz=10), hal, bus)
        node._tick()
        assert node.last_value is not None


class TestIMU:
    def test_publishes_accel(self):
        hal, bus = make_env()
        node = wire(IMUNode("imu", hz=100), hal, bus)
        received = []
        bus.subscribe("/robot/sensor/imu/accel", received.append)
        node._tick()
        assert len(received) == 1
        d = received[0].data
        assert "ax" in d and "ay" in d and "az" in d

    def test_publishes_orientation(self):
        hal, bus = make_env()
        node = wire(IMUNode("imu", hz=100, complementary=True), hal, bus)
        received = []
        bus.subscribe("/robot/sensor/imu/orientation", received.append)
        for _ in range(5):
            node._tick()
        assert len(received) == 5
        assert "roll" in received[0].data
        assert "pitch" in received[0].data

    def test_inject_accel(self):
        hal, bus = make_env()
        hal.inject_sensor("imu_ax", 1.5)
        hal.inject_sensor("imu_ay", 0.0)
        hal.inject_sensor("imu_az", 9.81)
        node = wire(IMUNode("imu", hz=100, complementary=False), hal, bus)
        received = []
        bus.subscribe("/robot/sensor/imu/accel", received.append)
        node._tick()
        assert abs(received[0].data["ax"] - 1.5) < 0.01


class TestUltrasonic:
    def test_publishes_distance(self):
        hal, bus = make_env()
        hal.inject_sensor("front_sonar_distance_cm", 45.0)
        node = wire(UltrasonicNode("front_sonar", trig_pin=4, echo_pin=5, hz=10), hal, bus)
        received = []
        bus.subscribe("/robot/sensor/ultrasonic/front_sonar", received.append)
        node._tick()
        assert len(received) == 1
        assert received[0].data["distance_cm"] == 45.0
        assert received[0].data["valid"] is True

    def test_invalid_when_out_of_range(self):
        hal, bus = make_env()
        hal.inject_sensor("sonar_distance_cm", 500.0)  # > 400 cm max
        node = wire(UltrasonicNode("sonar", trig_pin=4, echo_pin=5, hz=10, max_retries=1), hal, bus)
        received = []
        bus.subscribe("/robot/sensor/ultrasonic/sonar", received.append)
        node._tick()
        assert received[0].data["valid"] is False


class TestLineFollower:
    def test_centre_line_zero_error(self):
        hal, bus = make_env()
        # Centre sensor (index 2 of 5) sees line, others see white
        for i, p in enumerate([14, 15, 16, 17, 18]):
            # Centre pin sees BLACK (high voltage = line in analog mode)
            hal.inject_pin_read(p, 0.9 if i == 2 else 0.05)
        node = wire(LineFollowerNode("line", pins=[14,15,16,17,18],
                                    analog=True, invert=False, hz=100), hal, bus)
        for _ in range(3):
            node._tick()
        assert node.detected is True
        assert abs(node.error) < 0.1   # near centre

    def test_all_white_not_detected(self):
        hal, bus = make_env()
        for p in [14,15,16,17,18]:
            hal.inject_pin_read(p, 0.0)   # all white
        node = wire(LineFollowerNode("line", pins=[14,15,16,17,18],
                                    analog=True, invert=False, hz=100), hal, bus)
        node._tick()
        assert node.detected is False


class TestTemperature:
    def test_simulate_mode(self):
        hal, bus = make_env()
        hal.inject_sensor("env_temp_celsius", 37.5)
        node = wire(TemperatureNode("env_temp", mode="simulate", hz=1), hal, bus)
        received = []
        bus.subscribe("/robot/sensor/temperature/env_temp", received.append)
        node._tick()
        assert abs(received[0].data["celsius"] - 37.5) < 0.1

    def test_fahrenheit_conversion(self):
        hal, bus = make_env()
        hal.inject_sensor("t_celsius", 100.0)
        node = wire(TemperatureNode("t", mode="simulate", hz=1), hal, bus)
        received = []
        bus.subscribe("/robot/sensor/temperature/t", received.append)
        node._tick()
        assert abs(received[0].data["fahrenheit"] - 212.0) < 0.1


class TestEncoder:
    def test_tick_count_increments(self):
        hal, bus = make_env()
        # Simulate rising edges on pin A
        toggle = [0]
        def toggling_a():
            toggle[0] ^= 1
            return toggle[0]
        hal.inject_pin_read(18, toggling_a)
        hal.inject_pin_read(19, lambda: 1)  # always forward
        node = wire(EncoderNode("enc", pin_a=18, pin_b=19,
                                ticks_per_rev=360, hz=500), hal, bus)
        for _ in range(10):
            node._tick()
        # Rising edges detected → ticks > 0
        assert node.ticks > 0

    def test_reset(self):
        hal, bus = make_env()
        hal.inject_pin_read(18, 1)
        hal.inject_pin_read(19, 1)
        node = wire(EncoderNode("enc", pin_a=18, pin_b=19, hz=500), hal, bus)
        node.ticks = 1234
        node.distance_m = 0.5
        node.reset()
        assert node.ticks == 0
        assert node.distance_m == 0.0


class TestBattery:
    def test_ok_status(self):
        hal, bus = make_env()
        # Inject ~4.0V for a 1S LiPo (range 3.0–4.2V)
        # divider_ratio=1.0, vref=5.0 → raw = 4.0/5.0 = 0.80
        hal.inject_pin_read(19, 0.80)
        node = wire(BatteryMonitorNode("bat", pin=19, profile="lipo_1s",
                                       divider_ratio=1.0, adc_vref=5.0), hal, bus)
        received = []
        bus.subscribe("/robot/sensor/battery", received.append)
        node._tick()
        assert received[0].data["status"] == "ok"

    def test_critical_alert_published(self):
        hal, bus = make_env()
        # Inject 2.8V (below 3.0V critical for 1S LiPo)
        hal.inject_pin_read(19, 2.8 / 5.0)
        node = wire(BatteryMonitorNode("bat", pin=19, profile="lipo_1s",
                                       divider_ratio=1.0, adc_vref=5.0,
                                       critical_pct=50), hal, bus)
        alerts = []
        bus.subscribe("/robot/system/battery_alert", alerts.append)
        node._tick()
        assert len(alerts) >= 1
        assert alerts[0].data["status"] in ("low", "critical")


# ══ ACTUATOR NODES ══════════════════════════════════════════════════════════

class TestMotor:
    def test_forward(self):
        hal, bus = make_env()
        node = wire(MotorNode("motor_l", pin_en=5, pin_in1=6, pin_in2=7, hz=100), hal, bus)
        from neuros.bus.message import Message
        bus.publish(Message(topic="/robot/cmd/motor/motor_l", data={"speed": 0.75}))
        node._tick()
        assert node.direction == "forward"
        assert abs(node.speed - 0.75) < 0.01

    def test_backward(self):
        hal, bus = make_env()
        node = wire(MotorNode("motor_l", pin_en=5, pin_in1=6, pin_in2=7, hz=100), hal, bus)
        from neuros.bus.message import Message
        bus.publish(Message(topic="/robot/cmd/motor/motor_l", data={"speed": -0.5}))
        node._tick()
        assert node.direction == "backward"

    def test_stop_command(self):
        hal, bus = make_env()
        node = wire(MotorNode("motor_l", pin_en=5, pin_in1=6, pin_in2=7, hz=100), hal, bus)
        from neuros.bus.message import Message
        bus.publish(Message(topic="/robot/cmd/motor/motor_l", data={"speed": 0.8}))
        node._tick()
        bus.publish(Message(topic="/robot/cmd/stop", data={}))
        node._tick()
        assert node.direction == "stopped"
        assert node.speed == 0.0

    def test_speed_clamped(self):
        hal, bus = make_env()
        node = wire(MotorNode("motor_l", pin_en=5, pin_in1=6, pin_in2=7), hal, bus)
        from neuros.bus.message import Message
        bus.publish(Message(topic="/robot/cmd/motor/motor_l", data={"speed": 5.0}))
        node._tick()
        assert node.speed <= 1.0

    def test_publishes_feedback(self):
        hal, bus = make_env()
        node = wire(MotorNode("motor_r", pin_en=10, pin_in1=11, pin_in2=12, hz=100), hal, bus)
        received = []
        bus.subscribe("/robot/actuator/motor/motor_r", received.append)
        node._tick()
        assert len(received) == 1
        assert "speed" in received[0].data


class TestServo:
    def test_initial_angle(self):
        hal, bus = make_env()
        node = wire(ServoNode("pan", pin=9, angle_init=90.0), hal, bus)
        assert abs(node.angle_deg - 90.0) < 0.1

    def test_command_changes_angle(self):
        hal, bus = make_env()
        node = wire(ServoNode("tilt", pin=10, hz=50), hal, bus)
        from neuros.bus.message import Message
        bus.publish(Message(topic="/robot/cmd/servo/tilt", data={"angle_deg": 45.0}))
        node._tick()
        assert abs(node.angle_deg - 45.0) < 1.0

    def test_angle_clamped_to_range(self):
        hal, bus = make_env()
        node = wire(ServoNode("arm", pin=11, angle_min=30.0, angle_max=150.0, hz=50), hal, bus)
        from neuros.bus.message import Message
        bus.publish(Message(topic="/robot/cmd/servo/arm", data={"angle_deg": 200.0}))
        node._tick()
        assert node.angle_deg <= 150.0

    def test_duty_within_range(self):
        hal, bus = make_env()
        node = wire(ServoNode("s", pin=9, angle_init=0.0), hal, bus)
        node._tick()
        duty = node._angle_to_duty(0.0)
        assert 0.02 <= duty <= 0.03

    def test_publishes_feedback(self):
        hal, bus = make_env()
        node = wire(ServoNode("pan2", pin=9), hal, bus)
        received = []
        bus.subscribe("/robot/actuator/servo/pan2", received.append)
        node._tick()
        assert "angle_deg" in received[0].data


class TestLED:
    def test_digital_on_off(self):
        hal, bus = make_env()
        node = wire(LEDNode("led", pin=13, mode="digital"), hal, bus)
        from neuros.bus.message import Message
        bus.publish(Message(topic="/robot/cmd/led/led", data={"state": "on"}))
        node._tick()
        assert node._state is True
        bus.publish(Message(topic="/robot/cmd/led/led", data={"state": "off"}))
        node._tick()
        assert node._state is False

    def test_toggle(self):
        hal, bus = make_env()
        node = wire(LEDNode("led2", pin=12, mode="digital"), hal, bus)
        from neuros.bus.message import Message
        bus.publish(Message(topic="/robot/cmd/led/led2", data={"state": "off"}))
        node._tick()
        bus.publish(Message(topic="/robot/cmd/led/led2", data={"state": "toggle"}))
        node._tick()
        assert node._state is True

    def test_blink_pattern(self):
        hal, bus = make_env()
        node = wire(LEDNode("led3", pin=11, mode="digital", hz=100), hal, bus)
        from neuros.bus.message import Message
        bus.publish(Message(topic="/robot/cmd/led/led3", data={"pattern": "blink", "hz": 2}))
        for _ in range(10):
            node._tick()
        assert node._pattern == "blink"

    def test_publishes_feedback(self):
        hal, bus = make_env()
        node = wire(LEDNode("led4", pin=10, mode="pwm"), hal, bus)
        received = []
        bus.subscribe("/robot/actuator/led/led4", received.append)
        node._tick()
        assert "state" in received[0].data


class TestBuzzer:
    def test_on_off(self):
        hal, bus = make_env()
        node = wire(BuzzerNode("bz", pin=8, passive=False), hal, bus)
        from neuros.bus.message import Message
        bus.publish(Message(topic="/robot/cmd/buzzer/bz", data={"state": "on"}))
        node._tick()
        assert node._active is True
        bus.publish(Message(topic="/robot/cmd/buzzer/bz", data={"state": "off"}))
        node._tick()
        assert node._active is False

    def test_pattern_beep(self):
        hal, bus = make_env()
        node = wire(BuzzerNode("bz2", pin=8), hal, bus)
        from neuros.bus.message import Message
        bus.publish(Message(topic="/robot/cmd/buzzer/bz2", data={"pattern": "beep"}))
        for _ in range(20):
            node._tick()
        # After sequence completes, pattern resets
        assert node._pattern in ("beep", "none")

    def test_publishes_feedback(self):
        hal, bus = make_env()
        node = wire(BuzzerNode("bz3", pin=8), hal, bus)
        received = []
        bus.subscribe("/robot/actuator/buzzer/bz3", received.append)
        node._tick()
        assert "active" in received[0].data


# ══ SAFETY SUPERVISOR ═══════════════════════════════════════════════════════

class TestSafetySupervisor:
    def test_starts_safe(self):
        hal, bus = make_env()
        node = wire(SafetySupervisor(), hal, bus)
        assert node.is_safe is True

    def test_soft_estop(self):
        hal, bus = make_env()
        node = wire(SafetySupervisor(), hal, bus)
        from neuros.bus.message import Message
        bus.publish(Message(topic="/robot/cmd/estop", data={"reason": "test"}))
        node._tick()
        assert node.is_safe is False

    def test_battery_critical_triggers_estop(self):
        hal, bus = make_env()
        node = wire(SafetySupervisor(battery_crit_v=3.5), hal, bus)
        from neuros.bus.message import Message
        bus.publish(Message(topic="/robot/sensor/battery",
                            data={"voltage_v": 3.0, "soc_pct": 5.0, "status": "critical"}))
        node._tick()
        assert node.is_safe is False

    def test_fault_recorded(self):
        hal, bus = make_env()
        node = wire(SafetySupervisor(), hal, bus)
        node.trigger_estop(FaultCode.SOFT_ESTOP, "unit test")
        assert len(node.faults) == 1
        assert node.faults[0]["code"] == FaultCode.SOFT_ESTOP

    def test_reset_estop(self):
        hal, bus = make_env()
        node = wire(SafetySupervisor(), hal, bus)
        node.trigger_estop(FaultCode.SOFT_ESTOP, "test")
        node.reset_estop()
        assert node.is_safe is True

    def test_publishes_safety_status(self):
        hal, bus = make_env()
        node = wire(SafetySupervisor(), hal, bus)
        received = []
        bus.subscribe("/robot/system/safety_status", received.append)
        node._tick()
        assert len(received) == 1
        assert "estop" in received[0].data


# ══ CONFIG SYSTEM ═══════════════════════════════════════════════════════════

class TestConfig:
    def test_defaults(self):
        from neuros.config import Config
        cfg = Config()
        assert cfg.get("kernel.hz") == 1000
        assert cfg.get("motor.max_speed") == 1.0

    def test_set_and_get(self):
        from neuros.config import Config
        cfg = Config()
        cfg.set("motor.max_speed", 0.75)
        assert cfg.get("motor.max_speed") == 0.75

    def test_watch_fires_on_change(self):
        from neuros.config import Config
        cfg = Config()
        changes = []
        cfg.watch("led.blink_hz", lambda old, new: changes.append((old, new)))
        cfg.set("led.blink_hz", 5.0)
        assert len(changes) == 1
        assert changes[0] == (2.0, 5.0)

    def test_default_fallback(self):
        from neuros.config import Config
        cfg = Config()
        val = cfg.get("nonexistent.key", default="fallback")
        assert val == "fallback"

    def test_singleton(self):
        from neuros.config import get_config
        c1 = get_config()
        c2 = get_config()
        assert c1 is c2
