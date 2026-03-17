P.E.T-O Reverse Vending Machine (RVM)
======================================

OVERVIEW
--------
A Reverse Vending Machine running on Raspberry Pi 5 that gives users
free WiFi in exchange for empty plastic bottles. The system:

1. Creates a WiFi hotspot with a captive portal
2. Scans bottle barcodes to identify the bottle type
3. Uses AI (YOLOv8) to visually confirm a real bottle is present
4. Opens a servo-driven intake door for the user to drop the bottle
5. Verifies the bottle was actually inserted via a load cell (weight sensor)
6. Credits WiFi time to the user's account
7. Manages internet access per user via iptables MAC filtering

HARDWARE
--------
- Raspberry Pi 5 (main controller + WiFi hotspot)
- Ethernet cable (connects RPi to router/modem for WAN internet)
- MH-ET Live Scanner V3 (USB barcode scanner, acts as HID keyboard)
- USB Webcam (for AI bottle detection)
- PCA9685 16-channel PWM driver (I2C servo controller on I2C0, address 0x40)
- 3x MG995 continuous rotation servo motors:
    - Servo 1 (channel 1): Intake door
    - Servo 2 (channel 15): Exit door
    - Servo 3 (channel 14): Reject door
- HX711 + Load cell (weight sensor to confirm bottle insertion)
- 4x20 I2C LCD display (PCF8574 backpack, address 0x27, on I2C1)

AI MODEL
--------
- Model: YOLOv8n (YOLOv8 Nano) - ultralytics built-in pretrained model
- File: yolov8n.pt (auto-downloaded on first run)
- Dataset: COCO (80 classes, using class ID 39 = "bottle")
- Input size: 640x640
- Confidence threshold: 0.75
- Inference: CPU (no GPU required on RPi 5)
- Purpose: Detects whether the object shown to the camera is a bottle.
  This prevents users from scanning a barcode without presenting a real bottle.

A custom NCNN model (best_ncnn_model/) is also available for dual
verification via dual_verification.py, but the production system uses
the built-in YOLOv8n for simplicity and reliability.

WIRING
------
PCA9685 Servo Controller (I2C0):
  RPi5 GPIO1 (Pin 28) --> PCA9685 SCL
  RPi5 GPIO0 (Pin 27) --> PCA9685 SDA
  RPi5 3.3V           --> PCA9685 VCC
  RPi5 GND            --> PCA9685 GND
  External 5-6V PSU   --> PCA9685 V+ (servo power, separate from logic)

  Requires: dtoverlay=i2c0-pi5 in /boot/firmware/config.txt

Servo Motors (connected to PCA9685 PWM channels):
  Servo 1 (intake)  --> PCA9685 Channel 1
  Servo 2 (exit)    --> PCA9685 Channel 15
  Servo 3 (reject)  --> PCA9685 Channel 14

HX711 Load Cell:
  HX711 DOUT  --> RPi5 GPIO5 (Pin 29)
  HX711 SCK   --> RPi5 GPIO6 (Pin 31)
  HX711 VCC   --> RPi5 5V (Pin 2 or 4)
  HX711 GND   --> RPi5 GND

LCD Display (I2C1 - default RPi I2C bus):
  LCD SDA --> RPi5 GPIO2 (Pin 3)
  LCD SCL --> RPi5 GPIO3 (Pin 5)
  LCD VCC --> RPi5 5V
  LCD GND --> RPi5 GND

Barcode Scanner:
  Plug into any USB port via micro-USB cable (HID keyboard device).

DEPENDENCIES
------------
Python packages (install in a venv):
  pip install ultralytics opencv-python evdev flask RPLCD hx711
  pip install adafruit-circuitpython-servokit adafruit-blinka

System packages:
  sudo apt install python3-lgpio

Full list in requirements.txt.

HOW TO RUN
----------
Option 1 - Startup script (recommended):
  chmod +x start_phase1.sh
  ./start_phase1.sh

Option 2 - Manual (two terminals):
  Terminal 1 (portal - needs sudo for port 80 + iptables):
    sudo python3 portal.py

  Terminal 2 (main script - needs sudo for scanner grab):
    sudo python3 main_integrated.py

Both scripts share the SQLite database at /home/raspi/rvm/rvm.db.

Logs:
  Portal:  tail -f /tmp/rvm_portal.log
  Main:    tail -f /tmp/rvm_main_integrated.log


PROGRAM FLOW
------------

  User connects to "P.E.T-O WI-FI" hotspot
  Phone opens captive portal at http://10.42.0.1
              |
              v
  +----------------------------------+
  |  Portal: "Insert Bottles" button |
  |  User taps button               |
  |  Machine locks to user's MAC    |
  +----------------------------------+
              |
              v
  +----------------------------------+
  |  STEP 1: WAIT FOR BARCODE SCAN  |  <-- LCD: "Scan bottle"
  |  (scanner reads EAN-13 barcode) |
  +----------------------------------+
              |
         barcode read
              |
              v
  +----------------------------------+
  |  Check BARCODE_MAP               |
  |  Handles clipped scans          |  -- NO MATCH --> LCD: "Unknown bottle"
  |  (suffix/prefix/substring)      |                  loop back to Step 1
  +----------------------------------+
              |
            MATCH
              |
              v
  +----------------------------------+
  |  STEP 2: AI VERIFICATION        |  <-- LCD: "Verifying..."
  |  Open camera, run YOLOv8n       |      30 second timeout
  |  Looking for COCO class 39      |
  |  (bottle) with conf >= 0.75     |
  +----------------------------------+
              |
        bottle detected?
         /          \
       YES           NO (timeout)
        |              |
        v              v
  +-----------+   +------------------+
  |  STEP 3:  |   | LCD: "No bottle" |
  |  Servo 1  |   | "Try again"      |
  |  opens    |   | loop back         |
  |  (intake) |   +------------------+
  +-----------+
        |
        v
  +----------------------------------+
  |  STEP 4: WEIGHT DETECTION        |  <-- LCD: "Drop bottle now"
  |  HX711 load cell monitors for   |      5 second timeout
  |  weight change (1000 raw units) |
  |  Needs 3 consecutive readings   |
  +----------------------------------+
              |
        weight detected?
         /          \
       YES           NO
        |              |
        v              v
  +-----------+   +------------------+
  |  ACCEPTED |   |  REJECTED        |
  |  +time to |   |  Servo 3 closes  |
  |  user's   |   |  (reject path)   |
  |  account  |   |  Servo 2 opens   |
  |           |   |  (exit)          |
  |  Servo 2  |   |  All close       |
  |  opens    |   +------------------+
  |  (exit)   |          |
  +-----------+          |
        |                |
        v                v
  +----------------------------------+
  |  Servo 1 closes (intake door)   |
  |  LCD: "Scan next bottle"        |
  |  Loop back to Step 1            |
  +----------------------------------+
              |
              v
  User taps "Start WiFi" on portal
  --> iptables allows user's MAC
  --> countdown timer starts
  --> user has internet access


SERVO BEHAVIOR
--------------
All three servos are continuous rotation (MG995 clones), not positional.
They are controlled by setting a speed angle for a timed duration, then
sending a stop angle to halt rotation.

  Servo 1 (Intake door):
    Stop: 91°  |  Open: 130° for 0.3s  |  Close: 60° for 0.3s

  Servo 2 (Exit door):
    Stop: 91°  |  Open: 130° for 0.3s  |  Close: 60° for 0.3s
    Stays open for 5 seconds after accept/reject

  Servo 3 (Reject door):
    Stop: 92°  |  Open: 20° for 0.3s   |  Close: 160° for 0.3s
    Default position: OPEN
    Closes to push rejected items out


LOAD CELL BEHAVIOR
------------------
- HX711 ADC with 128x gain
- Averages 10 samples per reading
- Baseline (tare) taken with 3 separate readings averaged
- Weight change threshold: 1000 raw units
- Requires 3 consecutive readings above threshold (filters noise)
- 5-second timeout window for bottle insertion
- Re-tares after each bottle cycle


REGISTERED BARCODES
-------------------
  4800100123456  -> water_bottle-500mL   (5 min)
  4800014147083  -> water_bottle-350mL   (3 min 30s)
  4800602087937  -> water_bottle-1L      (10 min)
  4800100456789  -> coke_2L              (20 min)
  4801981118502  -> coke_mismo           (3 min 20s)
  8997035600010  -> pocari_350mL         (3 min 30s)
  4801981116270  -> sprite_1.5L          (15 min)
  4801981116171  -> royal_1.5L           (15 min)
  4800049720121  -> natures_spring_1000ml (10 min)

Barcode matching handles clipped scans (11-12 digits) by trying
suffix, prefix, and substring matches against the full 13-digit codes.

To add new bottles:
  1. Scan barcode with test/test_scanner.py to get the exact string
  2. Add to BARCODE_MAP in main_integrated.py
  3. Add to BOTTLE_DISPLAY for LCD name
  4. Add to bottles table in db.py init_db()


WIFI TIME FORMAT
----------------
Time values in the database use a custom format: X.Y
  X = whole minutes
  Y = additional seconds (multiplied by 10)

Examples:
  3.5  = 3 minutes + 50 seconds = 230 seconds
  3.2  = 3 minutes + 20 seconds = 200 seconds
  5    = 5 minutes + 0 seconds  = 300 seconds
  10   = 10 minutes             = 600 seconds
  15   = 15 minutes             = 900 seconds


CODE STRUCTURE
--------------

main_integrated.py  (~985 lines)
  The main hardware controller. Handles:
  - Barcode scanning via evdev (HID keyboard)
  - AI bottle verification via YOLOv8n
  - 3 servo motors via PCA9685 (continuous rotation, timed)
  - HX711 load cell for weight detection
  - 4x20 I2C LCD display
  - Machine state polling from SQLite

portal.py  (~670 lines)
  Flask captive portal server. Handles:
  - User-facing web interface
  - Machine lock/unlock via SQLite
  - WiFi session start/stop
  - iptables MAC allow/revoke
  - Background session monitor (expires users)
  - Captive portal detection endpoints

db.py  (~257 lines)
  Shared SQLite database module. Three tables:
  - users: MAC, accumulated_time, wifi_active, session timestamps
  - bottles: bottle_type, time_minutes
  - machine_state: active_mac, lock_started (single row)

utils.py  (~70 lines)
  Shared utilities:
  - format_time(seconds) -> "MM:SS" string
  - validate_ip_address(ip) -> bool
  - validate_mac_address(mac) -> bool


TESTING UTILITIES
-----------------
All test scripts are in the test/ directory:

Barcode:
  test/portal_test.py          - Portal integration test

Load Cell (HX711):
  test/calibrate_load_cell.py  - Full calibration procedure
  test/test_load_cell.py       - Verify load cell connection
  test/test_load_cell_raw.py   - Raw ADC value readout
  test/test_hx711_quick.py     - Quick connection test
  test/simple_load_cell.py     - Simple weight reading

Servo Motors:
  test/calibrate_stop_angle.py - Find the stop angle for servos 1 & 2
  test/calibrate_servo3_stop.py- Find the stop angle for servo 3
  test/test_open_close.py      - Test door open/close timing
  test/test_continuous_servos.py- Test continuous rotation behavior
  test/test_servo_simple.py    - Basic servo movement test
  test/test_servos.py          - Full servo test suite

AI Detection:
  test/test_yolo_builtin.py    - Test built-in YOLOv8n model
  test/test_yolo_dual.py       - Test dual verification mode
  test/test_yolo_live.py       - Live camera detection test


GRACEFUL DEGRADATION
--------------------
The system runs even without hardware connected:
- No scanner: falls back to manual keyboard input
- No PCA9685/servos: prints simulated OPEN/CLOSE messages
- No HX711/load cell: rejects all items (cannot verify insertion)
- No LCD: runs silently without display output
- No camera: skips AI verification, loops back to scan


DEBUGGING
---------
  # View logs
  tail -f /tmp/rvm_main_integrated.log
  tail -f /tmp/rvm_portal.log

  # View database
  sqlite3 /home/raspi/rvm/rvm.db "SELECT * FROM users;"
  sqlite3 /home/raspi/rvm/rvm.db "SELECT * FROM machine_state;"
  sqlite3 /home/raspi/rvm/rvm.db "SELECT * FROM bottles;"

  # Check iptables rules
  sudo iptables -L FORWARD -v -n | grep MAC

  # Reset database
  rm /home/raspi/rvm/rvm.db
  python3 -c "import db"

  # Check hotspot
  nmcli connection show --active | grep Hotspot

  # Stop everything
  sudo pkill -f portal.py
  pkill -f main_integrated.py
