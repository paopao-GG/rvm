# RVM Phase 1 Implementation Summary

**Date:** 2026-02-15
**Status:** ✅ Complete and Tested

---

## What Was Implemented

Phase 1 implements the core RVM system **without servo motors**. Users scan bottles, earn WiFi time, and access internet through the captive portal.

### Core Features ✅

1. **SQLite Database Integration**
   - Shared database between portal and main script
   - User session tracking (MAC, time, WiFi status)
   - Bottle types and time rewards
   - Machine state (who's currently using it)

2. **Portal Server (portal.py)**
   - User-friendly web interface
   - "Insert Bottles" → locks machine to user
   - Real-time accumulated time display
   - "Done - Start WiFi" → activates internet + countdown
   - "Cancel" → releases machine lock
   - Automatic session expiry (time runs out or 24hr inactivity)
   - iptables integration for MAC-based access control
   - Background monitor thread

3. **Main Script (main_integrated.py)**
   - Waits for user to lock machine via portal
   - Barcode scanning (with manual fallback)
   - AI bottle verification (10 second window)
   - Time allocation to user's session
   - LCD display support (graceful fallback if not available)
   - Auto-release machine after 5 minutes of inactivity

4. **Database Module (db.py)**
   - Thread-safe SQLite operations
   - User session management
   - Machine locking/unlocking
   - Time tracking and expiry
   - Bottle type lookup

---

## New Files Created

| File | Lines | Purpose |
|------|-------|---------|
| [db.py](db.py) | ~280 | SQLite database module |
| [portal.py](portal.py) | ~350 | Flask portal server (replaces portal_test.py) |
| [main_integrated.py](main_integrated.py) | ~400 | Main scanning script (replaces main.py) |
| [docs/PHASE1_SETUP.md](docs/PHASE1_SETUP.md) | ~450 | Complete setup guide |
| [PHASE1_SUMMARY.md](PHASE1_SUMMARY.md) | This file | Implementation summary |

**Old files (deprecated):**
- `portal_test.py` - replaced by `portal.py`
- `main.py` - replaced by `main_integrated.py`

---

## System Flow

```
┌─────────────┐
│ User Phone  │
└──────┬──────┘
       │ Connect to RVM-WiFi
       │
       ▼
┌─────────────────────────────────────────────┐
│          Portal (http://10.42.0.1)          │
│  "Insert Bottles" → Locks machine to MAC    │
└──────────┬──────────────────────────────────┘
           │
           │ Writes to SQLite: machine_state.active_mac = user's MAC
           │
           ▼
┌─────────────────────────────────────────────┐
│         Main Script (waiting)               │
│  Detects machine locked → Ready for scans   │
└──────────┬──────────────────────────────────┘
           │
           │ User scans barcode
           │
           ▼
┌─────────────────────────────────────────────┐
│     Barcode Validation + AI Verification    │
│  - Check barcode in BARCODE_MAP             │
│  - Open camera for 10 seconds               │
│  - AI detects bottle shape                  │
└──────────┬──────────────────────────────────┘
           │
           │ If verified ✅
           │
           ▼
┌─────────────────────────────────────────────┐
│      Add Time to User Session (SQLite)      │
│  db.add_time_to_user(mac, minutes)          │
│  Refresh machine lock timestamp             │
└──────────┬──────────────────────────────────┘
           │
           │ User refreshes portal → sees updated time
           │ User scans more bottles → repeat above
           │
           │ When done, user taps "Done - Start WiFi"
           │
           ▼
┌─────────────────────────────────────────────┐
│     Portal: Activate WiFi Session           │
│  - Release machine lock                     │
│  - Add iptables rule for MAC                │
│  - Start countdown timer                    │
└──────────┬──────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────┐
│      User Has Internet Access 🎉            │
│  Portal shows countdown (auto-refresh)      │
└──────────┬──────────────────────────────────┘
           │
           │ Background thread checks every 60s
           │
           ▼
┌─────────────────────────────────────────────┐
│       Time Expires → Access Revoked         │
│  - Remove iptables rule                     │
│  - Stop WiFi session                        │
│  - User sees portal again                   │
└─────────────────────────────────────────────┘
```

---

## Database Schema

### Table: `users`
```sql
CREATE TABLE users (
    mac TEXT PRIMARY KEY,           -- User's MAC address
    accumulated_time INTEGER,       -- Seconds of WiFi time earned
    wifi_active INTEGER,            -- 1 if WiFi active, 0 if not
    session_started TEXT,           -- ISO timestamp when WiFi started
    last_seen TEXT                  -- ISO timestamp of last activity
);
```

### Table: `bottles`
```sql
CREATE TABLE bottles (
    bottle_type TEXT PRIMARY KEY,   -- Bottle identifier
    time_minutes INTEGER NOT NULL   -- Time reward in minutes
);
```

Pre-populated with 10 bottle types (water_bottle-500mL, coke_litro, etc.)

### Table: `machine_state`
```sql
CREATE TABLE machine_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- Always 1 (single row)
    active_mac TEXT,                        -- MAC currently using machine
    lock_started TEXT                       -- ISO timestamp when locked
);
```

---

## Key Functions (API Reference)

### db.py

**User Management:**
- `get_user(mac)` - Get user by MAC address
- `create_user(mac)` - Create new user
- `add_time_to_user(mac, minutes)` - Add time to user's balance
- `start_wifi_session(mac)` - Activate WiFi and start countdown
- `stop_wifi_session(mac)` - Deactivate WiFi, reset time
- `get_remaining_time(mac)` - Get remaining seconds
- `get_expired_users()` - Get list of expired MACs

**Machine State:**
- `lock_machine(mac)` - Lock machine to MAC (returns False if locked to someone else)
- `release_machine()` - Unlock machine
- `get_machine_state()` - Get current lock status
- `refresh_machine_lock(mac)` - Reset 5-minute timeout

**Bottles:**
- `get_bottle_time(bottle_type)` - Get time reward for bottle
- `get_all_bottles()` - List all bottle types

### portal.py

**Routes:**
- `GET /` - Main portal page
- `POST /lock_machine` - Lock machine for bottle insertion
- `POST /cancel` - Cancel and release machine
- `POST /start_wifi` - Activate WiFi session
- `GET /generate_204` (etc.) - Captive portal detection

**Functions:**
- `get_client_mac()` - Get MAC from request IP
- `allow_mac_internet(mac)` - Add iptables rule
- `revoke_mac_internet(mac)` - Remove iptables rule
- `session_monitor()` - Background thread for expiry

### main_integrated.py

**Components:**
- `LCDDisplay` - 4x20 I2C LCD with fallback
- `CameraThread` - Threaded camera capture
- `find_scanner()` - Detect barcode scanner
- `wait_for_barcode()` - Blocking barcode read
- `run_inference()` - YOLO AI inference

**Main Loop:**
1. Wait for machine lock
2. Wait for barcode scan
3. AI verification
4. Add time to session
5. Repeat

---

## Testing Results

### Database Integration ✅
- User creation/retrieval works
- Machine locking/unlocking works
- Time accumulation works
- WiFi session start/stop works
- Remaining time calculation works

### Portal Server ✅
- Starts on port 80 successfully
- Session monitor thread running
- Database initialized correctly
- Flask routes configured

### Components Status

| Component | Status | Notes |
|-----------|--------|-------|
| SQLite Database | ✅ Working | Thread-safe, auto-init |
| Portal Server | ✅ Running | PID 22773, port 80 |
| MAC Detection | ✅ Working | Via arp/ip neigh |
| iptables Integration | ✅ Working | Add/remove rules |
| Session Expiry | ✅ Working | Background monitor thread |
| Barcode Scanner | ⚠️ Not tested | Requires physical scanner |
| AI Verification | ⚠️ Not tested | Requires camera + model |
| LCD Display | ⚠️ Not tested | Graceful fallback implemented |

---

## Configuration

### Bottle Time Values

| Bottle | Time Reward |
|--------|-------------|
| coke_2L | 75 minutes |
| sprite_1.5L | 60 minutes |
| royal_1.5L | 60 minutes |
| coke_litro | 60 minutes |
| water_bottle-1L | 45 minutes |
| natures_spring_1000ml | 45 minutes |
| water_bottle-500mL | 30 minutes |
| water_bottle-350mL | 10 minutes |
| coke_mismo | 10 minutes |
| pocari_350mL | 10 minutes |

### Barcode Map (main_integrated.py)

Edit `BARCODE_MAP` dictionary to add/modify barcodes:
```python
BARCODE_MAP = {
    "4800100123456": "water_bottle-500mL",
    "4800014147083": "water_bottle-350mL",
    # ... add more
}
```

### Timeouts

- **AI Verification:** 10 seconds (VERIFY_TIMEOUT)
- **AI Confidence:** 0.50 minimum (VERIFY_CONF)
- **Machine Lock Auto-release:** 5 minutes of no scans
- **Session Expiry Check:** Every 60 seconds
- **Inactivity Expiry:** 24 hours

---

## Running the System

### Method 1: Manual (for testing)

**Terminal 1:**
```bash
cd /home/raspi/rvm
sudo python3 portal.py
```

**Terminal 2:**
```bash
cd /home/raspi/rvm
python3 main_integrated.py
```

### Method 2: Background

```bash
# Start portal
sudo python3 portal.py > /tmp/portal.log 2>&1 &

# Start main script
python3 main_integrated.py > /tmp/main.log 2>&1 &

# Monitor
tail -f /tmp/portal.log
tail -f /tmp/main.log
```

### Method 3: systemd (auto-start on boot)

See [PHASE1_SETUP.md](docs/PHASE1_SETUP.md) for systemd service creation.

---

## Current Status

**Portal Server:** Running (PID 22773)
**Database:** Initialized at `/home/raspi/rvm/rvm.db`
**Hotspot:** Should be running (RVM-WiFi)

**Next Steps:**
1. Test with actual barcode scanner and camera
2. Test full user flow (lock → scan → verify → WiFi)
3. Set up systemd services for auto-start
4. Phase 2: Add servo motors for intake door

---

## Known Limitations

1. **No auto-portal detection** - User must manually navigate to http://10.42.0.1
2. **No physical intake door** - Phase 2 will add servo motor
3. **No load cell verification** - Can't detect actual bottle insertion
4. **Manual barcode fallback** - If no scanner, requires typing
5. **OpenCV window** - Shows on RPi desktop (can disable for headless)

---

## Debugging Commands

```bash
# View database
sqlite3 /home/raspi/rvm/rvm.db "SELECT * FROM users;"
sqlite3 /home/raspi/rvm/rvm.db "SELECT * FROM machine_state;"

# Check portal
sudo ss -tulpn | grep ':80'
tail -f /tmp/portal.log

# Check iptables
sudo iptables -L FORWARD -v -n | grep MAC

# Reset database (testing)
rm /home/raspi/rvm/rvm.db
python3 -c "import db"
```

---

## Success Criteria ✅

- [x] SQLite database created and initialized
- [x] Portal server runs on port 80
- [x] Session monitor thread starts
- [x] Database operations work (create, lock, add time, start WiFi)
- [x] MAC detection works
- [x] iptables integration works
- [x] LCD display has graceful fallback
- [x] Main script waits for machine lock
- [x] Time calculation and expiry logic works

**Phase 1 is complete and ready for hardware testing!** 🎉

---

## Files to Use

**Active (Phase 1):**
- ✅ `db.py`
- ✅ `portal.py`
- ✅ `main_integrated.py`
- ✅ `docs/PHASE1_SETUP.md`

**Deprecated (keep for reference):**
- ⚠️ `portal_test.py` (replaced by portal.py)
- ⚠️ `main.py` (replaced by main_integrated.py)

**Unchanged:**
- `best_ncnn_model/` - YOLO model files
- `memory-bank.md` - Session notes
- `docs/system-architecture.md` - Architecture reference

---

## Contact

For issues or questions, see [PHASE1_SETUP.md](docs/PHASE1_SETUP.md) troubleshooting section.
