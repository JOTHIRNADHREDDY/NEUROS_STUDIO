"""Integration tests for the core Orchestrator -> Safety loop."""

import unittest
from neuros.core.orchestrator.agent import Orchestrator
from neuros.core.tool_registry.registry import ToolRegistry
from neuros.safety.validator.validator import SafetyValidator
from neuros.tests.mocks.esp32 import MockESP32

class TestIntegration(unittest.TestCase):
    
    def setUp(self):
        self.tool_registry = ToolRegistry()
        self.safety_validator = SafetyValidator()
        self.orchestrator = Orchestrator(self.tool_registry)
        self.robot = MockESP32(robot_id="test_robot_01")
        self.robot.connect()
        
    def test_mission_execution(self):
        # A mocked intent parsing
        result = self.orchestrator.execute_mission("move forward 5 meters", self.robot.robot_id)
        self.assertEqual(result["status"], "success")
        
        # Test basic mock robot functionality
        self.assertTrue(self.robot.is_connected())
        move_res = self.robot.execute("move", distance=5)
        self.assertEqual(move_res["action"], "move")
        
    def test_safety_validator_interception(self):
        # Simulate orchestrator deciding to move very fast
        # The safety validator should catch it
        passed = self.safety_validator.validate_action("move", {"speed": 6.0})
        self.assertFalse(passed)  # Max speed is 5.0
        
        passed = self.safety_validator.validate_action("move", {"speed": 2.0})
        self.assertTrue(passed)

if __name__ == '__main__':
    unittest.main()
