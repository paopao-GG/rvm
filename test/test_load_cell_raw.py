#!/usr/bin/env python3
"""
Load Cell Raw Value Test
Continuously prints raw values and weight change from tare baseline.
Run from test/ directory: python3 test_load_cell_raw.py
"""

import time
from hx711 import HX711

# Configuration
DT_PIN = 5          # HX711 DOUT pin (BCM)
SCK_PIN = 6         # HX711 PD_SCK pin (BCM)
GAIN = 128          # Channel A gain
SAMPLES = 10        # Samples to average per reading
SCALE_FACTOR = 10   # Raw units per gram (adjust after calibration)
READ_INTERVAL = 0.5 # Seconds between readings

print("=" * 60)
print("HX711 Load Cell Raw Test")
print("=" * 60)
print(f"DT Pin:   GPIO {DT_PIN}")
print(f"SCK Pin:  GPIO {SCK_PIN}")
print(f"Gain:     {GAIN}")
print(f"Samples:  {SAMPLES}")
print(f"Scale:    {SCALE_FACTOR} (raw per gram)")
print(f"Interval: {READ_INTERVAL}s")
print("=" * 60)

# Initialize HX711
try:
    hx = HX711(dt_pin=DT_PIN, sck_pin=SCK_PIN, gain=GAIN)
    print("✓ HX711 initialized")
except Exception as e:
    print(f"✗ Failed to initialize HX711: {e}")
    exit(1)

# Tare
print("\nTaring... (keep scale empty)")
time.sleep(1)
hx.tare(times=SAMPLES)
tare_value = hx.read_average(times=SAMPLES)
print(f"✓ Tare baseline: {tare_value:.0f}")

# Continuous reading
print("\n" + "=" * 60)
print("CONTINUOUS READING (Press Ctrl+C to stop)")
print("=" * 60)
print(f"{'Time':<10} {'Raw':<15} {'Change':<15} {'Grams':<12} {'Kg':<10}")
print("─" * 60)

try:
    count = 0
    start = time.time()

    while True:
        raw = hx.read_average(times=SAMPLES)
        change = raw - tare_value
        grams = change / SCALE_FACTOR
        kg = grams / 1000.0
        elapsed = time.time() - start

        print(f"{elapsed:<10.1f} {raw:<15.0f} {change:<15.0f} {grams:<12.1f} {kg:<10.3f}")

        count += 1
        time.sleep(READ_INTERVAL)

except KeyboardInterrupt:
    print("\n\n" + "=" * 60)
    print("STOPPED")
    print("=" * 60)
    print(f"Total readings: {count}")
    print(f"Total time: {time.time() - start:.1f}s")
    print(f"Tare baseline: {tare_value:.0f}")

    print("\n" + "─" * 60)
    print("Calibration:")
    print("─" * 60)
    print("1. Place a known weight (e.g. 100g) on the scale")
    print("2. Note the 'Change' value")
    print("3. SCALE_FACTOR = Change / weight_in_grams")
    print(f"   Current SCALE_FACTOR = {SCALE_FACTOR}")
    print("4. Update SCALE_FACTOR in this file and main_integrated.py")
    print("─" * 60)

finally:
    hx.cleanup()
    print("\n✓ HX711 cleaned up")
