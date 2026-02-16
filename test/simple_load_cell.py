#!/usr/bin/env python3
"""
Simple Load Cell Example
Minimal code to read weight from a 1kg load cell with HX711.
"""

import time
from hx711 import HX711

# Pin Configuration (BCM numbering)
DT_PIN = 5      # Data pin
SCK_PIN = 6     # Clock pin

# Calibration values (run calibrate_load_cell.py to find these)
SCALE_FACTOR = 50   # Adjust this based on your calibration
OFFSET = 0          # Will be set during tare

def main():
    # Initialize HX711
    print("Initializing HX711...")
    hx = HX711(dt_pin=DT_PIN, sck_pin=SCK_PIN, gain=128)
    hx.scale = SCALE_FACTOR

    try:
        # Tare the scale (zero it)
        print("Remove all weight and taring...")
        time.sleep(2)
        hx.tare(times=15)
        print("Scale tared!\n")

        # Read weight continuously
        print("Reading weight (Ctrl+C to stop):")
        print("-" * 40)

        while True:
            # Get weight in grams
            weight_g = hx.get_grams(times=5)
            weight_kg = weight_g / 1000.0

            # Display
            print(f"Weight: {weight_g:7.2f}g ({weight_kg:6.3f}kg)")

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n\nStopped")
    finally:
        hx.cleanup()
        print("Cleanup complete")

if __name__ == "__main__":
    main()
