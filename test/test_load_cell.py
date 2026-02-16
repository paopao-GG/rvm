#!/usr/bin/env python3
"""
Load Cell Continuous Test
Continuously reads and displays weight from HX711 load cell.
"""

import time
from hx711 import HX711

# Configuration
DT_PIN = 5          # HX711 DOUT pin (BCM)
SCK_PIN = 6         # HX711 PD_SCK pin (BCM)
GAIN = 128          # Channel A gain
SCALE_FACTOR = 10  # Calibration factor (adjust based on your load cell)

# Reading settings
READ_INTERVAL = 0.5  # Seconds between readings
AVERAGE_SAMPLES = 1  # Number of samples to average per reading (reduce noise for light objects)

print("=" * 60)
print("HX711 Load Cell Continuous Test")
print("=" * 60)
print(f"DT Pin:   GPIO {DT_PIN}")
print(f"SCK Pin:  GPIO {SCK_PIN}")
print(f"Gain:     {GAIN}")
print(f"Scale:    {SCALE_FACTOR}")
print(f"Interval: {READ_INTERVAL}s")
print(f"Samples:  {AVERAGE_SAMPLES} per reading")
print("=" * 60)

# Initialize HX711
try:
    hx = HX711(dt_pin=DT_PIN, sck_pin=SCK_PIN, gain=GAIN)
    hx.scale = SCALE_FACTOR
    print("✓ HX711 initialized successfully")
except Exception as e:
    print(f"✗ Failed to initialize HX711: {e}")
    exit(1)

# Ask user if they want to tare
print("\n" + "─" * 60)
print("Tare the scale? (y/n)")
print("  Press 'y' to zero the scale with current load")
print("  Press 'n' to skip taring")
print("─" * 60)

try:
    choice = input("Your choice: ").strip().lower()
    if choice == 'y':
        print("\nTaring... (remove all weight from scale)")
        time.sleep(2)
        hx.tare(times=10)
        print("✓ Scale tared successfully!")
    else:
        print("\nSkipping tare (offset = 0)")
except KeyboardInterrupt:
    print("\n✗ Cancelled")
    hx.cleanup()
    exit(0)

# Start continuous reading
print("\n" + "=" * 60)
print("CONTINUOUS WEIGHT READING")
print("=" * 60)
print("Press Ctrl+C to stop\n")
print(f"{'Time':<12} {'Raw Value':<15} {'Weight (g)':<15} {'Weight (kg)':<15}")
print("─" * 60)

try:
    reading_count = 0
    start_time = time.time()

    while True:
        try:
            # Read raw value and weight
            raw = hx.read_average(times=AVERAGE_SAMPLES)
            weight_grams = hx.get_grams(times=AVERAGE_SAMPLES)
            weight_kg = weight_grams / 1000.0

            # Calculate elapsed time
            elapsed = time.time() - start_time
            time_str = f"{elapsed:.1f}s"

            # Display reading
            print(f"{time_str:<12} {raw:<15.0f} {weight_grams:<15.2f} {weight_kg:<15.3f}")

            reading_count += 1
            time.sleep(READ_INTERVAL)

        except TimeoutError:
            print("⚠ Timeout reading sensor - check connections")
            time.sleep(READ_INTERVAL)

except KeyboardInterrupt:
    print("\n\n" + "=" * 60)
    print("STOPPED")
    print("=" * 60)
    print(f"Total readings: {reading_count}")
    print(f"Total time: {time.time() - start_time:.1f}s")

    # Final reading
    try:
        final_raw = hx.read_average(times=5)
        final_grams = hx.get_grams(times=5)
        print(f"\nFinal reading:")
        print(f"  Raw:    {final_raw:.0f}")
        print(f"  Weight: {final_grams:.2f}g ({final_grams/1000:.3f}kg)")
    except:
        pass

    print("\n" + "─" * 60)
    print("Calibration Notes:")
    print("─" * 60)
    print("If readings seem incorrect:")
    print("  1. Place a known weight on the scale")
    print("  2. Note the raw value displayed")
    print("  3. Calculate: SCALE_FACTOR = raw_value / weight_in_grams")
    print("  4. Update SCALE_FACTOR at the top of this file")
    print(f"  5. Current SCALE_FACTOR = {SCALE_FACTOR}")
    print("─" * 60)

finally:
    hx.cleanup()
    print("\n✓ HX711 cleaned up")
