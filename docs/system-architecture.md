# RVM System Architecture

The P.E.T-O Reverse Vending Machine accepts empty plastic bottles and rewards users with free WiFi time. It runs on a Raspberry Pi 5 acting as both the machine controller and WiFi hotspot.

## Hardware

| Component | Model / Spec | Purpose |
|-----------|-------------|---------|
| Raspberry Pi 5 | 4GB+ RAM | Main controller, WiFi hotspot, AI inference |
| Ethernet cable | Cat5e/Cat6 | Connects RPi to router/modem for internet (WAN) |
| Barcode scanner | MH-ET Live Scanner V3 | Identifies bottle type via EAN-13 barcode (USB HID) |
| USB webcam | Any UVC-compatible | Captures frames for AI bottle verification |
| PCA9685 board | 16-channel, I2C, 0x40 | PWM driver for all three servo motors |
| Servo 1 (intake) | MG995 continuous rotation | Opens/closes the intake door for bottle insertion |
| Servo 2 (exit) | MG995 continuous rotation | Opens/closes the exit door after accepted bottles |
| Servo 3 (reject) | MG995 continuous rotation | Closes to push out rejected items (default: open) |
| HX711 + load cell | 1kg load cell, 128x gain | Detects weight change to confirm bottle was dropped in |
| LCD display | 4x20 I2C (PCF8574, 0x27) | Shows status messages to the user at the machine |
| Power supply | 5V 3A+ for RPi, 5-6V for servos | Separate servo power via PCA9685 V+ terminal |

### I2C Bus Layout

The RPi 5 uses two separate I2C buses to avoid address conflicts:

| Bus | GPIO Pins | Device | Address |
|-----|-----------|--------|---------|
| I2C0 | GPIO0 (SDA), GPIO1 (SCL) | PCA9685 servo driver | 0x40 |
| I2C1 | GPIO2 (SDA), GPIO3 (SCL) | LCD display (PCF8574) | 0x27 |

I2C0 requires `dtoverlay=i2c0-pi5` in `/boot/firmware/config.txt`.

### GPIO Pin Assignment

| GPIO (BCM) | Physical Pin | Connected To |
|------------|-------------|--------------|
| GPIO0 | Pin 27 | PCA9685 SDA |
| GPIO1 | Pin 28 | PCA9685 SCL |
| GPIO2 | Pin 3 | LCD SDA |
| GPIO3 | Pin 5 | LCD SCL |
| GPIO5 | Pin 29 | HX711 DOUT (data) |
| GPIO6 | Pin 31 | HX711 SCK (clock) |

## Software

| Component | Technology | Purpose |
|-----------|-----------|---------|
| NetworkManager (nmcli) | Built into Bookworm | Creates the RPi WiFi hotspot ("P.E.T-O WI-FI") |
| dnsmasq | System service | DHCP server + DNS redirect for captive portal |
| iptables | Kernel netfilter | Blocks/allows internet per MAC address, NAT forwarding |
| Flask | Python web framework | Captive portal page served on port 80 |
| SQLite | Python sqlite3 | Stores users, bottles, machine state (shared between scripts) |
| main_integrated.py | Python | Barcode scanning, AI verification, servos, load cell, LCD |
| portal.py | Python (Flask) | Web portal, WiFi session management, iptables rules |
| db.py | Python | Thread-safe SQLite database module (shared) |
| utils.py | Python | MAC/IP validation, time formatting |
| YOLOv8n | ultralytics (PyTorch) | AI bottle detection model |
| adafruit-servokit | CircuitPython | PCA9685 servo driver interface |
| RPLCD | Python | 4x20 I2C LCD display driver |
| hx711 | Python | HX711 ADC driver for load cell |
| evdev | Python | Linux input device access for barcode scanner |
| OpenCV | Python (cv2) | Camera capture and frame display |

## AI Model Details

| Property | Value |
|----------|-------|
| Model | YOLOv8n (Nano) |
| Framework | Ultralytics / PyTorch |
| File | `yolov8n.pt` (auto-downloaded on first run, ~6MB) |
| Training data | COCO dataset (80 object classes) |
| Target class | Class 39 = "bottle" |
| Input resolution | 640x640 |
| Confidence threshold | 0.75 (75%) |
| Max detections | 1 per frame |
| Inference device | CPU (RPi 5, no GPU) |
| Half precision | Disabled (CPU mode) |

The model is a general-purpose object detector. It is NOT trained specifically on plastic bottles — it uses the COCO "bottle" class which covers water bottles, soda bottles, etc. This works well enough because the barcode scan already identifies the bottle type; the AI just confirms that the user is holding a real bottle (not scanning a barcode from a phone screen or piece of paper).

A custom NCNN model (`best_ncnn_model/`) trained specifically on bottle types is also available. The `dual_verification.py` module can run both models together for higher accuracy, but the production system uses YOLOv8n alone for simplicity.

## User Flow

```
1. User connects phone to "P.E.T-O WI-FI" hotspot
     - Phone detects captive portal and opens http://10.42.0.1
     - Portal shows welcome page with bottle rate table

2. User taps "Insert Bottles" on the portal
     - Portal locks the machine to this user's MAC address
     - If machine is already in use, portal shows "Machine In Use"
     - LCD shows "Session Active — Scan bottle"

3. User scans the barcode of a bottle
     - Scanner sends EAN-13 barcode as keyboard input
     - System matches against BARCODE_MAP (handles partial/clipped scans)
     - If unknown barcode: LCD shows "Unknown Bottle", user tries again
     - If matched: proceed to step 4

4. AI verification — camera opens for 30 seconds
     - YOLOv8n runs inference looking for COCO class 39 (bottle)
     - Live preview window shows bounding box + confidence
     - LCD shows "Verifying... Show bottle to camera"
     - If bottle detected (conf >= 0.75): proceed to step 5
     - If timeout (no bottle seen): LCD shows "No Bottle Detected", retry

5. Intake door opens (servo 1)
     - LCD shows "Drop bottle now"
     - User drops bottle into the machine

6. Load cell checks for weight change (5 second window)
     - HX711 takes baseline reading (tare)
     - Monitors for weight change >= 1000 raw units
     - Requires 3 consecutive readings above threshold (noise filter)

7a. Weight detected — bottle accepted
     - WiFi time added to user's SQLite record
     - Machine lock timeout refreshed
     - Servo 2 opens (exit door) for 5 seconds, then closes
     - LCD shows "Accepted! +X:XX" and total accumulated time

7b. No weight detected — bottle rejected
     - No time is credited
     - Servo 3 closes (pushes item toward reject path)
     - Servo 2 opens (exit) for 5 seconds
     - Both close, servo 3 returns to default open position
     - LCD shows "Item rejected — No weight detected"

8. Intake door closes (servo 1)
     - LCD shows "Scan next bottle"
     - Loop back to step 3

9. When done, user taps "Start WiFi" on the portal
     - Portal releases machine lock
     - Portal activates WiFi session (sets session_started timestamp)
     - iptables rule allows user's MAC address through
     - Countdown timer starts on portal page

10. User browses the internet
      - Portal auto-refreshes every 2 seconds showing remaining time
      - User can tap "Insert More Bottles" to add time mid-session

11. Time expires
      - Background monitor (every 5 seconds) detects expired session
      - iptables rule removed, MAC blocked again
      - User returned to captive portal
      - User can insert more bottles to earn more time
```

## Session Persistence

- If a user disconnects from WiFi and reconnects, their MAC still has remaining time in SQLite
- Sessions expire after 24 hours of inactivity (last_seen not updated)
- Machine lock (who is inserting bottles) auto-releases after 5 minutes of no scans
- WiFi time countdown is calculated from `session_started` timestamp, not decremented

## Database Schema

Three SQLite tables shared between portal.py and main_integrated.py:

**users** — one row per device (identified by MAC address)
| Column | Type | Description |
|--------|------|-------------|
| mac | TEXT PRIMARY KEY | User's MAC address |
| accumulated_time | INTEGER | WiFi time earned (seconds) |
| wifi_active | INTEGER | 1 = WiFi session active, 0 = inactive |
| session_started | TEXT | ISO timestamp when WiFi was activated |
| last_seen | TEXT | ISO timestamp of last portal visit |

**bottles** — preloaded bottle definitions
| Column | Type | Description |
|--------|------|-------------|
| bottle_type | TEXT PRIMARY KEY | Identifier (e.g. "water_bottle-500mL") |
| time_minutes | REAL | WiFi time reward (custom format: X.Y) |

**machine_state** — single-row table (enforced by CHECK constraint)
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Always 1 |
| active_mac | TEXT | MAC of user currently inserting bottles (NULL = idle) |
| lock_started | TEXT | ISO timestamp when machine was locked |

## Bottle Time Table

| Bottle Type | Time Reward |
|-------------|-------------|
| water_bottle-500mL | 5 min |
| water_bottle-350mL | 3 min 30s |
| water_bottle-1L | 10 min |
| coke_2L | 20 min |
| coke_mismo | 3 min 20s |
| pocari_350mL | 3 min 30s |
| sprite_1.5L | 15 min |
| royal_1.5L | 15 min |
| natures_spring_1000ml | 10 min |
| coke_litro | 15 min |

## How the Captive Portal Works

1. RPi connects to a router via ethernet for internet access
2. nmcli creates a WiFi hotspot ("P.E.T-O WI-FI") using the built-in WiFi chip
3. iptables enables NAT (masquerade) to forward hotspot traffic to the ethernet interface
4. iptables blocks all FORWARD traffic by default — only allowed MACs get through
5. dnsmasq assigns IP addresses (10.42.0.x) and redirects DNS queries to the RPi
6. When a phone connects, its captive portal detection triggers (Flask responds to probe URLs like `/generate_204`, `/hotspot-detect.html` with 302 redirects)
7. The portal page is served at `http://10.42.0.1:80`
8. Users are identified by their MAC address (resolved via `ip neigh show`)
9. When a user earns time and taps "Start WiFi", an iptables rule allows their MAC
10. A background thread checks every 5 seconds and removes expired users

## Anti-Abuse Measures

| Attack | Prevention |
|--------|-----------|
| Scanning barcode without a real bottle | AI verification requires showing a real bottle to the camera |
| Showing bottle to camera but not inserting | Load cell detects whether a bottle was actually dropped in |
| Dumping non-bottles into the machine | Servo door only opens after AI confirms a bottle shape |
| Two users using machine simultaneously | Machine lock allows only one active session at a time |
| Stale machine lock blocking others | Auto-releases after 5 minutes of no barcode scans |
| IP address injection in MAC lookup | IP validated with `ipaddress` module before subprocess call |

**Known gap**: MAC address spoofing. A user could change their device's MAC to steal another user's WiFi time. For a community kiosk this is acceptable risk; production deployment should add session tokens or SMS verification.

## LCD Messages

| State | Line 1 | Line 2 | Line 3/4 |
|-------|--------|--------|-----------|
| Idle | "connect to" | "P.E.T.-O WI-FI" | "go to" / "10.42.0.1" |
| Session started | "Session Active" | "MAC: XX:XX:XX" | "Scan bottle" |
| Barcode unknown | "Unknown Bottle" | "Try again" | barcode digits |
| AI verifying | "Verifying..." | bottle volume | "Show bottle to camera" |
| AI verified | "Bottle Verified!" | bottle volume | "Drop bottle now" |
| Weight monitoring | "Drop bottle now" | "Monitoring weight..." | timeout |
| Bottle accepted | bottle volume | "Accepted! +M:SS" | "Total: M:SS" |
| No weight | "No bottle detected" | "Rejecting item..." | |
| Item rejected | "Item rejected" | "No weight detected" | "Scan next bottle" |
| Session ended | "Session Ended" | "Thank you!" | |

## How to Build the Device

### Step 1: Set up the Raspberry Pi
1. Flash Raspberry Pi OS (Bookworm, 64-bit) to an SD card
2. Boot, connect keyboard/monitor, complete first-boot setup
3. Connect ethernet cable to your router (this is the WAN uplink)
4. Enable I2C0 overlay: add `dtoverlay=i2c0-pi5` to `/boot/firmware/config.txt`
5. Reboot

### Step 2: Set up the WiFi hotspot
```bash
# Create hotspot
sudo nmcli connection add type wifi ifname wlan0 con-name Hotspot \
  autoconnect yes ssid "P.E.T-O WI-FI" \
  wifi.mode ap wifi.band bg \
  ipv4.method shared ipv4.addresses 10.42.0.1/24

# Enable IP forwarding
echo 'net.ipv4.ip_forward=1' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Set up iptables (block all, allow portal)
sudo iptables -P FORWARD DROP
sudo iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT
sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE

# Install dnsmasq for DNS redirect
sudo apt install dnsmasq
# Configure to redirect all DNS to 10.42.0.1
```

### Step 3: Wire the hardware
1. Connect the PCA9685 to I2C0 (GPIO0/GPIO1) — see Wiring section above
2. Connect three MG995 servos to PCA9685 channels 1, 14, and 15
3. Provide separate 5-6V power to PCA9685 V+ terminal (do not power servos from RPi)
4. Connect HX711 + load cell to GPIO5 (DOUT) and GPIO6 (SCK)
5. Connect LCD to I2C1 (GPIO2/GPIO3)
6. Plug in the barcode scanner via USB
7. Plug in the webcam via USB

### Step 4: Install software
```bash
cd /home/raspi
git clone <repo-url> rvm
cd rvm
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
sudo apt install python3-lgpio
```

### Step 5: Calibrate hardware
```bash
# Calibrate servo stop angles (prevents jitter when idle)
python3 test/calibrate_stop_angle.py
python3 test/calibrate_servo3_stop.py

# Test door open/close timing
python3 test/test_open_close.py

# Calibrate load cell baseline
python3 test/calibrate_load_cell.py

# Test AI detection
python3 test/test_yolo_builtin.py

# Test barcode scanner
python3 test/test_scanner.py
```

### Step 6: Run the system
```bash
chmod +x start_phase1.sh
./start_phase1.sh
```

Or set up systemd services for auto-start on boot:
- `rvm-main.service` — runs main_integrated.py
- `rvm-portal.service` — runs portal.py (with sudo for port 80)

## Integration (Main Script + Flask)

Both run as separate processes and communicate through SQLite:

- **Flask (portal.py)**: portal UI, machine lock/unlock, WiFi start/stop, iptables rules, session expiry
- **Main script (main_integrated.py)**: barcode scanning, AI verification, servo control, load cell, LCD display
- **SQLite (rvm.db)**: shared state between both processes

Data flow:
1. User taps "Insert Bottles" → Flask sets `machine_state.active_mac` = user's MAC
2. Main script polls `machine_state` every 0.5s, detects the lock
3. User scans bottle → main script verifies with AI → checks weight → writes `+time` to `users.accumulated_time`
4. User taps "Start WiFi" → Flask reads `accumulated_time`, adds iptables rule, sets `wifi_active = 1`
5. Background monitor checks every 5s → removes expired iptables rules, sets `wifi_active = 0`

## Deployment

| Service | File | Port | Requires sudo |
|---------|------|------|--------------|
| Portal | portal.py | 80 | Yes (port 80 + iptables) |
| Main | main_integrated.py | — | Yes (scanner grab + GPIO) |

Both should be run from `/home/raspi/rvm/` with the virtual environment activated.
