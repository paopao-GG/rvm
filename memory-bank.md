# RVM Captive Portal - Memory Bank

**Last Updated:** 2026-02-15
**Status:** ✅ Production Implementation - Phase 1

---

## Overview

Raspberry Pi 5 captive portal system for RVM (Reverse Vending Machine) project. Users connect to WiFi hotspot, scan bottles with barcode + AI verification to earn internet time.

### Current Implementation
- **WiFi Hotspot:** P.E.T-O WI-FI (open, no password)
- **Portal Server:** Flask app on port 80 with SQLite database, P.E.T-O branding & logo
- **Main Script:** Barcode scanning + YOLO AI verification (NCNN model)
- **Access Control:** MAC-based iptables filtering with time limits (MM:SS format)
- **Hardware:** Barcode scanner (evdev), webcam (cv2), 4x20 I2C LCD display (RPLCD)

---

## System Architecture

```
[Phone] → [P.E.T-O WI-FI Hotspot]
              ↓
         [dnsmasq DHCP]
              ↓
         [Portal Server :80] ←→ [SQLite Database] ←→ [Main Script]
         (P.E.T-O branded)                                 ↓
              ↓                                   [Barcode Scanner + Camera]
     [iptables MAC filter]                                 ↓
              ↓                                   [YOLO AI Verification]
         [NAT → Internet]                                  ↓
                                                    [4x20 I2C LCD Display]
```

**Integration:** Both portal.py and main_integrated.py share the same SQLite database (rvm.db) for session management, machine locking, and time tracking.

---

## Key Components

### 1. WiFi Hotspot (NetworkManager)
**Config:** `/etc/NetworkManager/system-connections/Hotspot.nmconnection`
```ini
[connection]
id=Hotspot
type=wifi
autoconnect=yes

[wifi]
ssid=P.E.T-O WI-FI
mode=ap

[ipv4]
method=shared
address1=10.42.0.1/24

[ipv6]
method=disabled
```

**Commands:**
```bash
# Start hotspot
sudo nmcli connection up Hotspot

# Stop hotspot
sudo nmcli connection down Hotspot

# Check status
nmcli device status | grep wlan0
```

### 2. dnsmasq (via NetworkManager)
**Config:** NetworkManager spawns dnsmasq automatically for "shared" mode

**Settings:**
- Listen address: 10.42.0.1
- DHCP range: 10.42.0.10 - 10.42.0.254
- Lease time: 3600 seconds

**Config directory:** `/etc/NetworkManager/dnsmasq-shared.d/`
- **NOTE:** DNS redirect (`address=/#/10.42.0.1`) was REMOVED to fix browsing issues
- Clients now get real DNS responses

**Check dnsmasq:**
```bash
ps aux | grep dnsmasq
sudo ss -tulpn | grep ':53'
```

### 3. iptables Firewall

**Current Rules:**
```bash
# IP forwarding (enabled)
net.ipv4.ip_forward=1

# NAT - masquerade traffic going out eth0
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE

# FORWARD chain - block by default
iptables -P FORWARD DROP

# Allow established connections
iptables -A FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT

# Allow traffic from RPi itself
iptables -A INPUT -i wlan0 -j ACCEPT
iptables -A OUTPUT -o wlan0 -j ACCEPT

# MAC-based allow rules (added by portal dynamically)
# Example: iptables -I FORWARD 1 -m mac --mac-source XX:XX:XX:XX:XX:XX -j ACCEPT
```

**View rules:**
```bash
# FORWARD chain (shows allowed MACs)
sudo iptables -L FORWARD -v -n

# NAT rules
sudo iptables -t nat -L -v -n

# Save rules (persist across reboots)
sudo netfilter-persistent save
```

### 4. Portal Server (Flask) - Production

**File:** `/home/raspi/rvm/portal.py`

**Features:**
- P.E.T-O branding with logo (peto.jpg)
- WiFi time rate table (100mL to 2000mL bottles)
- MAC address detection via `arp` or `ip neigh`
- iptables integration (add/remove MAC rules)
- SQLite database for persistent sessions
- Machine locking (one user at a time)
- Time tracking and countdown display (MM:SS format)
- Session expiry (24 hours inactive or time runs out)
- Background session monitor thread

**Start portal:**
```bash
sudo python3 portal.py

# Or use startup script:
bash start_phase1.sh
```

**Monitor logs:**
```bash
tail -f /tmp/rvm_portal.log
```

**Key Routes:**
- `/` - Main portal page (shows status, accumulated time, WiFi countdown)
- `/lock_machine` - Claim machine for bottle insertion
- `/start_wifi` - Activate internet after scanning bottles
- `/cancel` - Release machine lock
- `/peto.jpg` - Serves P.E.T-O logo image

**WiFi Time Rates (displayed on portal):**
| Volume | Time |
|--------|------|
| 100mL | 1 min |
| 200mL | 2 min |
| 230mL | 2.3 min |
| 250mL | 2.5 min |
| 280mL | 2.8 min |
| 290mL | 3.2 min |
| 330mL | 3.3 min |
| 350mL | 3.5 min |
| 500mL | 5 min |
| 600mL | 6 min |
| 750mL | 7.5 min |
| 1000mL (1L) | 10 min |
| 1250mL | 12.5 min |
| 1500mL (1.5L) | 15 min |
| 2000mL (2L) | 20 min |

**Time Format:** X.Y where X = whole minutes, Y = additional seconds
- Example: 3.2 = 3 minutes + 20 seconds = 3:20 display

### 5. Main Script (Bottle Scanning & AI)

**File:** `/home/raspi/rvm/main_integrated.py`

**Features:**
- Barcode scanning via evdev (USB barcode scanner)
- YOLO AI verification using NCNN model (optimized for RPi 5)
- Camera integration with threading (non-blocking)
- 4x20 I2C LCD display for user feedback (volume-only labels)
- SQLite integration for time allocation
- Time display in MM:SS format

**Start main script:**
```bash
python3 main_integrated.py

# Or use startup script:
bash start_phase1.sh
```

**Monitor logs:**
```bash
tail -f /tmp/rvm_main_integrated.log
```

**Flow:**
1. Wait for user to lock machine via portal
2. User scans barcode at machine
3. Camera opens, AI verifies bottle (10 second window)
4. If verified, time added to user's accumulated time
5. Repeat until user taps "Done" on portal
6. User starts WiFi session to activate internet

**NCNN Model:**
- **Path:** `/home/raspi/rvm/best_ncnn_model/`
- **Files:** `model.ncnn.bin`, `model.ncnn.param`, `metadata.yaml`
- **Classes:** water_bottle-500mL, water_bottle-350mL, water_bottle-1L, coke_litro, coke_mismo
- **Confidence:** 0.50 minimum for verification

**Important Fix Applied (2026-02-15):**
- Installed `ncnn` Python package (version 1.0.20260114)
- Required for Ultralytics to load NCNN models
- Fixed "No module named 'ncnn'" error

### 6. Database (SQLite)

**File:** `/home/raspi/rvm/db.py`

**Database:** `/home/raspi/rvm/rvm.db`

**Tables:**
- `users` - MAC, accumulated_time (seconds), wifi_active, session_started, last_seen
- `bottles` - bottle_type, time_minutes (format: X.Y where X=min, Y=sec)
- `machine_state` - active_mac, lock_started (one user at a time)

**Bottle Time Values (X.Y format: X minutes + Y seconds):**
- coke_mismo: 3.2 → 3:20 (200 seconds)
- water_bottle-350mL: 3.5 → 3:30 (210 seconds)
- pocari_350mL: 3.5 → 3:30 (210 seconds)
- water_bottle-500mL: 5.0 → 5:00 (300 seconds)
- water_bottle-1L: 10.0 → 10:00 (600 seconds)
- natures_spring_1000ml: 10.0 → 10:00 (600 seconds)
- sprite_1.5L: 15.0 → 15:00 (900 seconds)
- royal_1.5L: 15.0 → 15:00 (900 seconds)
- coke_litro: 15.0 → 15:00 (900 seconds)
- coke_2L: 20.0 → 20:00 (1200 seconds)

**Key Functions:**
- `lock_machine(mac)` - Claim machine (5-minute timeout if stale)
- `add_time_to_user(mac, minutes)` - Add earned time (converts X.Y to seconds)
- `start_wifi_session(mac)` - Activate internet countdown
- `get_remaining_time(mac)` - Calculate time left (returns seconds)
- `get_expired_users()` - Find sessions to revoke (24hr or time=0)

---

## Network Configuration

### IP Addresses
- **Hotspot (wlan0):** 10.42.0.1/24 (constant - never changes regardless of upstream network)
- **Ethernet (eth0):** 192.168.137.2/24 (static IP for laptop internet sharing)
- **Gateway:** 192.168.137.1 (via eth0, laptop's shared internet)

**Note:** The hotspot IP (10.42.0.1) is managed by NetworkManager and remains constant even when connecting to different routers or networks via Ethernet. This ensures users always access the portal at the same address.

### Routing
```bash
# View routes
ip route show

# Default route via eth0
default via 192.168.137.1 dev eth0
```

### Connected Clients
```bash
# View connected devices
ip neigh show dev wlan0

# Example output:
# 10.42.0.18 lladdr c2:42:01:6e:9f:63 REACHABLE
```

---

## Startup Sequence

### Production Startup (Recommended)
Use the startup script:
```bash
bash /home/raspi/rvm/start_phase1.sh
```

**What it does:**
1. Checks if hotspot is running, starts if needed
2. Enables IP forwarding (sysctl)
3. Stops old portal.py and main_integrated.py processes
4. Starts portal.py as root (background, logs to /tmp/portal.log)
5. Starts main_integrated.py (background, logs to /tmp/main.log)
6. Verifies portal is listening on port 80
7. Shows status and PIDs

**Logs:**
```bash
# Portal logs (detailed debug level)
tail -f /tmp/rvm_portal.log

# Main script logs (detailed debug level)
tail -f /tmp/rvm_main_integrated.log

# Startup script logs (stdout)
tail -f /tmp/portal.log
tail -f /tmp/main.log
```

### Manual Startup (Alternative)
```bash
# 1. Start hotspot (usually auto-starts)
sudo nmcli connection up Hotspot

# 2. Enable IP forwarding
sudo sysctl -w net.ipv4.ip_forward=1

# 3. Start portal server
sudo python3 /home/raspi/rvm/portal.py &

# 4. Start main script
python3 /home/raspi/rvm/main_integrated.py &
```

### Future: Automatic Startup (TODO)
Create systemd services for both portal and main script:
```bash
# /etc/systemd/system/rvm-portal.service
[Unit]
Description=RVM Captive Portal
After=NetworkManager.service

[Service]
Type=simple
User=root
WorkingDirectory=/home/raspi/rvm
ExecStart=/usr/bin/python3 /home/raspi/rvm/portal.py
Restart=always

[Install]
WantedBy=multi-user.target

# /etc/systemd/system/rvm-main.service
[Unit]
Description=RVM Bottle Scanning Script
After=rvm-portal.service

[Service]
Type=simple
User=raspi
WorkingDirectory=/home/raspi/rvm
ExecStart=/usr/bin/python3 /home/raspi/rvm/main_integrated.py
Restart=always
Environment="DISPLAY=:0"

[Install]
WantedBy=multi-user.target
```

---

## Production Workflow

### Complete User Flow
1. **Connect:** User connects phone to "P.E.T-O WI-FI" hotspot
2. **Portal:** Phone opens portal at http://10.42.0.1 (or manual navigation)
   - Portal displays P.E.T-O logo and WiFi time rate table
3. **Lock Machine:** User taps "Insert Bottles 🍾" button on portal
   - Portal locks machine to user's MAC address
   - Other users see "Machine In Use" message
4. **Scan Bottle:** User goes to RVM machine
   - LCD shows: "Session Active - Scan bottle"
   - User scans barcode with barcode scanner
5. **AI Verify:** Camera opens automatically
   - 10-second window to show bottle to camera
   - YOLO AI detects bottle type
   - LCD shows: "Verifying... 500mL" (volume only)
   - If verified: time added to user's accumulated time
   - LCD shows: "500mL / Accepted! +5:00 / Total: 10:00" (MM:SS format)
   - If not: "No Bottle Detected - Try again"
6. **Repeat:** User can scan more bottles to accumulate more time
7. **Done:** User returns to portal, taps "Done - Start WiFi 🚀"
   - Portal shows: "You have 10:00 accumulated" (MM:SS format)
   - Machine lock released (immediately available for next user)
   - WiFi session activated (countdown starts in MM:SS format)
   - iptables rule added for user's MAC
8. **Internet:** User now has internet access for accumulated time
   - Portal shows countdown timer: "10:00 → 9:59 → 9:58..." (auto-refreshes every 2 seconds)
   - Access automatically revoked when time expires

### Testing Workflow (Legacy portal_test.py)

1. Connect to "P.E.T-O WI-FI"
2. Open browser, go to http://10.42.0.1
3. See portal page showing "❌ No Internet Access"
4. Click "Insert Bottle (Test)"
5. Portal logs show: `✅ Allowed MAC: XX:XX:XX:XX:XX:XX`
6. Internet access works!
7. Click "Revoke Access (Test)" to remove access

### Verification Commands
```bash
# Check if hotspot is running
nmcli connection show --active | grep Hotspot

# Check connected clients
ip neigh show dev wlan0

# Check which MACs are allowed
sudo iptables -L FORWARD -v -n | grep MAC

# Test internet from RPi
ping -c 2 8.8.8.8

# Check portal server
sudo ss -tulpn | grep ':80'
```

---

## Troubleshooting

### Portal doesn't auto-open
**Cause:** DNS redirect removed to fix browsing issues

**Solution:** Clients must manually browse to http://10.42.0.1

**Future Fix:** Add iptables HTTP redirect for non-allowed clients

### Internet not working after clicking button
**Check:**
```bash
# 1. Was MAC rule added?
sudo iptables -L FORWARD -v -n | grep MAC

# 2. Is IP forwarding enabled?
cat /proc/sys/net/ipv4/ip_forward  # Should be 1

# 3. Is NAT working?
sudo iptables -t nat -L POSTROUTING -v -n | grep MASQUERADE

# 4. Can RPi reach internet?
ping -c 2 8.8.8.8
```

### dnsmasq conflicts
**Symptom:** "Address already in use" on port 53

**Cause:** Both systemd dnsmasq and NetworkManager dnsmasq trying to run

**Solution:**
```bash
# Stop systemd dnsmasq
sudo systemctl stop dnsmasq
sudo systemctl disable dnsmasq

# Let NetworkManager handle it
```

### Hotspot won't start
**Symptom:** "IP configuration could not be reserved"

**Causes:**
1. wlan0 connected to another WiFi network
2. dnsmasq conflict (see above)

**Solutions:**
```bash
# Disconnect wlan0
sudo nmcli device disconnect wlan0

# Restart NetworkManager
sudo systemctl restart NetworkManager

# Try again
sudo nmcli connection up Hotspot
```

### NCNN Model Error
**Symptom:** `ModuleNotFoundError: No module named 'ncnn'`

**Cause:** NCNN Python bindings not installed

**Solution:**
```bash
pip install --break-system-packages ncnn
```

**Verification:**
```bash
python3 -c "import ncnn; print(ncnn.__version__)"
# Should print: 20260114 (or similar date-based version)
```

### AI Verification Timeout
**Symptom:** "AI verification timeout - no bottle detected" even with bottle visible

**Possible Causes:**
1. Camera not capturing bottle properly
2. NCNN model confidence threshold too high (0.50)
3. Wrong bottle type (not in trained classes)
4. Lighting issues

**Troubleshooting:**
```bash
# Check camera feed (should show OpenCV window during verification)
# Window title: "RVM - Bottle Detection"

# Check model classes in main_integrated.py:
# CLASS_NAMES = ["coke_litro", "coke_mismo", "water_bottle-1L",
#                "water_bottle-350mL", "water_bottle-500mL"]

# Lower confidence threshold if needed (edit main_integrated.py):
# VERIFY_CONF = 0.30  # Instead of 0.50
```

### Barcode Scanner Not Working
**Symptom:** "WARNING: evdev not installed — barcode scanner disabled"

**Solution:**
```bash
pip install --break-system-packages evdev
```

**Check scanner is detected:**
```bash
ls -la /dev/input/by-id/ | grep -i barcode
# Should show a device like: usb-xxx-Barcode_Scanner-event-kbd
```

### LCD Display Not Working
**Symptom:** "WARNING: RPLCD not installed — LCD disabled"

**Solution:**
```bash
pip install --break-system-packages RPLCD
```

**Note:** LCD is optional, system falls back to console output if not available

### I2C LCD Setup
**Symptom:** `Error: Could not open file '/dev/i2c-1'`

**Solution - Enable I2C:**
```bash
# Enable I2C interface
sudo raspi-config nonint do_i2c 0

# Add user to i2c group
sudo usermod -a -G i2c raspi

# Reboot or re-login for group to take effect
```

**Hardware Connection (4x20 I2C LCD):**
- VCC → Pin 2 or 4 (5V)
- GND → Pin 6 (Ground)
- SDA → Pin 3 (GPIO 2 - I2C SDA)
- SCL → Pin 5 (GPIO 3 - I2C SCL)

**Verify I2C is working:**
```bash
# Detect I2C devices (should show 0x27 or 0x3f)
i2cdetect -y 1

# Test LCD directly
python3 << 'EOF'
from RPLCD.i2c import CharLCD
lcd = CharLCD('PCF8574', 0x27, cols=20, rows=4)
lcd.clear()
lcd.write_string("P.E.T-O Ready")
print("LCD working!")
EOF
```

**LCD Display Messages:**
- Startup: "P.E.T-O Ready / Waiting for user..."
- Idle/Ready: "connect to / P.E.T.-O WI-FI / go to / 10.42.0.1" (WiFi connection instructions)
- Active: "Session Active / MAC: XX:XX:XX:XX / / Scan bottle"
- Verifying: "Verifying... / 500mL / / Show bottle to camera"
- Accepted: "500mL / Accepted! +5:00 / / Total: 10:00"
- Volume labels only (500mL, 1L, 2L, etc.) - no internal bottle type names

---

## Important Files

```
/home/raspi/rvm/
├── portal.py                   # Production Flask portal server (P.E.T-O branded)
├── main_integrated.py          # Production barcode + AI script
├── db.py                       # SQLite database module (shared)
├── utils.py                    # Shared utilities (format_time, validate_ip, validate_mac)
├── rvm.db                      # SQLite database (runtime)
├── peto.jpg                    # P.E.T-O logo image (392KB)
├── SECURITY.md                 # Security documentation (MAC spoofing, vulnerabilities)
├── start_phase1.sh             # Startup script (both portal + main)
├── requirements.txt            # Python dependencies
├── best_ncnn_model/            # YOLO NCNN model directory
│   ├── model.ncnn.bin          # Model weights (109MB)
│   ├── model.ncnn.param        # Model structure
│   └── metadata.yaml           # Model metadata
├── portal_test.py              # Test portal (legacy)
├── docs/
│   ├── PORTAL_SETUP.md         # Original setup guide
│   └── system-architecture.md  # Full architecture doc
└── memory-bank.md              # This file

/tmp/
├── rvm_portal.log              # Portal server logs (debug level)
├── rvm_main_integrated.log     # Main script logs (debug level)
└── rvm.db (symlink)            # Database location

/etc/NetworkManager/
├── system-connections/
│   └── Hotspot.nmconnection    # WiFi hotspot config
├── conf.d/
│   └── no-dnsmasq.conf         # Disable NM's global dnsmasq
└── dnsmasq-shared.d/           # Per-connection dnsmasq configs
    └── (empty - DNS redirect removed)

/etc/
├── sysctl.conf                 # IP forwarding config
└── iptables/
    └── rules.v4                # Saved iptables rules
```

---

## Known Issues & Limitations

### Current Issues (Phase 1)
1. **No auto-portal detection:** Removed DNS redirect, so phones don't auto-open portal
   - Users must manually navigate to http://10.42.0.1
2. **Manual startup:** Portal and main script started via bash script, not systemd
3. **No servo motors:** Phase 1 focuses on verification only (no physical bottle handling)
4. **No load cell:** Cannot verify actual bottle insertion (anti-abuse relies on AI only)
5. **Camera window required:** OpenCV requires X11/display for cv2.imshow (runs in console with display)

### Completed (Production Features)
✅ **P.E.T-O branding:** Logo, custom WiFi name, rate table on portal
✅ **Time format:** MM:SS display format (X.Y → X min + Y sec, e.g., 3.2 = 3:20)
✅ **SQLite database:** Sessions persist across restarts
✅ **Time limits:** Sessions expire after time runs out or 24 hours inactive
✅ **Background monitor:** Auto-revokes expired sessions every 5 seconds (fast expiration detection)
✅ **Machine locking:** One user at a time, immediate release after WiFi start, 5-minute stale timeout
✅ **Barcode integration:** evdev-based barcode scanner with fuzzy matching (11-13 char acceptance)
✅ **AI verification:** YOLO NCNN model for bottle detection (RPi 5 optimized)
✅ **4x20 I2C LCD display:** Real-time feedback with volume-only labels (500mL, 1L, etc.)
✅ **I2C setup:** Enabled interface, user permissions, address 0x27
✅ **Comprehensive logging:** Debug-level logs for both portal and main script
✅ **Volume display:** Clean labels on LCD (500mL instead of water_bottle-500mL)
✅ **Code quality:** DRY compliance, type hints, shared utils.py, security documentation
✅ **LCD responsiveness:** 0.2s polling rate (5x faster than original 1s)
✅ **WiFi instructions on LCD:** Initial display shows connection info (10.42.0.1 gateway)
✅ **Fuzzy barcode matching:** Handles clipped barcodes (suffix/prefix/substring matching)

### Planned Improvements (Phase 2)
1. **HTTP redirect:** Use iptables to redirect port 80 for non-allowed clients
2. **Systemd service:** Auto-start portal and main script on boot
3. **Servo motors:** Physical bottle handling (intake door)
4. **Load cell:** Weight verification for anti-abuse
5. **Production server:** Replace Flask dev server with gunicorn/nginx
6. **Headless mode:** Run AI verification without cv2.imshow window

---

## Python Dependencies

**File:** `/home/raspi/rvm/requirements.txt`

**Install all dependencies:**
```bash
pip install --break-system-packages -r requirements.txt
```

**Required Packages:**
- `ultralytics==8.4.12` - YOLO object detection framework
- `opencv-python==4.13.0.92` - Computer vision and camera handling
- `evdev==1.9.3` - Barcode scanner input device handling
- `gpiozero==2.0.1` - GPIO control (future servo motors)
- `numpy==2.4.2` - Array operations (dependency for ultralytics)
- `ncnn==1.0.20260114` - **CRITICAL:** NCNN backend for Ultralytics (ARM-optimized)
- `RPLCD` - I2C LCD display library (4x20 character display)

**System Dependencies:**
- Flask (for portal.py) - `pip install --break-system-packages flask`
- sqlite3 (built-in with Python)
- NetworkManager (pre-installed on Bookworm)
- dnsmasq (handled by NetworkManager)
- iptables (pre-installed on Raspberry Pi OS)

**Important Notes:**
- Using `--break-system-packages` because no venv (global install)
- `ncnn` package MUST be installed for NCNN model to work
- `RPLCD` optional if running without LCD display (fallback to console)
- `evdev` optional if running without barcode scanner (manual input mode)

---

## Related Documentation

- [PORTAL_SETUP.md](docs/PORTAL_SETUP.md) - Original setup guide
- Portal test server: `portal_test.py` (has inline documentation)

---

## Quick Reference

### Start Everything (Production)
```bash
# Use startup script (recommended)
bash /home/raspi/rvm/start_phase1.sh

# Or manually:
sudo nmcli connection up Hotspot
sudo python3 /home/raspi/rvm/portal.py &
python3 /home/raspi/rvm/main_integrated.py &
```

### Stop Everything
```bash
# Stop both scripts
sudo pkill -f portal.py
pkill -f main_integrated.py

# Stop hotspot (optional)
sudo nmcli connection down Hotspot
```

### Restart Everything
```bash
# Quick restart
sudo pkill -f portal.py
pkill -f main_integrated.py
sleep 2
bash /home/raspi/rvm/start_phase1.sh
```

### View Status
```bash
# Hotspot status
nmcli connection show --active | grep Hotspot

# Connected clients
ip neigh show dev wlan0

# Allowed MACs (active WiFi sessions)
sudo iptables -L FORWARD -v -n | grep MAC

# Portal server running?
sudo ss -tulpn | grep ':80'

# Check processes
ps aux | grep -E '(portal|main_integrated)' | grep -v grep
```

### View Logs
```bash
# Portal logs (debug level)
tail -f /tmp/rvm_portal.log

# Main script logs (debug level)
tail -f /tmp/rvm_main_integrated.log

# Follow both (split terminal)
tail -f /tmp/rvm_portal.log | grep -E '(INFO|WARNING|ERROR)' &
tail -f /tmp/rvm_main_integrated.log | grep -E '(INFO|WARNING|ERROR)'
```

### Database Inspection
```bash
# View all users
sqlite3 /home/raspi/rvm/rvm.db "SELECT * FROM users;"

# View machine state
sqlite3 /home/raspi/rvm/rvm.db "SELECT * FROM machine_state;"

# View bottle types
sqlite3 /home/raspi/rvm/rvm.db "SELECT * FROM bottles ORDER BY time_minutes DESC;"

# Check active WiFi sessions
sqlite3 /home/raspi/rvm/rvm.db "SELECT mac, accumulated_time/60 as minutes, wifi_active FROM users WHERE wifi_active=1;"
```

---

## Session Notes

**2026-02-16 (Latest - Code Quality, Bug Fixes & LCD Improvements):**
- ✅ **Network configuration:** Switched from WiFi to Ethernet for upstream internet access
  - Configured static IP on eth0: 192.168.137.2/24 (laptop internet sharing)
  - Hotspot IP (10.42.0.1) remains constant regardless of upstream network
  - Confirmed hotspot gateway is always 10.42.0.1 even when connected to different routers
- ✅ **Code quality improvements (Bob review):**
  - Created utils.py with shared utilities (format_time, validate_ip_address, validate_mac_address)
  - Fixed all DRY violations in main_integrated.py and portal.py
  - Removed dead code: HX711 imports, SERVO2 config, duplicate print statements
  - Added type hints to all functions and classes
  - Created SECURITY.md documenting MAC spoofing vulnerability
- ✅ **Bug fix #1: LCD stuck on "Session Active"**
  - Problem: After clicking "Done", LCD didn't update back to ready screen
  - Root cause: Barcode timeout of 1 second meant machine state only checked once per second
  - Solution: Reduced barcode timeout from 1s to 0.2s (5x faster polling = every 200ms)
- ✅ **Bug fix #2: Barcode scanner clipping digits**
  - Problem: Scanner clips 1-2 digits from start/end (e.g., 4801981118502 → 80198111850)
  - Solution: Created find_barcode_match() with fuzzy matching
    - Exact match first (13 digits)
    - Suffix match (barcode ends with scanned digits)
    - Prefix match (barcode starts with scanned digits)
    - Substring match (scanned digits found anywhere)
  - Updated validation to accept 11-13 character barcodes instead of 8+
- ✅ **Bug fix #3: Internet revocation delay (55 seconds)**
  - Problem: After time expires, users still had internet for 55+ seconds
  - Root cause: Session monitor using get_expired_users() too slow, 60s interval
  - Solution: Rewrote monitor to directly query active users every 5 seconds
    - Changed from 60s intervals to 5s intervals
    - Direct query instead of complex get_expired_users() logic
    - Internet now revoked within 5 seconds of expiration
- ✅ **LCD code refactoring (Bob review):**
  - Fixed DRY violations: 5 repeated "Session Active" display calls
  - Created 20+ LCD message constants (LCD_MSG_READY, LCD_MSG_SESSION_ACTIVE, etc.)
  - Created 3 LCD helper functions:
    - show_session_active(lcd, mac) - Display session active with MAC
    - show_ready_screen(lcd) - Display WiFi connection instructions
    - show_session_ended(lcd) - Display session ended message
  - Updated all lcd.display() calls to use named parameters
  - Removed useless logger fallback and redundant clear() method
- ✅ **LCD initial display update:**
  - Changed from: "Ready / Tap 'Insert Bottles' / on your phone"
  - Changed to: "connect to / P.E.T.-O WI-FI / go to / 10.42.0.1"
  - Users now see WiFi connection instructions immediately on LCD
  - Added 4 new constants: LCD_MSG_CONNECT_TO, LCD_MSG_WIFI_NAME, LCD_MSG_GO_TO, LCD_MSG_GATEWAY_IP
- ✅ **Performance improvements:**
  - LCD refresh rate: 1s → 0.2s (5x faster)
  - Session monitor: 60s → 5s intervals (12x faster expiration detection)
  - Barcode acceptance: exact match only → fuzzy matching (more reliable)

**2026-02-15 (P.E.T-O Branding & Time Format Update):**
- ✅ **P.E.T-O branding:** Changed WiFi name to "P.E.T-O WI-FI", added peto.jpg logo to portal
- ✅ **Rate table:** Added comprehensive WiFi time rate table on portal (100mL to 2000mL)
- ✅ **Bottle times updated:** New time values with X.Y format (3.2 = 3 min + 20 sec)
  - coke_mismo: 3.2 → 3:20 (200 seconds)
  - water_bottle-350mL: 3.5 → 3:30 (210 seconds)
  - All other bottles updated to match rate table
- ✅ **Time display format:** Changed from whole minutes to MM:SS format everywhere
  - Portal: "You have 3:20 accumulated" instead of "3 minutes"
  - LCD: "Accepted! +3:20" and "Total: 10:00" instead of minute-only display
  - WiFi countdown: "10:00 → 9:59 → 9:58..." with MM:SS format
- ✅ **Time conversion logic:** Updated db.py add_time_to_user() to properly convert X.Y format
  - Integer part = whole minutes (× 60)
  - Decimal part = additional seconds (× 100)
  - Example: 3.2 → (3 × 60) + (0.2 × 100) = 180 + 20 = 200 seconds
- ✅ **LCD messages:** Updated to show "P.E.T-O Ready" and volume-only labels
  - "500mL" instead of "water_bottle-500mL"
  - "1L" instead of "water_bottle-1L"
  - Added BOTTLE_DISPLAY mapping dictionary
- ✅ **I2C LCD setup:** Enabled I2C interface, installed RPLCD, configured permissions
  - Address: 0x27 (PCF8574)
  - Connection: SDA→Pin 3, SCL→Pin 5
  - User added to i2c group
- ✅ **Machine availability:** Confirmed machine lock releases immediately after WiFi start

**2026-02-15 (Earlier):**
- ✅ **NCNN fix:** Installed ncnn Python package (v1.0.20260114) to fix "No module named 'ncnn'" error
- ✅ **Requirements updated:** Added ncnn and RPLCD to requirements.txt
- ✅ **Production logging:** Added comprehensive debug logging to portal.py and main_integrated.py
  - Portal logs: /tmp/rvm_portal.log (machine locks, WiFi sessions, iptables, expirations)
  - Main logs: /tmp/rvm_main_integrated.log (barcode scans, AI verification timing, time additions)
- ✅ **Model verified:** NCNN model at /home/raspi/rvm/best_ncnn_model/ has correct structure
- ✅ **Ready for testing:** Both portal.py and main_integrated.py should now run without errors

**2026-02-15 (Earlier):**
- ✅ Initial captive portal test setup completed
- ✅ Fixed dnsmasq conflict (disabled systemd dnsmasq)
- ✅ Fixed portal iptables commands (removed redundant sudo)
- ✅ Removed DNS redirect to fix browsing issues
- ✅ Tested successfully with phone (MAC: c2:42:01:6e:9f:63)
- ✅ Production implementation: portal.py, main_integrated.py, db.py
- ✅ SQLite database integration completed
- ✅ Machine locking mechanism implemented
- ⚠️ Portal auto-detection disabled (manual navigation to http://10.42.0.1 required)

**Known Working Configuration:**
- Raspberry Pi 5 (Bookworm)
- Python 3.13
- YOLO Ultralytics with NCNN backend (ncnn v1.0.20260114)
- NetworkManager hotspot: "P.E.T-O WI-FI" (open, no password)
- iptables MAC-based filtering
- SQLite database for session persistence
- 4x20 I2C LCD at address 0x27 (PCF8574)
- Time format: X.Y (X minutes + Y seconds) → MM:SS display

**Current Bottle Times:**
- 280mL (coke_mismo): 3:20
- 350mL (water/pocari): 3:30
- 500mL (water): 5:00
- 1L (water/natures spring): 10:00
- 1.5L (sprite/royal): 15:00
- 2L (coke): 20:00

**Next Steps:**
1. ✅ Test end-to-end flow (connect → lock → scan → AI verify → start WiFi)
2. ✅ Verify NCNN model loads without errors
3. ✅ Test barcode scanner integration
4. ✅ Test LCD display feedback with volume labels
5. Monitor logs for any issues during production use
6. Consider systemd service setup for auto-start
7. Test time accuracy (verify 3:20 displays and counts down correctly)
8. Verify machine availability after WiFi start for next user
