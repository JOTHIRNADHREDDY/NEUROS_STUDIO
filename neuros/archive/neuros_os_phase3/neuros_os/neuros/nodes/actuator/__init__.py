"""
neuros.nodes.actuator
=====================
Standard actuator nodes for Phase 1 (Domain A).

Included nodes
--------------
  MotorNode       DC motor via L298N / L293D H-bridge (PWM + direction)
  ServoNode       Hobby servo (PWM 50 Hz, 1–2ms pulse width)
  LEDNode         Single LED or RGB LED with brightness control
  BuzzerNode      Active/passive buzzer with tone generation
"""
from neuros.nodes.actuator.motor  import MotorNode
from neuros.nodes.actuator.servo  import ServoNode
from neuros.nodes.actuator.led    import LEDNode
from neuros.nodes.actuator.buzzer import BuzzerNode

__all__ = ["MotorNode", "ServoNode", "LEDNode", "BuzzerNode"]
