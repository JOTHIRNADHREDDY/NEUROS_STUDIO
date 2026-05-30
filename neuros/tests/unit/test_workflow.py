"""Unit tests for the Workflow Engine."""

import unittest
from neuros.workflow.triggers import BatteryLowTrigger, ObjectDetectedTrigger
from neuros.workflow.conditions import RobotOnline

class TestWorkflowEngine(unittest.TestCase):
    
    def test_battery_low_trigger(self):
        trigger = BatteryLowTrigger(threshold=20.0)
        self.assertTrue(trigger.evaluate("TELEMETRY", {"battery": 15.0}))
        self.assertFalse(trigger.evaluate("TELEMETRY", {"battery": 25.0}))
        self.assertFalse(trigger.evaluate("VISION", {"battery": 15.0}))
        
    def test_object_detected_trigger(self):
        trigger = ObjectDetectedTrigger(object_class="person")
        self.assertTrue(trigger.evaluate("VISION", {"detected_objects": ["person", "chair"]}))
        self.assertFalse(trigger.evaluate("VISION", {"detected_objects": ["chair", "desk"]}))
        
    def test_robot_online_condition(self):
        condition = RobotOnline()
        self.assertTrue(condition.evaluate({"robot_status": "online"}))
        self.assertFalse(condition.evaluate({"robot_status": "offline"}))

if __name__ == '__main__':
    unittest.main()
