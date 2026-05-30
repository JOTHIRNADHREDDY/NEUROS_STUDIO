"""
neuros.nodes.sensor
===================
Standard sensor nodes for Phase 1 (Domain A).

All sensor nodes follow the same pattern:
  1. configure()  — register pins / addresses
  2. tick()       — read hardware, publish to Neural Bus
  3. destroy()    — release hardware

Included nodes
--------------
  GPIOSensorNode      digital/analog input (button, proximity, etc.)
  IMUNode             6-DOF inertial measurement (I2C, e.g. MPU6050)
  UltrasonicNode      HC-SR04 time-of-flight distance sensor
  LineFollowerNode    IR reflectance array for line following
  TemperatureNode     DS18B20 or NTC thermistor
  EncoderNode         quadrature encoder for odometry
  BatteryMonitorNode  voltage divider → battery state-of-charge
"""

from neuros.nodes.sensor.gpio_sensor    import GPIOSensorNode
from neuros.nodes.sensor.imu            import IMUNode
from neuros.nodes.sensor.ultrasonic     import UltrasonicNode
from neuros.nodes.sensor.line_follower  import LineFollowerNode
from neuros.nodes.sensor.temperature    import TemperatureNode
from neuros.nodes.sensor.encoder        import EncoderNode
from neuros.nodes.sensor.battery        import BatteryMonitorNode

__all__ = [
    "GPIOSensorNode",
    "IMUNode",
    "UltrasonicNode",
    "LineFollowerNode",
    "TemperatureNode",
    "EncoderNode",
    "BatteryMonitorNode",
]
