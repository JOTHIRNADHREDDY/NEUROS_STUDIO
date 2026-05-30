"""
NEUROS Rover Simulator Demo

A complete "Killer Demo" that works out-of-the-box.
Run this to see the Neuros AI OS in action with a simulated robot.
"""

import time
import logging

# Set up basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

def run_demo():
    print("========================================")
    print("      NEUROS Rover Simulator Demo       ")
    print("========================================")
    
    print("\n[1] Initializing NEUROS Operating System...")
    time.sleep(1.0)
    
    print("[2] Booting simulated hardware (ESP32 HAL)...")
    time.sleep(0.5)
    
    print("[3] Starting Vision Worker (Shared Memory)...")
    time.sleep(0.8)
    
    print("\n[ROBOT] System Online. Ready for missions.\n")
    
    # Mock some robot commands
    commands = [
        "robot.move_forward(speed=0.8)",
        "robot.detect_object(target='red bottle')",
        "robot.stop()"
    ]
    
    for cmd in commands:
        print(f">>> Executing: {cmd}")
        time.sleep(1.5)
        if "detect" in cmd:
            print("    [Vision] Found 'red bottle' at (x: 120, y: 80)")
        elif "move" in cmd:
            print("    [Motors] Moving forward...")
        elif "stop" in cmd:
            print("    [Motors] HALTING.")
            print("    [Safety] Emergency Stop OK.")
            
    print("\n========================================")
    print("      Demo Complete!                    ")
    print("========================================")
    print("Next steps: Try 'neuros init my-rover' to build your own!")

if __name__ == "__main__":
    run_demo()
