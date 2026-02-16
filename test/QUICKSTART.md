# RVM Phase 1 - Quick Start Guide

## TL;DR

```bash
# Start everything
./start_phase1.sh

# Or manually:
sudo python3 portal.py &
python3 main_integrated.py &
```

Then on your phone:
1. Connect to "RVM-WiFi"
2. Browse to http://10.42.0.1
3. Tap "Insert Bottles"
4. Scan bottles at the machine
5. Tap "Done - Start WiFi"
6. Enjoy internet! 🎉

---

## What Is This?

Reverse Vending Machine (RVM) that gives WiFi time in exchange for recycling bottles.

**Phase 1 Features:**
- ✅ Barcode scanning + AI verification
- ✅ Time tracking (SQLite database)
- ✅ WiFi portal with countdown timer
- ❌ No servo motors yet (Phase 2)

---

## First Time Setup

### 1. Install Dependencies

```bash
sudo apt update
sudo apt install -y python3-pip iptables sqlite3
pip3 install flask ultralytics opencv-python evdev

# Optional: LCD display
pip3 install RPLCD
```

### 2. Verify Hotspot

```bash
# Check if hotspot exists
nmcli connection show | grep Hotspot

# If not, see docs/PHASE1_SETUP.md for full setup
```

### 3. Verify iptables

```bash
# Check IP forwarding
cat /proc/sys/net/ipv4/ip_forward  # Should be 1

# Check NAT rule
sudo iptables -t nat -L | grep MASQUERADE  # Should exist
```

---

## Running the System

### Option 1: Startup Script (Recommended)

```bash
cd /home/raspi/rvm
./start_phase1.sh
```

This will:
- ✓ Check and start hotspot
- ✓ Enable IP forwarding
- ✓ Stop old processes
- ✓ Start portal server (port 80)
- ✓ Start main script
- ✓ Show status and log locations

### Option 2: Manual Start

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

### Option 3: systemd Services (Auto-start on boot)

See [docs/PHASE1_SETUP.md](docs/PHASE1_SETUP.md#option-3-systemd-services-auto-start-on-boot)

---

## User Flow

1. **Connect to WiFi**
   - SSID: "RVM-WiFi"
   - No password

2. **Open Portal**
   - Browse to: http://10.42.0.1
   - Portal shows welcome screen

3. **Lock Machine**
   - Tap "Insert Bottles 🍾"
   - Machine locks to your phone's MAC address
   - Portal shows "0:00" accumulated time

4. **Scan Bottles**
   - At the machine, scan barcode
   - Show bottle to camera (10 second window)
   - If verified: time is added (e.g., +30 min)
   - LCD shows "Accepted! +30 min"
   - Scan more bottles to accumulate time

5. **Start WiFi**
   - When done, tap "Done - Start WiFi 🚀"
   - Internet access granted immediately
   - Portal shows countdown timer
   - Enjoy browsing!

6. **Time Expires**
   - When countdown hits 0:00
   - Internet access is automatically revoked
   - Can insert more bottles to get more time

---

## Monitoring

### View Logs

```bash
# Portal logs
tail -f /tmp/portal.log

# Main script logs
tail -f /tmp/main.log
```

### Check Database

```bash
# View users
sqlite3 /home/raspi/rvm/rvm.db "SELECT * FROM users;"

# View machine state
sqlite3 /home/raspi/rvm/rvm.db "SELECT * FROM machine_state;"

# View allowed MACs in iptables
sudo iptables -L FORWARD -v -n | grep MAC
```

### Check Processes

```bash
# Portal server
sudo ss -tulpn | grep ':80'

# All Python processes
ps aux | grep python3
```

---

## Stopping the System

```bash
# Stop portal
sudo pkill -f portal.py

# Stop main script
pkill -f main_integrated.py

# Stop hotspot (optional)
sudo nmcli connection down Hotspot
```

---

## Troubleshooting

### Portal not accessible
```bash
# 1. Check if running
sudo ss -tulpn | grep ':80'

# 2. Check hotspot
nmcli connection show --active | grep Hotspot

# 3. Check logs
tail /tmp/portal.log
```

### No internet after clicking "Start WiFi"
```bash
# 1. Check iptables rule was added
sudo iptables -L FORWARD -v -n | grep MAC

# 2. Check IP forwarding
cat /proc/sys/net/ipv4/ip_forward  # Must be 1

# 3. Check NAT
sudo iptables -t nat -L POSTROUTING -v -n | grep MASQUERADE
```

### Barcode scanner not detected
```bash
# List input devices
ls -l /dev/input/by-id/

# Check evdev
python3 -c "import evdev; print(evdev.list_devices())"

# Run main script to see error details
python3 main_integrated.py
```

### Camera not working
```bash
# List cameras
ls -l /dev/video*

# Test camera
python3 -c "import cv2; cap = cv2.VideoCapture(0); print('Camera OK' if cap.isOpened() else 'Camera FAIL')"
```

### Reset Everything (Testing)
```bash
# Stop processes
sudo pkill -f portal.py
pkill -f main_integrated.py

# Clear database
rm /home/raspi/rvm/rvm.db
python3 -c "import db"  # Recreate

# Clear iptables rules (CAREFUL!)
sudo iptables -F FORWARD
sudo iptables -P FORWARD DROP
sudo iptables -A FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT

# Restart
./start_phase1.sh
```

---

## File Overview

| File | Purpose |
|------|---------|
| `db.py` | SQLite database module |
| `portal.py` | Web portal server |
| `main_integrated.py` | Scanning + AI script |
| `start_phase1.sh` | Startup script |
| `rvm.db` | SQLite database (auto-created) |
| `QUICKSTART.md` | This file |
| `PHASE1_SUMMARY.md` | Implementation details |
| `docs/PHASE1_SETUP.md` | Full setup guide |

---

## Bottle Time Values

| Bottle | Barcode | Time |
|--------|---------|------|
| water_bottle-500mL | 4800100123456 | 30 min |
| water_bottle-350mL | 4800014147083 | 10 min |
| water_bottle-1L | 4800602087937 | 45 min |
| coke_2L | 4800100456789 | 75 min |
| coke_mismo | 4801981118502 | 10 min |
| pocari_350mL | 8997035600010 | 10 min |
| sprite_1.5L | 4801981116270 | 60 min |
| royal_1.5L | 4801981116171 | 60 min |
| natures_spring_1000ml | 4800049720121 | 45 min |
| coke_litro | (custom) | 60 min |

Add more barcodes in `main_integrated.py` → `BARCODE_MAP`

---

## Next Steps

- [ ] Test with real barcode scanner and camera
- [ ] Test full user flow end-to-end
- [ ] Set up systemd services for auto-start
- [ ] Update barcodes in BARCODE_MAP (use real bottle barcodes)
- [ ] Phase 2: Add servo motors for intake door

---

## Getting Help

1. Check logs: `/tmp/portal.log` and `/tmp/main.log`
2. Read [PHASE1_SETUP.md](docs/PHASE1_SETUP.md) for detailed troubleshooting
3. Check database: `sqlite3 /home/raspi/rvm/rvm.db`
4. Verify hotspot: `nmcli connection show --active`
5. Check firewall: `sudo iptables -L -v -n`

---

**Phase 1 is ready! 🚀**

Connect your barcode scanner, webcam, and (optional) LCD display, then run `./start_phase1.sh` to begin!
