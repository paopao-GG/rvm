# RVM Phase 1 Setup Guide

**Phase 1 Implementation:**
- ✅ Barcode scanning
- ✅ AI bottle verification
- ✅ Time allocation via SQLite
- ✅ WiFi portal with session management
- ✅ Countdown timer and expiry
- ❌ Servo motors (Phase 2)
- ❌ Load cell verification (Future)

---

## System Architecture

```
[User Phone] → [RVM-WiFi Hotspot]
                    ↓
    ┌──────────────────────────────┐
    │                              │
[Portal Server]  ←→  [SQLite DB]  ←→  [Main Script]
    │                                      │
[iptables]                          [Barcode + AI]
```

**Components:**
1. **Portal Server** ([portal.py](../portal.py)) - Flask web interface, session management, iptables control
2. **Main Script** ([main_integrated.py](../main_integrated.py)) - Barcode scanning, AI verification, time allocation
3. **SQLite Database** ([db.py](../db.py)) - Shared data store for sessions and bottle types

---

## Prerequisites

### 1. Hardware
- Raspberry Pi 5 with WiFi + Ethernet
- USB Barcode Scanner (MH-ET Live V3 or compatible)
- USB Webcam for AI verification
- Optional: 4x20 I2C LCD display (I2C address 0x27)

### 2. Software Packages

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3 python3-pip python3-venv
sudo apt install -y iptables netfilter-persistent
sudo apt install -y sqlite3

# Python packages
pip3 install flask ultralytics opencv-python evdev

# Optional: LCD support
pip3 install RPLCD
```

### 3. WiFi Hotspot Setup

The hotspot should already be configured from the previous setup. Verify:

```bash
# Check hotspot exists
nmcli connection show | grep Hotspot

# Start hotspot if not running
sudo nmcli connection up Hotspot

# Verify
nmcli device status | grep wlan0
```

Hotspot details:
- **SSID:** RVM-WiFi
- **IP:** 10.42.0.1/24
- **DHCP:** 10.42.0.10 - 10.42.0.254
- **Mode:** Open (no password)

### 4. iptables Firewall

Verify firewall rules are in place:

```bash
# Check IP forwarding
cat /proc/sys/net/ipv4/ip_forward  # Should be 1

# Check NAT
sudo iptables -t nat -L POSTROUTING -v -n | grep MASQUERADE

# Check FORWARD chain
sudo iptables -L FORWARD -v -n
```

If not set up, run:

```bash
# Enable IP forwarding
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Add NAT rule
sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE

# Block by default
sudo iptables -P FORWARD DROP
sudo iptables -A FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT

# Save rules
sudo netfilter-persistent save
```

---

## File Structure

```
/home/raspi/rvm/
├── db.py                    # SQLite database module
├── portal.py                # Portal server (NEW)
├── main_integrated.py       # Main script (NEW)
├── rvm.db                   # SQLite database (auto-created)
├── best_ncnn_model/         # YOLO NCNN model files
├── portal_test.py           # Old test portal (deprecated)
├── main.py                  # Old main script (deprecated)
└── docs/
    ├── PHASE1_SETUP.md      # This file
    ├── PORTAL_SETUP.md      # Old setup guide
    └── system-architecture.md
```

---

## Running Phase 1

### Option 1: Manual Startup (Testing)

**Terminal 1 - Portal Server:**
```bash
cd /home/raspi/rvm
sudo python3 portal.py
```

**Terminal 2 - Main Script:**
```bash
cd /home/raspi/rvm
python3 main_integrated.py
```

### Option 2: Background Processes

```bash
# Start portal in background
sudo python3 /home/raspi/rvm/portal.py > /tmp/portal.log 2>&1 &

# Start main script in background
python3 /home/raspi/rvm/main_integrated.py > /tmp/main.log 2>&1 &

# Monitor logs
tail -f /tmp/portal.log
tail -f /tmp/main.log
```

### Option 3: systemd Services (Auto-start on boot)

**Create portal service:**
```bash
sudo tee /etc/systemd/system/rvm-portal.service > /dev/null <<EOF
[Unit]
Description=RVM Captive Portal
After=NetworkManager.service

[Service]
Type=simple
User=root
WorkingDirectory=/home/raspi/rvm
ExecStart=/usr/bin/python3 /home/raspi/rvm/portal.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

**Create main script service:**
```bash
sudo tee /etc/systemd/system/rvm-main.service > /dev/null <<EOF
[Unit]
Description=RVM Main Script (Scanning and AI)
After=rvm-portal.service

[Service]
Type=simple
User=raspi
WorkingDirectory=/home/raspi/rvm
ExecStart=/usr/bin/python3 /home/raspi/rvm/main_integrated.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

**Enable and start services:**
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start
sudo systemctl enable rvm-portal.service
sudo systemctl enable rvm-main.service

# Start now
sudo systemctl start rvm-portal.service
sudo systemctl start rvm-main.service

# Check status
sudo systemctl status rvm-portal.service
sudo systemctl status rvm-main.service

# View logs
sudo journalctl -u rvm-portal.service -f
sudo journalctl -u rvm-main.service -f
```

---

## User Flow (Phase 1)

### 1. User Connects to WiFi
- Connect phone to "RVM-WiFi"
- Manual navigation to http://10.42.0.1 (auto-detection disabled)

### 2. Lock Machine
- Tap "Insert Bottles 🍾" button
- Machine locks to user's MAC address
- Portal shows "Machine Ready" with 0:00 time
- LCD shows "Session Active - Scan bottle"

### 3. Insert Bottles
- User physically scans barcode at machine
- Main script:
  - Validates barcode
  - Opens camera for 10 seconds
  - AI verifies bottle shape
  - If verified: adds time to user's session in SQLite
  - LCD shows "Accepted! +XX min"
- Portal page shows accumulated time (refresh to see updates)
- User can scan multiple bottles

### 4. Start WiFi
- When done scanning, user taps "Done - Start WiFi 🚀"
- Portal:
  - Releases machine lock
  - Adds iptables rule for user's MAC
  - Starts countdown timer
- User now has internet access!
- Portal page shows countdown (auto-refreshes every 2 seconds)

### 5. Time Expires
- Background thread checks every 60 seconds
- When time runs out:
  - iptables rule removed
  - Session marked inactive
  - User redirected back to portal
- User can insert more bottles to get more time

---

## Database Schema

The SQLite database ([rvm.db](../rvm.db)) contains:

### Table: users
| Column | Type | Description |
|--------|------|-------------|
| mac | TEXT | Primary key - user's MAC address |
| accumulated_time | INTEGER | Seconds of WiFi time earned |
| wifi_active | INTEGER | Boolean: 1 if WiFi active, 0 if not |
| session_started | TEXT | ISO timestamp when WiFi started |
| last_seen | TEXT | ISO timestamp of last activity |

### Table: bottles
| Column | Type | Description |
|--------|------|-------------|
| bottle_type | TEXT | Primary key - bottle identifier |
| time_minutes | INTEGER | Time reward in minutes |

### Table: machine_state
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Always 1 (single row) |
| active_mac | TEXT | MAC address currently inserting bottles |
| lock_started | TEXT | ISO timestamp when machine locked |

---

## Testing

### Quick Test (No Scanner)

If you don't have a barcode scanner:

1. Start both scripts manually
2. Portal: Tap "Insert Bottles"
3. Main script: Type barcode manually when prompted (e.g., "4800100123456")
4. Show a bottle to the webcam
5. After verification, check portal - time should increase
6. Tap "Done - Start WiFi"
7. Test internet access on phone

### Database Queries

```bash
# View all users
sqlite3 /home/raspi/rvm/rvm.db "SELECT * FROM users;"

# View machine state
sqlite3 /home/raspi/rvm/rvm.db "SELECT * FROM machine_state;"

# View bottle types
sqlite3 /home/raspi/rvm/rvm.db "SELECT * FROM bottles;"

# Reset everything (for testing)
sqlite3 /home/raspi/rvm/rvm.db "DELETE FROM users; UPDATE machine_state SET active_mac = NULL, lock_started = NULL;"
```

### Check iptables Rules

```bash
# View allowed MACs
sudo iptables -L FORWARD -v -n | grep MAC

# View specific rule
sudo iptables -L FORWARD -v -n --line-numbers
```

---

## Troubleshooting

### Portal not accessible
```bash
# Check if portal is running
sudo ss -tulpn | grep ':80'

# Check hotspot
nmcli connection show --active | grep Hotspot

# Restart portal
sudo systemctl restart rvm-portal.service
```

### Main script not detecting barcode scanner
```bash
# List input devices
ls -l /dev/input/by-id/

# Check evdev
python3 -c "import evdev; print(evdev.list_devices())"

# Run main script manually to see error
python3 main_integrated.py
```

### Camera not working
```bash
# List video devices
ls -l /dev/video*

# Test camera
python3 -c "import cv2; cap = cv2.VideoCapture(0); print(cap.isOpened())"
```

### Database locked errors
```bash
# Check who's using the database
lsof /home/raspi/rvm/rvm.db

# Reset database (WARNING: deletes all data)
rm /home/raspi/rvm/rvm.db
python3 -c "import db"  # Reinitialize
```

### Time not being added
- Check if machine is locked to the correct MAC
- Check main script logs for verification failures
- Verify bottle type is in BARCODE_MAP and database

### Internet not working after "Start WiFi"
```bash
# Check if iptables rule was added
sudo iptables -L FORWARD -v -n | grep MAC

# Check IP forwarding
cat /proc/sys/net/ipv4/ip_forward

# Check NAT
sudo iptables -t nat -L POSTROUTING -v -n
```

---

## Known Limitations (Phase 1)

1. **No physical intake door** - AI verification happens, but user manually places bottle
2. **No load cell** - Can't detect if bottle was actually inserted after verification
3. **No auto-portal detection** - User must manually navigate to http://10.42.0.1
4. **Manual barcode fallback** - If scanner not detected, requires manual typing
5. **Camera window on main script** - OpenCV window shows on RPi desktop (can disable in headless mode)

---

## Next Steps (Phase 2)

- Add servo motor for intake door
- Integrate door opening after AI verification
- Add physical button on machine (alternative to portal lock)
- Implement HTTP redirect for auto-portal detection
- Add production WSGI server (gunicorn) for portal
- Implement load cell for bottle insertion verification

---

## Files Summary

| File | Purpose | Runs as |
|------|---------|---------|
| [db.py](../db.py) | SQLite database module | Imported by others |
| [portal.py](../portal.py) | Web portal + session management | root (port 80) |
| [main_integrated.py](../main_integrated.py) | Scanning + AI + time allocation | raspi user |

All files use the same SQLite database at `/home/raspi/rvm/rvm.db`.

---

## Support

- Check logs: `sudo journalctl -u rvm-portal.service -u rvm-main.service -f`
- Database inspection: `sqlite3 /home/raspi/rvm/rvm.db`
- Network status: `nmcli device status`
- Firewall rules: `sudo iptables -L -v -n`
