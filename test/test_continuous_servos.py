#!/usr/bin/env python3
"""
Test script for CONTINUOUS ROTATION servos with timed control.
Tests door open/close cycles with proper timing.
"""

import time
import board
import busio
from adafruit_servokit import ServoKit

# Continuous rotation servo configuration
SERVO1_CHANNEL = 0
SERVO2_CHANNEL = 1

# Calibrated values
SERVO_STOP = 91         # Angle that stops rotation (calibrated)
SERVO1_OPEN_SPEED = 60  # Rotate to open (lower angle = one direction)
SERVO1_CLOSE_SPEED = 120  # Rotate to close (higher angle = opposite direction)
SERVO2_OPEN_SPEED = 60
SERVO2_CLOSE_SPEED = 120

# Timing (tune these based on how far your doors need to move)
SERVO1_OPEN_TIME = 2.0  # Seconds to rotate open
SERVO1_CLOSE_TIME = 2.0  # Seconds to rotate closed
SERVO1_STAY_OPEN = 5.0  # Seconds to stay in open position

SERVO2_OPEN_TIME = 1.5
SERVO2_CLOSE_TIME = 1.5
SERVO2_STAY_OPEN = 3.0

def test_servo(kit, channel, name, open_speed, close_speed,
               open_time, close_time, stay_open):
    """Test one servo through open/close cycle."""
    print(f"\n{'='*60}")
    print(f"Testing {name} (Channel {channel})")
    print(f"{'='*60}")

    # Ensure stopped
    print(f"[1/5] Stopping servo...")
    kit.servo[channel].angle = SERVO_STOP
    time.sleep(1)

    # Open door
    print(f"[2/5] Opening {name} (rotating at {open_speed}° for {open_time}s)...")
    kit.servo[channel].angle = open_speed
    time.sleep(open_time)

    # Stop
    print(f"[3/5] Door open - stopping servo...")
    kit.servo[channel].angle = SERVO_STOP

    # Stay open
    print(f"[4/5] Door stays open for {stay_open}s (waiting)...")
    time.sleep(stay_open)

    # Close door
    print(f"[5/5] Closing {name} (rotating at {close_speed}° for {close_time}s)...")
    kit.servo[channel].angle = close_speed
    time.sleep(close_time)

    # Stop
    print(f"✓ Door closed - stopping servo...")
    kit.servo[channel].angle = SERVO_STOP
    time.sleep(1)

    print(f"✓ {name} test complete!")

def main():
    print("=" * 60)
    print("Continuous Rotation Servo Test")
    print("=" * 60)
    print(f"Stop angle: {SERVO_STOP}°")
    print("=" * 60)

    # Initialize I2C and PCA9685
    try:
        i2c_bus = busio.I2C(board.D1, board.D0)
        kit = ServoKit(channels=16, i2c=i2c_bus, address=0x40)
        kit._pca.frequency = 50
        print("✓ PCA9685 initialized on I2C0")
    except Exception as e:
        print(f"✗ Failed to initialize PCA9685: {e}")
        return

    # Ensure both servos are stopped initially
    print("\nInitializing servos to STOP position...")
    kit.servo[SERVO1_CHANNEL].angle = SERVO_STOP
    kit.servo[SERVO2_CHANNEL].angle = SERVO_STOP
    time.sleep(2)

    try:
        while True:
            choice = input("\nTest which servo? (1=intake, 2=exit, b=both, q=quit): ").strip()

            if choice == '1':
                test_servo(kit, SERVO1_CHANNEL, "Intake Door",
                          SERVO1_OPEN_SPEED, SERVO1_CLOSE_SPEED,
                          SERVO1_OPEN_TIME, SERVO1_CLOSE_TIME, SERVO1_STAY_OPEN)

            elif choice == '2':
                test_servo(kit, SERVO2_CHANNEL, "Exit Door",
                          SERVO2_OPEN_SPEED, SERVO2_CLOSE_SPEED,
                          SERVO2_OPEN_TIME, SERVO2_CLOSE_TIME, SERVO2_STAY_OPEN)

            elif choice == 'b':
                print("\n" + "="*60)
                print("Testing BOTH servos (simulating bottle flow)")
                print("="*60)

                test_servo(kit, SERVO1_CHANNEL, "Intake Door",
                          SERVO1_OPEN_SPEED, SERVO1_CLOSE_SPEED,
                          SERVO1_OPEN_TIME, SERVO1_CLOSE_TIME, SERVO1_STAY_OPEN)

                print("\n[User drops bottle, weight detected...]\n")

                test_servo(kit, SERVO2_CHANNEL, "Exit Door",
                          SERVO2_OPEN_SPEED, SERVO2_CLOSE_SPEED,
                          SERVO2_OPEN_TIME, SERVO2_CLOSE_TIME, SERVO2_STAY_OPEN)

                print("\n✓ Full cycle complete!")

            elif choice == 'q':
                break

            else:
                print("Invalid choice. Use 1, 2, b, or q")

    except KeyboardInterrupt:
        print("\n\nInterrupted!")

    finally:
        print("\nStopping all servos...")
        kit.servo[SERVO1_CHANNEL].angle = SERVO_STOP
        kit.servo[SERVO2_CHANNEL].angle = SERVO_STOP
        print("✓ All servos stopped")
        print("\n" + "="*60)
        print("Tuning Guide:")
        print("="*60)
        print("If door doesn't open enough:")
        print("  → Increase OPEN_TIME (e.g., 2.0 → 2.5)")
        print()
        print("If door rotates too far:")
        print("  → Decrease OPEN_TIME (e.g., 2.0 → 1.5)")
        print()
        print("If door rotates wrong direction:")
        print("  → Swap OPEN_SPEED and CLOSE_SPEED values")
        print("="*60)

if __name__ == "__main__":
    main()
