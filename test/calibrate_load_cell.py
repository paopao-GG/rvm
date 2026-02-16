#!/usr/bin/env python3
"""
Load Cell Calibration Script
Helps you calibrate your 1kg load cell with HX711 to find the correct scale factor.
"""

import time
from hx711 import HX711

# Configuration
DT_PIN = 5          # HX711 DOUT pin (BCM)
SCK_PIN = 6         # HX711 PD_SCK pin (BCM)
GAIN = 128          # Channel A gain

# Calibration settings
CALIBRATION_SAMPLES = 20  # Number of samples to average for calibration

print("=" * 60)
print("HX711 LOAD CELL CALIBRATION")
print("=" * 60)
print(f"DT Pin:   GPIO {DT_PIN}")
print(f"SCK Pin:  GPIO {SCK_PIN}")
print(f"Gain:     {GAIN}")
print(f"Samples:  {CALIBRATION_SAMPLES} per measurement")
print("=" * 60)

# Initialize HX711
try:
    hx = HX711(dt_pin=DT_PIN, sck_pin=SCK_PIN, gain=GAIN)
    print("\n✓ HX711 initialized successfully")
except Exception as e:
    print(f"\n✗ Failed to initialize HX711: {e}")
    exit(1)

print("\n" + "─" * 60)
print("CALIBRATION PROCESS")
print("─" * 60)
print("This script will help you calibrate your load cell.")
print("You will need a known weight (e.g., 100g, 500g, or 1000g)")
print("─" * 60)

try:
    # Step 1: Tare (get offset with no weight)
    print("\n[STEP 1] TARE - Zero the Scale")
    print("─" * 60)
    input("Remove ALL weight from the scale, then press ENTER...")

    print("\nMeasuring offset (no weight)...")
    time.sleep(1)

    hx.tare(times=CALIBRATION_SAMPLES)
    offset_value = hx.offset

    print(f"✓ Offset recorded: {offset_value:.0f}")
    print("  (This is the 'zero' point of your scale)")

    # Step 2: Measure with known weight
    print("\n[STEP 2] CALIBRATE - Measure Known Weight")
    print("─" * 60)

    # Ask for known weight
    known_weight = None
    while known_weight is None:
        try:
            weight_input = input("Enter the weight you'll use in GRAMS (e.g., 100, 500, 1000): ").strip()
            known_weight = float(weight_input)
            if known_weight <= 0:
                print("✗ Weight must be positive. Try again.")
                known_weight = None
        except ValueError:
            print("✗ Invalid input. Please enter a number.")

    print(f"\nYou entered: {known_weight}g")
    input(f"Place EXACTLY {known_weight}g on the scale, then press ENTER...")

    print("\nMeasuring with weight...")
    time.sleep(2)  # Let the scale settle

    # Read raw value with known weight
    raw_with_weight = hx.read_average(times=CALIBRATION_SAMPLES)

    print(f"✓ Raw value with weight: {raw_with_weight:.0f}")

    # Step 3: Calculate scale factor
    print("\n[STEP 3] CALCULATE - Determine Scale Factor")
    print("─" * 60)

    # The scale factor is the difference divided by the known weight
    raw_difference = raw_with_weight - offset_value
    scale_factor = raw_difference / known_weight

    print(f"Raw difference: {raw_difference:.0f}")
    print(f"Known weight:   {known_weight}g")
    print(f"\n✓ CALCULATED SCALE FACTOR: {scale_factor:.2f}")

    # Step 4: Verify calibration
    print("\n[STEP 4] VERIFY - Test Calibration")
    print("─" * 60)

    hx.scale = scale_factor

    input("Keep the weight on the scale and press ENTER to verify...")

    measured_weight = hx.get_grams(times=CALIBRATION_SAMPLES)
    error_grams = measured_weight - known_weight
    error_percent = (error_grams / known_weight) * 100

    print(f"\nVerification Results:")
    print(f"  Expected weight:  {known_weight:.2f}g")
    print(f"  Measured weight:  {measured_weight:.2f}g")
    print(f"  Error:           {error_grams:+.2f}g ({error_percent:+.2f}%)")

    if abs(error_percent) < 5:
        print("  ✓ Calibration looks GOOD!")
    elif abs(error_percent) < 10:
        print("  ⚠ Calibration is OK, but could be better")
    else:
        print("  ✗ Calibration may need adjustment")

    # Final summary
    print("\n" + "=" * 60)
    print("CALIBRATION COMPLETE!")
    print("=" * 60)
    print("\nYour calibration values:")
    print(f"  SCALE_FACTOR = {scale_factor:.2f}")
    print(f"  OFFSET       = {offset_value:.0f}")
    print("\nTo use these values:")
    print(f"  1. Open test_load_cell.py")
    print(f"  2. Change line 14 to: SCALE_FACTOR = {scale_factor:.2f}")
    print(f"  3. Run the test script to measure weights")
    print("=" * 60)

    # Optional: Test with weight removed
    print("\n[OPTIONAL] Test Zero Reading")
    choice = input("Remove weight and test zero reading? (y/n): ").strip().lower()
    if choice == 'y':
        input("Remove ALL weight from the scale, then press ENTER...")
        time.sleep(1)
        zero_weight = hx.get_grams(times=CALIBRATION_SAMPLES)
        print(f"Zero reading: {zero_weight:.2f}g")
        if abs(zero_weight) < 5:
            print("✓ Zero reading looks good!")
        else:
            print(f"⚠ Zero reading is off by {zero_weight:.2f}g")

except KeyboardInterrupt:
    print("\n\n✗ Calibration cancelled")
except Exception as e:
    print(f"\n✗ Error during calibration: {e}")
finally:
    hx.cleanup()
    print("\n✓ HX711 cleaned up")
