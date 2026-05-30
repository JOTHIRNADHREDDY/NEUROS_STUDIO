"""End-to-End tests simulating the full User -> AI -> Robot flow."""

import unittest
from neuros.core.capability_registry.registry import CapabilityRegistry
from neuros.devices.manager.manager import RobotManager
from neuros.core.mission_engine.engine import MissionEngine
from neuros.tests.mocks.esp32 import MockESP32

class TestE2EFlow(unittest.TestCase):
    
    def test_end_to_end_discovery_to_execution(self):
        # 1. Discover Robot
        robot = MockESP32(robot_id="esp32_rover_01")
        robot.connect()
        
        manager = RobotManager()
        manager.register_robot(robot.robot_id, "rover")
        self.assertEqual(len(manager.get_dashboard()), 1)
        
        # 2. Register Capabilities
        cap_reg = CapabilityRegistry()
        cap_reg.register(robot.robot_id, ["move", "stop"])
        self.assertTrue(cap_reg.has_capability(robot.robot_id, "move"))
        
        # 3. Generate & Execute Mission
        mission_engine = MissionEngine()
        mission = mission_engine.create_mission("Patrol base", robot.robot_id)
        mission_engine.generate_plan(mission)
        
        self.assertEqual(len(mission.tasks), 2)
        
        # 4. Mock execution
        for task in mission.tasks:
            res = robot.execute(task.tool_name, **task.args)
            self.assertEqual(res["status"], "success")

if __name__ == '__main__':
    unittest.main()
