"""
NEUROS Example 02: Natural Language
=====================================

Demonstrates how to control a NEUROS robot using natural language.
The command is parsed by the Planner Agent into a sequence of skills,
which are then executed.
"""

import asyncio
from neuros import Robot

async def main():
    robot = Robot(name="nlp_rover", board="simulator", robot_type="rover")
    robot.start()
    
    # NLP command that translates to "navigate_to"
    print("Executing: 'go to the kitchen'")
    result = await robot.execute("go to the kitchen")
    print(f"Result: {result}")
    
    # NLP command that translates to "find_object" sequence
    print("\nExecuting: 'find the red ball'")
    result = await robot.execute("find the red ball")
    print(f"Result: {result}")
    
    robot.stop()

if __name__ == "__main__":
    asyncio.run(main())
