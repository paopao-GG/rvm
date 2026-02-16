#!/usr/bin/env python3
"""
Simple test: Open and close all three servos repeatedly.
For continuous rotation servos (MG995 clones).
Servo 2 has reversed direction (open/close swapped).
"""

import time
import board
import busio
from adafruit_servokit import ServoKit

# Configuration
SERVO1_CHANNEL = 15     # Exit door servo
SERVO2_CHANNEL = 1      # Intake door servo
SERVO3_CHANNEL = 14     # Third servo

# Continuous rotation settings
STOP_ANGLE = 91         # Calibrated stop angle for servos 1 & 2
SERVO3_STOP_ANGLE = 92  # Calibrated stop angle for servo 3

# Servo 1 (Exit door) - normal direction
SERVO1_OPEN_SPEED = 130   # Speed/direction to open
SERVO1_CLOSE_SPEED = 60 # Speed/direction to close

# Servo 2 (Intake door) - REVERSED direction
SERVO2_OPEN_SPEED = 130  # Reversed: close becomes open
SERVO2_CLOSE_SPEED = 60  # Reversed: open becomes close

# Servo 3 (Third servo) - normal direction with MUCH wider rotation
SERVO3_OPEN_SPEED = 160   # Speed/direction to open (much wider rotation)
SERVO3_CLOSE_SPEED = 20 # Speed/direction to close (much wider rotation)

# Timing (adjust these if needed)
OPEN_TIME = 0.3         # Seconds to rotate when opening
CLOSE_TIME = 0.3        # Seconds to rotate when closing
PAUSE_TIME = 5.0        # Seconds to pause between open/close

print("=" * 60)
print("Triple Servo Open/Close Test")
print("=" * 60)
print(f"Servo 1 (Exit door) - Channel {SERVO1_CHANNEL}")
print(f"  Open: {SERVO1_OPEN_SPEED}° for {OPEN_TIME}s")
print(f"  Close: {SERVO1_CLOSE_SPEED}° for {CLOSE_TIME}s")
print()
print(f"Servo 2 (Intake door) - Channel {SERVO2_CHANNEL} [REVERSED]")
print(f"  Open: {SERVO2_OPEN_SPEED}° for {OPEN_TIME}s")
print(f"  Close: {SERVO2_CLOSE_SPEED}° for {CLOSE_TIME}s")
print()
print(f"Servo 3 (Third servo) - Channel {SERVO3_CHANNEL}")
print(f"  Open: {SERVO3_OPEN_SPEED}° for {OPEN_TIME}s")
print(f"  Close: {SERVO3_CLOSE_SPEED}° for {CLOSE_TIME}s")
print()
print(f"Stop angles: Servo 1&2={STOP_ANGLE}°, Servo 3={SERVO3_STOP_ANGLE}°")
print("=" * 60)
print("\nPress Ctrl+C to stop\n")

# Initialize I2C and PCA9685
try:
    i2c_bus = busio.I2C(board.D1, board.D0)
    kit = ServoKit(channels=16, i2c=i2c_bus, address=0x40)
    kit._pca.frequency = 50
    print("✓ PCA9685 initialized\n")
except Exception as e:
    print(f"✗ Failed to initialize: {e}")
    exit(1)

# Make sure all servos are stopped initially
print("Initializing all servos to STOP...")
kit.servo[SERVO1_CHANNEL].angle = STOP_ANGLE
kit.servo[SERVO2_CHANNEL].angle = STOP_ANGLE
kit.servo[SERVO3_CHANNEL].angle = SERVO3_STOP_ANGLE
time.sleep(2)

try:
    cycle = 1
    while True:
        print(f"\n{'─'*60}")
        print(f"Cycle {cycle}")
        print(f"{'─'*60}")

        # OPEN ALL SERVOS
        print(f"[1/3] OPENING all servos...")
        print(f"      Servo 1: rotating at {SERVO1_OPEN_SPEED}° for {OPEN_TIME}s")
        print(f"      Servo 2: rotating at {SERVO2_OPEN_SPEED}° for {OPEN_TIME}s")
        print(f"      Servo 3: rotating at {SERVO3_OPEN_SPEED}° for {OPEN_TIME}s")
        kit.servo[SERVO1_CHANNEL].angle = SERVO1_OPEN_SPEED
        kit.servo[SERVO2_CHANNEL].angle = SERVO2_OPEN_SPEED
        kit.servo[SERVO3_CHANNEL].angle = SERVO3_OPEN_SPEED
        time.sleep(OPEN_TIME)

        print(f"[2/3] Stopping all servos...")
        kit.servo[SERVO1_CHANNEL].angle = STOP_ANGLE
        kit.servo[SERVO2_CHANNEL].angle = STOP_ANGLE
        kit.servo[SERVO3_CHANNEL].angle = SERVO3_STOP_ANGLE
        print(f"      ✓ All doors are OPEN - pausing for {PAUSE_TIME}s")
        time.sleep(PAUSE_TIME)

        # CLOSE ALL SERVOS
        print(f"[3/3] CLOSING all servos...")
        print(f"      Servo 1: rotating at {SERVO1_CLOSE_SPEED}° for {CLOSE_TIME}s")
        print(f"      Servo 2: rotating at {SERVO2_CLOSE_SPEED}° for {CLOSE_TIME}s")
        print(f"      Servo 3: rotating at {SERVO3_CLOSE_SPEED}° for {CLOSE_TIME}s")
        kit.servo[SERVO1_CHANNEL].angle = SERVO1_CLOSE_SPEED
        kit.servo[SERVO2_CHANNEL].angle = SERVO2_CLOSE_SPEED
        kit.servo[SERVO3_CHANNEL].angle = SERVO3_CLOSE_SPEED
        time.sleep(CLOSE_TIME)

        print(f"      Stopping all servos...")
        kit.servo[SERVO1_CHANNEL].angle = STOP_ANGLE
        kit.servo[SERVO2_CHANNEL].angle = STOP_ANGLE
        kit.servo[SERVO3_CHANNEL].angle = SERVO3_STOP_ANGLE
        print(f"      ✓ All doors are CLOSED - pausing for {PAUSE_TIME}s")
        time.sleep(PAUSE_TIME)

        cycle += 1

except KeyboardInterrupt:
    print("\n\n" + "="*60)
    print("Stopping all servos...")
    kit.servo[SERVO1_CHANNEL].angle = STOP_ANGLE
    kit.servo[SERVO2_CHANNEL].angle = STOP_ANGLE
    kit.servo[SERVO3_CHANNEL].angle = SERVO3_STOP_ANGLE
    print(f"✓ All servos stopped (S1&S2={STOP_ANGLE}°, S3={SERVO3_STOP_ANGLE}°)")
    print("="*60)
    print("\nDiagnostic:")
    print("─"*60)
    print("If ALL doors OPEN and CLOSE correctly:")
    print("  ✓ Timing is good, ready for main system!")
    print("")
    print("If Servo 1 (exit door) doesn't open/close enough:")
    print("  → Edit OPEN_TIME/CLOSE_TIME in this file (increase)")
    print("")
    print("If Servo 1 rotates wrong direction:")
    print("  → Edit this file: swap SERVO1_OPEN_SPEED ↔ SERVO1_CLOSE_SPEED")
    print("")
    print("If Servo 2 (intake door) doesn't open/close enough:")
    print("  → Edit OPEN_TIME/CLOSE_TIME in this file (increase)")
    print("")
    print("If Servo 2 rotates wrong direction:")
    print("  → Edit this file: swap SERVO2_OPEN_SPEED ↔ SERVO2_CLOSE_SPEED")
    print("")
    print("If Servo 3 (third servo) doesn't open/close enough:")
    print("  → Edit OPEN_TIME/CLOSE_TIME in this file (increase)")
    print("")
    print("If Servo 3 rotates wrong direction:")
    print("  → Edit this file: swap SERVO3_OPEN_SPEED ↔ SERVO3_CLOSE_SPEED")
    print("─"*60)
