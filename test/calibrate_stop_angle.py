#!/usr/bin/env python3
"""
Find the exact STOP angle for continuous rotation servos.
Use arrow keys to fine-tune until servo stops completely.
"""

import time
import board
import busio
from adafruit_servokit import ServoKit
import sys
import tty
import termios

def getch():
    """Get single character from keyboard."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

print("=" * 60)
print("Continuous Rotation Servo - STOP Angle Calibration")
print("=" * 60)
print()
print("This tool helps you find the exact angle that stops the servo.")
print()
print("Controls:")
print("  ↑ (w) - Increase angle by 1°")
print("  ↓ (s) - Decrease angle by 1°")
print("  → (d) - Increase angle by 0.1° (fine tune)")
print("  ← (a) - Decrease angle by 0.1° (fine tune)")
print("  q     - Quit and save stop angle")
print()
print("Goal: Find the angle where servo STOPS COMPLETELY (no movement)")
print("=" * 60)

# Initialize I2C and PCA9685
i2c_bus = busio.I2C(board.D1, board.D0)
kit = ServoKit(channels=16, i2c=i2c_bus, address=0x40)
kit._pca.frequency = 50

# Start at 90° (common stop point)
current_angle = 90.0
servo_channel = 0

print(f"\nStarting at {current_angle}° on servo channel {servo_channel}")
print("Adjusting servo now...\n")

kit.servo[servo_channel].angle = current_angle

try:
    while True:
        print(f"\rCurrent angle: {current_angle:6.1f}°  (Use ↑↓ or ws for ±1°, ←→ or ad for ±0.1°, q to quit)", end='', flush=True)

        key = getch()

        if key == 'q':
            print("\n\n" + "=" * 60)
            print(f"STOP angle found: {current_angle}°")
            print("=" * 60)
            print("\nUpdate your code with these values:")
            print(f"  SERVO_STOP = {current_angle}  # Angle that stops the servo")
            print("\nFor timed rotation control:")
            print(f"  Set servo to {current_angle}° to STOP")
            print(f"  Set servo to {current_angle - 30}° to rotate one direction")
            print(f"  Set servo to {current_angle + 30}° to rotate opposite direction")
            print("=" * 60)
            break

        elif key == 'w' or key == '\x1b[A':  # w or up arrow
            current_angle = min(180, current_angle + 1)
            kit.servo[servo_channel].angle = current_angle

        elif key == 's' or key == '\x1b[B':  # s or down arrow
            current_angle = max(0, current_angle - 1)
            kit.servo[servo_channel].angle = current_angle

        elif key == 'd' or key == '\x1b[C':  # d or right arrow
            current_angle = min(180, current_angle + 0.1)
            kit.servo[servo_channel].angle = current_angle

        elif key == 'a' or key == '\x1b[D':  # a or left arrow
            current_angle = max(0, current_angle - 0.1)
            kit.servo[servo_channel].angle = current_angle

except KeyboardInterrupt:
    print("\n\nCalibration cancelled.")

# Return to stop position
kit.servo[servo_channel].angle = current_angle
print("\n✓ Servo set to stop angle")
