#!/usr/bin/env python3
"""
Diagnostic test for Servo 3 (Channel 14)
Determines if it's a continuous rotation or standard positional servo
"""

import time
import board
import busio
from adafruit_servokit import ServoKit

SERVO3_CHANNEL = 14

print("=" * 60)
print("Servo 3 Diagnostic Test (Channel 14)")
print("=" * 60)
print("This test will help determine what type of servo you have.")
print("Press Ctrl+C to stop")
print("=" * 60)

# Initialize I2C and PCA9685
try:
    i2c_bus = busio.I2C(board.D1, board.D0)
    kit = ServoKit(channels=16, i2c=i2c_bus, address=0x40)
    kit._pca.frequency = 50
    print("✓ PCA9685 initialized\n")
except Exception as e:
    print(f"✗ Failed to initialize: {e}")
    exit(1)

try:
    print("\n" + "─"*60)
    print("TEST 1: Standard Positional Servo Test")
    print("─"*60)
    print("If servo 3 is a POSITIONAL servo, it should:")
    print("  - Move to 0° and STOP there")
    print("  - Move to 90° and STOP there")
    print("  - Move to 180° and STOP there")
    print()

    print("[1/3] Moving to 0°...")
    kit.servo[SERVO3_CHANNEL].angle = 0
    print("      Waiting 3 seconds... (watch if it STOPS at position)")
    time.sleep(3)

    print("[2/3] Moving to 90°...")
    kit.servo[SERVO3_CHANNEL].angle = 90
    print("      Waiting 3 seconds... (watch if it STOPS at position)")
    time.sleep(3)

    print("[3/3] Moving to 180°...")
    kit.servo[SERVO3_CHANNEL].angle = 180
    print("      Waiting 3 seconds... (watch if it STOPS at position)")
    time.sleep(3)

    print("\n" + "─"*60)
    print("TEST 2: Continuous Rotation Servo Test")
    print("─"*60)
    print("If servo 3 is a CONTINUOUS ROTATION servo, it should:")
    print("  - Rotate continuously at 60° (one direction)")
    print("  - STOP at 91°")
    print("  - Rotate continuously at 120° (opposite direction)")
    print()

    print("[1/3] Sending 60° (should rotate continuously)...")
    kit.servo[SERVO3_CHANNEL].angle = 60
    print("      Rotating for 2 seconds...")
    time.sleep(2)

    print("[2/3] Sending 91° (should STOP)...")
    kit.servo[SERVO3_CHANNEL].angle = 91
    print("      Waiting 2 seconds... (should be stopped)")
    time.sleep(2)

    print("[3/3] Sending 120° (should rotate opposite direction)...")
    kit.servo[SERVO3_CHANNEL].angle = 120
    print("      Rotating for 2 seconds...")
    time.sleep(2)

    print("\n[Final] Sending 91° to stop...")
    kit.servo[SERVO3_CHANNEL].angle = 91

    print("\n\n" + "="*60)
    print("RESULTS - Which behavior did you observe?")
    print("="*60)

except KeyboardInterrupt:
    print("\n\n[Interrupted]")

finally:
    print("\n" + "─"*60)
    print("Stopping servo 3...")
    kit.servo[SERVO3_CHANNEL].angle = 91
    print("✓ Sent stop signal (91°)")
    print("─"*60)

    print("\nDIAGNOSIS:")
    print("─"*60)
    print("Option A: STANDARD POSITIONAL SERVO")
    print("  Behavior: Moved to 0°, 90°, 180° and STOPPED at each position")
    print("  Type: Real MG995 or SG90 (standard servo)")
    print("  Control: Send target angle (0-180°), it moves and stays")
    print("")
    print("Option B: CONTINUOUS ROTATION SERVO")
    print("  Behavior: Kept rotating at 60° and 120°, stopped at 91°")
    print("  Type: Fake MG995 or modified servo (continuous rotation)")
    print("  Control: Send speed (0-90 = reverse, 91 = stop, 92-180 = forward)")
    print("─"*60)
    print("\nWhich one did you observe? (A or B)")
    print("This will help determine how to integrate servo 3 into the system.")
    print("─"*60)
