#!/usr/bin/env python3
"""
Quick HX711 Load Cell Diagnostic
Tests if the load cell is connected and working properly
"""

import sys

# Test 1: Check if hx711 library is installed
print("=" * 60)
print("HX711 Load Cell Diagnostic")
print("=" * 60)

print("\n[Test 1/3] Checking hx711 library...")
try:
    from hx711 import HX711
    print("✓ hx711 library is installed")
except ImportError as e:
    print(f"✗ hx711 library NOT installed: {e}")
    print("  Run: pip install hx711")
    sys.exit(1)

# Test 2: Try to initialize HX711
print("\n[Test 2/3] Initializing HX711...")
DT_PIN = 5   # GPIO 5 (data)
SCK_PIN = 6  # GPIO 6 (clock)

try:
    hx = HX711(dt_pin=DT_PIN, sck_pin=SCK_PIN, gain=128)
    print(f"✓ HX711 initialized successfully")
    print(f"  DT Pin:  GPIO {DT_PIN}")
    print(f"  SCK Pin: GPIO {SCK_PIN}")
except Exception as e:
    print(f"✗ Failed to initialize HX711: {e}")
    print("\nCheck wiring:")
    print(f"  HX711 DT (data)  → GPIO {DT_PIN} (Pin 29)")
    print(f"  HX711 SCK (clock) → GPIO {SCK_PIN} (Pin 31)")
    print("  HX711 VCC → 5V (Pin 2 or 4)")
    print("  HX711 GND → GND (Pin 6, 9, 14, 20, etc.)")
    sys.exit(1)

# Test 3: Try to read from load cell
print("\n[Test 3/3] Reading from load cell...")
try:
    print("Reading raw value (this may take 2-3 seconds)...")
    raw_value = hx.read_average(times=5)
    print(f"✓ Successfully read from load cell!")
    print(f"  Raw value: {raw_value:.0f}")
    print(f"\nLoad cell is WORKING! ✓")

    print("\n" + "=" * 60)
    print("Next steps:")
    print("=" * 60)
    print("1. Restart the main service:")
    print("   sudo systemctl restart rvm-main.service")
    print("")
    print("2. Check logs to confirm load cell is detected:")
    print("   tail -f /tmp/rvm_main_integrated.log")
    print("")
    print("3. Look for these messages:")
    print("   ✓ 'Load cell: initialized and tared'")
    print("   ✓ 'Baseline weight: XXXX (raw)'")
    print("=" * 60)

except Exception as e:
    print(f"✗ Failed to read from load cell: {e}")
    print("\nPossible issues:")
    print("  1. Wiring problem - check connections")
    print("  2. Load cell not connected to HX711")
    print("  3. Faulty HX711 module")
    print("  4. Incorrect GPIO pins")
    sys.exit(1)
finally:
    try:
        hx.cleanup()
    except:
        pass
