#!/usr/bin/env python3
"""
Quick test to determine if servos are position or continuous rotation type.
"""

import time
import board
import busio
from adafruit_servokit import ServoKit

print("=" * 60)
print("Servo Type Diagnostic Test")
print("=" * 60)

# Initialize I2C and PCA9685
i2c_bus = busio.I2C(board.D1, board.D0)
kit = ServoKit(channels=16, i2c=i2c_bus, address=0x40)

print("\nTesting Servo 1 on Channel 0...")
print("\n1. Setting angle to 90° (should be STOPPED if continuous, or middle position if standard)")
kit.servo[0].angle = 90
time.sleep(3)

print("\n2. Setting angle to 0° (should rotate CCW if continuous, or go to 0° if standard)")
kit.servo[0].angle = 0
time.sleep(3)

print("\n3. Setting angle to 180° (should rotate CW if continuous, or go to 180° if standard)")
kit.servo[0].angle = 180
time.sleep(3)

print("\n4. Setting angle to 90° again")
kit.servo[0].angle = 90
time.sleep(2)

print("\n" + "=" * 60)
print("RESULTS:")
print("=" * 60)
print("If servo STOPPED completely at 90°, ROTATED at 0° and 180°:")
print("  → You have CONTINUOUS ROTATION servos (fake MG995)")
print("")
print("If servo moved to DIFFERENT POSITIONS and STAYED THERE:")
print("  → You have STANDARD POSITION servos (real MG995)")
print("=" * 60)

answer = input("\nDid the servo STOP at 90° and ROTATE at 0°/180°? (yes/no): ").strip().lower()

if answer in ['yes', 'y']:
    print("\n✗ You have CONTINUOUS ROTATION servos (fake/clone MG995)")
    print("  Options:")
    print("  1. Buy real MG996R or SG90 servos (standard position)")
    print("  2. I can modify the code to use timing-based control")
else:
    print("\n✓ You have STANDARD POSITION servos")
    print("  The code should work. Let's check PCA9685 frequency...")
    print(f"  Current frequency: {kit._pca.frequency}Hz (should be ~50Hz)")

    # Try to set frequency explicitly
    kit._pca.frequency = 50
    print(f"  Set frequency to: {kit._pca.frequency}Hz")
    print("\n  Try running test_servos.py again!")
