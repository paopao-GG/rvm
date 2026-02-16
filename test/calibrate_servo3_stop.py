#!/usr/bin/env python3
"""
Calibrate the STOP angle for Servo 3 (Channel 14)
Find the exact angle where it stops rotating
"""

import time
import board
import busio
from adafruit_servokit import ServoKit

SERVO3_CHANNEL = 14

print("=" * 60)
print("Servo 3 Stop Angle Calibration (Channel 14)")
print("=" * 60)
print("This will test different angles to find where servo 3 stops.")
print("Watch the servo carefully and note which angle makes it stop.")
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
    print("Testing angles from 85° to 95° (typical stop range)...")
    print("Press Ctrl+C when you find the angle that makes it stop.\n")

    # Test angles in the typical stop range
    for angle in range(85, 96):
        print(f"{'─'*60}")
        print(f"Testing angle: {angle}°")
        print(f"{'─'*60}")
        kit.servo[SERVO3_CHANNEL].angle = angle
        print(f"  Servo 3 is now at {angle}°")
        print(f"  Observe: Is it STOPPED or still rotating?")
        print(f"  Waiting 5 seconds...")
        time.sleep(5)

    print("\n" + "="*60)
    print("Test complete! Did you find the stop angle?")
    print("="*60)
    print("If not, let's try a wider range (80° to 100°)...")
    print()

    for angle in range(80, 101):
        print(f"{'─'*60}")
        print(f"Testing angle: {angle}°")
        print(f"{'─'*60}")
        kit.servo[SERVO3_CHANNEL].angle = angle
        print(f"  Servo 3 is now at {angle}°")
        print(f"  Observe: Is it STOPPED or still rotating?")
        print(f"  Waiting 5 seconds...")
        time.sleep(5)

except KeyboardInterrupt:
    print("\n\n" + "="*60)
    print("Calibration interrupted!")
    print("="*60)

finally:
    # Try to stop it at 91° (best guess)
    print("\nStopping servo at 91°...")
    kit.servo[SERVO3_CHANNEL].angle = 91
    time.sleep(1)

    print("\n" + "="*60)
    print("CALIBRATION RESULTS")
    print("="*60)
    print("Remember the angle where servo 3 STOPPED completely.")
    print("")
    print("Common stop angles for continuous rotation servos:")
    print("  - 88° to 92° (most common)")
    print("  - Some servos: 86° or 94°")
    print("")
    print("Once you know the stop angle, update test_open_close.py:")
    print("  1. Add: SERVO3_STOP_ANGLE = <your_angle>")
    print("  2. Use that angle to stop servo 3 instead of 91°")
    print("="*60)
