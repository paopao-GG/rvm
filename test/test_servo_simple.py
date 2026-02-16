#!/usr/bin/env python3
"""
Simple servo test: rotate 0° to 90° and back, repeating.
"""

import time
import board
import busio
from adafruit_servokit import ServoKit

print("=" * 60)
print("Simple Servo Position Test")
print("=" * 60)
print("This will move servo between 0° and 90° repeatedly.")
print("Press Ctrl+C to stop")
print("=" * 60)

# Initialize I2C and PCA9685
i2c_bus = busio.I2C(board.D1, board.D0)
kit = ServoKit(channels=16, i2c=i2c_bus, address=0x40)

# Set PWM frequency to 50Hz (standard for servos)
kit._pca.frequency = 50

try:
    cycle = 1
    while True:
        print(f"\n[Cycle {cycle}]")

        # Move to 0 degrees
        print("  → Moving to 0°...")
        kit.servo[0].angle = 0
        print("  → At 0° - holding for 5 seconds")
        time.sleep(5)

        # Move to 90 degrees
        print("  → Moving to 90°...")
        kit.servo[0].angle = 90
        print("  → At 90° - holding for 5 seconds")
        time.sleep(5)

        cycle += 1

except KeyboardInterrupt:
    print("\n\nStopping servo...")
    kit.servo[0].angle = 0  # Return to 0° position
    time.sleep(1)
    print("✓ Servo stopped at 0°")
    print("\nDiagnostic:")
    print("─" * 60)
    print("If servo MOVED TO POSITIONS and STAYED STILL during 5s waits:")
    print("  ✓ You have STANDARD POSITION servos (real MG995)")
    print("  → The main code should work!")
    print("")
    print("If servo ROTATED CONTINUOUSLY (didn't stop):")
    print("  ✗ You have CONTINUOUS ROTATION servos (fake MG995)")
    print("  → Need to modify code for timed rotation control")
    print("─" * 60)
