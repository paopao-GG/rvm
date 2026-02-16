# Load Cell with HX711 - Python Code

Python scripts for using a 1kg load cell with HX711 ADC on Raspberry Pi.

## Hardware Setup

### Wiring
Connect the HX711 to your Raspberry Pi:
- **VCC** → 3.3V or 5V
- **GND** → Ground
- **DT (DOUT)** → GPIO 5 (BCM)
- **SCK (PD_SCK)** → GPIO 6 (BCM)

Connect your load cell to HX711:
- **Red** → E+ (Excitation+)
- **Black** → E- (Excitation-)
- **White** → A- (Signal-)
- **Green** → A+ (Signal+)

*Note: Wire colors may vary by manufacturer - check your load cell datasheet*

## Software Installation

### 1. Install Python library
```bash
pip3 install hx711
```

### 2. Enable GPIO (if needed)
```bash
sudo raspi-config
# Navigate to: Interface Options → I2C/SPI (enable if needed)
```

## Usage

### Step 1: Calibrate Your Load Cell

**Run the calibration script first:**
```bash
python3 calibrate_load_cell.py
```

This will guide you through:
1. Taring (zeroing) the scale
2. Measuring with a known weight
3. Calculating the correct SCALE_FACTOR
4. Verifying the calibration

You'll need a known weight (e.g., 100g, 500g, or 1000g) for calibration.

### Step 2: Test Continuous Reading

**After calibration, update and run the test script:**
```bash
python3 test_load_cell.py
```

Update line 14 with your calculated SCALE_FACTOR from calibration:
```python
SCALE_FACTOR = 50  # Replace with your calibrated value
```

### Step 3: Use Simple Example

**For basic integration into your projects:**
```bash
python3 simple_load_cell.py
```

## Files

- **calibrate_load_cell.py** - Interactive calibration wizard
- **test_load_cell.py** - Continuous weight monitoring with detailed output
- **simple_load_cell.py** - Minimal example for quick testing

## Troubleshooting

### No readings or timeout errors
- Check wiring connections
- Verify GPIO pins (BCM 5 and 6 by default)
- Ensure load cell is properly connected to HX711
- Try running with `sudo` if permission issues

### Readings are unstable
- Ensure load cell is mounted rigidly
- Reduce vibrations
- Increase AVERAGE_SAMPLES in the code
- Check for loose connections

### Readings are incorrect
- Re-run calibration with a precise known weight
- Ensure load cell capacity matches your application (1kg max)
- Check that SCALE_FACTOR is updated in the script

### Negative readings
- Check load cell wiring (swap A+ and A- if consistently negative)
- Ensure proper taring before use

## Example Code Snippet

```python
from hx711 import HX711

# Initialize
hx = HX711(dt_pin=5, sck_pin=6, gain=128)
hx.scale = 50  # Your calibrated scale factor

# Tare (zero)
hx.tare(times=15)

# Read weight
weight_grams = hx.get_grams(times=5)
print(f"Weight: {weight_grams:.2f}g")

# Cleanup
hx.cleanup()
```

## Specifications (Typical 1kg Load Cell)

- **Capacity:** 1kg (1000g)
- **Resolution:** ~0.1g with HX711
- **Operating Voltage:** 3.3V - 5V
- **Output:** Analog (amplified by HX711 to digital)

## References

- [HX711 PyPI Package](https://pypi.org/project/hx711/)
- [HX711 Datasheet](https://cdn.sparkfun.com/datasheets/Sensors/ForceFlex/hx711_english.pdf)
- [Raspberry Pi GPIO Pinout](https://pinout.xyz/)
