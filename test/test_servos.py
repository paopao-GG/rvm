#!/usr/bin/env python3
"""
Servo Motor Test Script for PCA9685 on I2C0 (GPIO 0/1)
Tests both intake (servo 1) and exit (servo 2) door servos.
Requires: dtoverlay=i2c0-pi5 in /boot/firmware/config.txt
Wiring: PCA9685 SCL→GPIO1 (Pin 28), SDA→GPIO0 (Pin 27)
"""

import time
import board
import busio
from adafruit_servokit import ServoKit

# Configuration (match main_integrated.py)
SERVO1_CHANNEL = 0      # Intake door
SERVO2_CHANNEL = 1      # Exit door

SERVO1_CLOSED = 0       # Intake closed angle
SERVO1_OPEN = 90        # Intake open angle
SERVO2_CLOSED = 0       # Exit closed angle
SERVO2_OPEN = 90        # Exit open angle

def main():
    print("=" * 60)
    print("PCA9685 Servo Test - I2C0 (GPIO 8/9)")
    print("=" * 60)

    # Initialize I2C0 bus (GPIO 0/1 on RPi 5)
    try:
        print("\n[1/3] Initializing I2C0 bus (GPIO 1=SCL, GPIO 0=SDA)...")
        print("    Using /dev/i2c-0 (requires dtoverlay=i2c0-pi5)")
        i2c_bus = busio.I2C(board.D1, board.D0)  # SCL=GPIO1, SDA=GPIO0
        kit = ServoKit(channels=16, i2c=i2c_bus, address=0x40)
        print("✓ I2C0 bus and PCA9685 initialized successfully")
    except Exception as e:
        print(f"✗ Failed to initialize PCA9685 on I2C0: {e}")
        print("\nTroubleshooting:")
        print("  1. Check if I2C0 is enabled: ls /dev/i2c-*")
        print("     (Should see /dev/i2c-0)")
        print("  2. Verify boot config has: dtoverlay=i2c0-pi5")
        print("  3. Reboot if you just changed the overlay")
        print("  4. Check wiring:")
        print("     PCA9685 VCC → Pin 1 (3.3V)")
        print("     PCA9685 GND → Pin 6 (GND)")
        print("     PCA9685 SCL → Pin 28 (GPIO 1)")
        print("     PCA9685 SDA → Pin 27 (GPIO 0)")
        print("  5. Verify PCA9685 detected: sudo i2cdetect -y 0")
        return

    # Move both servos to CLOSED position
    print("\n[3/3] Setting servos to CLOSED position...")
    try:
        kit.servo[SERVO1_CHANNEL].angle = SERVO1_CLOSED
        print(f"✓ Servo 1 (intake): set to {SERVO1_CLOSED}° (CLOSED)")
        time.sleep(0.5)

        kit.servo[SERVO2_CHANNEL].angle = SERVO2_CLOSED
        print(f"✓ Servo 2 (exit): set to {SERVO2_CLOSED}° (CLOSED)")
        time.sleep(0.5)

        print("\n✓ Both servos initialized in CLOSED state")
    except Exception as e:
        print(f"✗ Failed to move servos: {e}")
        print("\nTroubleshooting:")
        print("  1. Check servo connections to PCA9685 channels 0 and 1")
        print("  2. Verify external 5V power supply is connected to V+ terminal")
        print("  3. Check common ground between RPi and power supply")
        return

    # Interactive test menu
    print("\n" + "=" * 60)
    print("Interactive Servo Test Menu")
    print("=" * 60)
    print("Commands:")
    print("  1  - Open intake door (servo 1)")
    print("  2  - Close intake door (servo 1)")
    print("  3  - Open exit door (servo 2)")
    print("  4  - Close exit door (servo 2)")
    print("  5  - Test full cycle (both servos)")
    print("  c  - Custom angle test")
    print("  q  - Quit (close both servos)")
    print("=" * 60)

    try:
        while True:
            cmd = input("\nEnter command: ").strip().lower()

            if cmd == '1':
                print(f"Opening intake door to {SERVO1_OPEN}°...")
                kit.servo[SERVO1_CHANNEL].angle = SERVO1_OPEN
                print("✓ Intake door OPEN")

            elif cmd == '2':
                print(f"Closing intake door to {SERVO1_CLOSED}°...")
                kit.servo[SERVO1_CHANNEL].angle = SERVO1_CLOSED
                print("✓ Intake door CLOSED")

            elif cmd == '3':
                print(f"Opening exit door to {SERVO2_OPEN}°...")
                kit.servo[SERVO2_CHANNEL].angle = SERVO2_OPEN
                print("✓ Exit door OPEN")

            elif cmd == '4':
                print(f"Closing exit door to {SERVO2_CLOSED}°...")
                kit.servo[SERVO2_CHANNEL].angle = SERVO2_CLOSED
                print("✓ Exit door CLOSED")

            elif cmd == '5':
                print("\nRunning full cycle test...")
                print("  Step 1: Opening intake door...")
                kit.servo[SERVO1_CHANNEL].angle = SERVO1_OPEN
                time.sleep(2)

                print("  Step 2: Closing intake door...")
                kit.servo[SERVO1_CHANNEL].angle = SERVO1_CLOSED
                time.sleep(1)

                print("  Step 3: Opening exit door...")
                kit.servo[SERVO2_CHANNEL].angle = SERVO2_OPEN
                time.sleep(2)

                print("  Step 4: Closing exit door...")
                kit.servo[SERVO2_CHANNEL].angle = SERVO2_CLOSED
                time.sleep(1)

                print("✓ Full cycle complete")

            elif cmd == 'c':
                try:
                    servo_num = int(input("  Enter servo number (1 or 2): "))
                    angle = int(input("  Enter angle (0-180): "))

                    if servo_num == 1:
                        kit.servo[SERVO1_CHANNEL].angle = angle
                        print(f"✓ Servo 1 set to {angle}°")
                    elif servo_num == 2:
                        kit.servo[SERVO2_CHANNEL].angle = angle
                        print(f"✓ Servo 2 set to {angle}°")
                    else:
                        print("✗ Invalid servo number (use 1 or 2)")
                except ValueError:
                    print("✗ Invalid input")

            elif cmd == 'q':
                print("\nClosing both servos and exiting...")
                kit.servo[SERVO1_CHANNEL].angle = SERVO1_CLOSED
                kit.servo[SERVO2_CHANNEL].angle = SERVO2_CLOSED
                time.sleep(1)
                print("✓ Servos closed. Goodbye!")
                break

            else:
                print("✗ Invalid command. Use 1-5, c, or q")

    except KeyboardInterrupt:
        print("\n\nInterrupted! Closing both servos...")
        kit.servo[SERVO1_CHANNEL].angle = SERVO1_CLOSED
        kit.servo[SERVO2_CHANNEL].angle = SERVO2_CLOSED
        time.sleep(1)
        print("✓ Servos closed. Exiting.")

if __name__ == "__main__":
    main()
