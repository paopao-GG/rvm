# Captive Portal Setup Guide

This guide walks through setting up the P.E.T-O captive portal on Raspberry Pi 5 (Bookworm).

## Overview

The production system uses two scripts that share a SQLite database:

- **portal.py** — Flask web server on port 80. Handles the user-facing portal, machine locking, WiFi session management, and iptables MAC filtering.
- **main_integrated.py** — Hardware controller. Handles barcode scanning, AI verification, servo motors, load cell, and LCD display.

The full flow:
1. User connects to "P.E.T-O WI-FI" hotspot → blocked by default (no internet)
2. Phone detects captive portal, opens portal.py at http://10.42.0.1
3. User taps "Insert Bottles" → machine locks to their MAC
4. User scans bottles at the machine → time accumulates in SQLite
5. User taps "Start WiFi" → iptables rule allows their MAC → internet access
6. Background monitor revokes access when time expires

## Prerequisites

- Raspberry Pi 5 running Raspberry Pi OS Bookworm (64-bit)
- Ethernet cable connected to router/modem (WAN uplink)
- Python virtual environment with dependencies installed (see requirements.txt)

---

## Step 1: Create the WiFi Hotspot

Using NetworkManager (native to Bookworm):

### Option A: Open Hotspot (No Password) - Recommended for testing

```bash
# Delete any existing hotspot first
sudo nmcli connection delete Hotspot 2>/dev/null || true

# Create config file directly (avoids nmcli security quirks)
cat > /tmp/hotspot.nmconnection << 'EOF'
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
EOF

# Install the config
sudo cp /tmp/hotspot.nmconnection /etc/NetworkManager/system-connections/Hotspot.nmconnection
sudo chmod 600 /etc/NetworkManager/system-connections/Hotspot.nmconnection
sudo nmcli connection reload

# Start the hotspot
sudo nmcli connection up Hotspot

# Verify it's running (should show mode=ap)
nmcli connection show Hotspot | grep -E "ssid|mode"
```

### Option B: Hotspot with Password

```bash
sudo nmcli device wifi hotspot ifname wlan0 ssid "P.E.T-O WI-FI" password bottle123

# Verify it's running
nmcli connection show --active
```

The hotspot should appear as "Hotspot" in the connection list.

```bash
# Stop hotspot
sudo nmcli connection down Hotspot

# Start hotspot
sudo nmcli connection up Hotspot
```

---

## Step 2: Install and Configure dnsmasq

```bash
# Install dnsmasq
sudo apt update
sudo apt install dnsmasq -y

# Stop NetworkManager's built-in dnsmasq to avoid conflicts
sudo mkdir -p /etc/NetworkManager/conf.d
echo -e "[main]\ndns=default" | sudo tee /etc/NetworkManager/conf.d/no-dnsmasq.conf
sudo systemctl restart NetworkManager

# Configure dnsmasq
sudo nano /etc/dnsmasq.conf
```

Add these lines to `/etc/dnsmasq.conf`:

```
# Listen on the hotspot interface
interface=wlan0
bind-interfaces

# DHCP range for hotspot clients
dhcp-range=10.42.0.10,10.42.0.100,12h

# Redirect all DNS queries to this RPi (triggers captive portal detection)
address=/#/10.42.0.1
```

Restart dnsmasq:
```bash
sudo systemctl restart dnsmasq
sudo systemctl enable dnsmasq
```

---

## Step 3: Configure iptables (Firewall Rules)

```bash
# Enable IP forwarding (required for NAT)
sudo sysctl -w net.ipv4.ip_forward=1

# Make it permanent
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf

# Set up NAT (masquerade) so hotspot traffic can reach the internet via ethernet
sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE

# BLOCK all forwarding by default (no internet until portal allows it)
sudo iptables -P FORWARD DROP

# Allow established connections (so replies can come back)
sudo iptables -A FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT

# Allow traffic from RPi itself (so dnsmasq/portal work)
sudo iptables -A INPUT -i wlan0 -j ACCEPT
sudo iptables -A OUTPUT -o wlan0 -j ACCEPT

# Save the rules so they persist across reboots
sudo apt install iptables-persistent -y
sudo netfilter-persistent save
```

To view current rules:
```bash
sudo iptables -L -v -n
sudo iptables -L FORWARD -v -n | grep MAC   # See allowed MACs
```

To clear all rules (if you mess up):
```bash
sudo iptables -F
sudo iptables -t nat -F
sudo iptables -P FORWARD ACCEPT
```

---

## Step 4: Run the Portal

```bash
cd /home/raspi/rvm
source venv/bin/activate

# Run portal (requires sudo for port 80 and iptables)
sudo python3 portal.py
```

You should see:
```
============================================================
RVM Captive Portal - Phase 1 Starting
============================================================
Database initialized
Starting portal on http://0.0.0.0:80
Prerequisites: 1) Hotspot running 2) iptables configured 3) main_integrated.py running
============================================================

 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:80
 * Running on http://10.42.0.1:80
```

The portal starts a background session monitor thread that checks every 5 seconds for expired sessions and revokes their iptables rules automatically.

---

## Step 5: Run the Main Script (Second Terminal)

```bash
cd /home/raspi/rvm
source venv/bin/activate

# Run main script (requires sudo for barcode scanner grab)
sudo python3 main_integrated.py
```

Or use the startup script that runs both:
```bash
chmod +x start_phase1.sh
./start_phase1.sh
```

---

## Step 6: Test from Your Phone

1. **Connect to "P.E.T-O WI-FI"** on your phone
   - Open hotspot: just connect, no password
   - Password hotspot: enter `bottle123`
2. Your phone should **automatically open** the captive portal page
   - If it doesn't, open a browser and go to `http://10.42.0.1`
   - Or visit any HTTP site (e.g. `http://example.com`) — it will redirect
3. You should see the P.E.T-O portal with a rate table and "Insert Bottles" button
4. **Tap "Insert Bottles"** — the machine locks to your MAC
5. Scan a bottle barcode at the machine → AI verifies → time is added
6. **Tap "Start WiFi"** on the portal
7. Your phone now has internet access with a countdown timer
8. When time runs out, access is revoked and you're back at the portal

---

## Portal Pages and States

The portal dynamically shows different content based on user/machine state:

| State | What the user sees | Available actions |
|-------|-------------------|-------------------|
| Idle (no WiFi, no lock) | Welcome message, rate table | "Insert Bottles" button |
| Machine locked to me | "Machine Ready", accumulated time | "Start WiFi", "Cancel" |
| WiFi active + inserting | Countdown timer, "Inserting Bottles" | "Done Inserting" |
| WiFi active (browsing) | Countdown timer, "Internet Active" | "Insert More Bottles" |
| Machine locked to someone else | "Machine In Use" | Wait and retry |

---

## Captive Portal Detection

The portal handles automatic captive portal detection for all major platforms.
These endpoints respond with a 302 redirect to `/`:

| Endpoint | Platform |
|----------|----------|
| `/generate_204` | Android (Chrome) |
| `/gen_204` | Android (fallback) |
| `/hotspot-detect.html` | iOS / macOS |
| `/library/test/success.html` | iOS (fallback) |
| `/ncsi.txt` | Windows |
| `/success.txt` | Generic |

---

## How It Works (Technical)

1. **Hotspot (nmcli):** Creates a WiFi network on `wlan0`, assigns IPs via DHCP (10.42.0.x range)
2. **dnsmasq:** Intercepts all DNS queries and returns the RPi's IP (10.42.0.1) for every domain. This triggers captive portal detection on phones.
3. **iptables:** Blocks all FORWARD traffic by default. When a user taps "Start WiFi", portal.py runs `iptables -I FORWARD 1 -m mac --mac-source <MAC> -j ACCEPT` to allow that device through.
4. **NAT (masquerade):** Translates hotspot traffic (10.42.0.x) to the RPi's ethernet IP so it can reach the internet router.
5. **MAC resolution:** Portal uses `ip neigh show <client_ip>` to map the HTTP client's IP to their MAC address. The IP is validated before use to prevent command injection.
6. **Session monitor:** A background thread runs every 5 seconds. It checks all active WiFi sessions — if `accumulated_time - elapsed_since_session_started <= 0`, it runs `iptables -D` to revoke access and marks the session as inactive in SQLite.

---

## Troubleshooting

### Phone doesn't open portal automatically

**Symptom:** Phone connects to WiFi but no portal page appears

**Fix:** Make sure dnsmasq is running and redirecting DNS:
```bash
sudo systemctl status dnsmasq
```

Test DNS redirection from another device on the hotspot:
```bash
nslookup google.com
# Should return 10.42.0.1 (the RPi's IP)
```

If dnsmasq is running but no redirect, check that NetworkManager's built-in DNS isn't conflicting:
```bash
cat /etc/NetworkManager/conf.d/no-dnsmasq.conf
# Should contain: [main] dns=default
```

### "Insert Bottles" works but "Start WiFi" doesn't give internet

**Check iptables rules:**
```bash
sudo iptables -L FORWARD -v -n
```

You should see a rule like:
```
ACCEPT  all  --  *  *  0.0.0.0/0  0.0.0.0/0  MAC XX:XX:XX:XX:XX:XX
```

**Check NAT is set up:**
```bash
sudo iptables -t nat -L -v -n
# Should see MASQUERADE rule in POSTROUTING chain
```

**Check IP forwarding:**
```bash
cat /proc/sys/net/ipv4/ip_forward
# Should print 1
```

### "Error: Could not determine your MAC address"

**Symptom:** Portal shows error or "UNKNOWN" MAC

**Fix:** Check that `ip neigh` can see the client:
```bash
ip neigh show
# Should list connected devices with their MAC addresses
```

If the client doesn't appear, they may not have sent any traffic yet. Visiting any page should trigger an ARP entry.

### Portal shows "Machine In Use" but nobody is using it

The machine lock auto-expires after 5 minutes of no barcode scans. If it's stuck:
```bash
# Check the lock
sqlite3 /home/raspi/rvm/rvm.db "SELECT * FROM machine_state;"

# Manually release the lock
sqlite3 /home/raspi/rvm/rvm.db "UPDATE machine_state SET active_mac = NULL, lock_started = NULL WHERE id = 1;"
```

### Time expired but user still has internet

The session monitor checks every 5 seconds. If it's not running:
```bash
# Check portal logs for monitor messages
grep "Session monitor" /tmp/rvm_portal.log
```

Manually revoke a MAC:
```bash
sudo iptables -D FORWARD -m mac --mac-source AA:BB:CC:DD:EE:FF -j ACCEPT
```

---

## Logs

```bash
# Portal server logs
tail -f /tmp/rvm_portal.log

# Main script logs
tail -f /tmp/rvm_main_integrated.log

# Both at once
tail -f /tmp/rvm_portal.log /tmp/rvm_main_integrated.log
```

---

## Database Inspection

```bash
# View all users and their time
sqlite3 /home/raspi/rvm/rvm.db "SELECT mac, accumulated_time, wifi_active, session_started FROM users;"

# View machine lock status
sqlite3 /home/raspi/rvm/rvm.db "SELECT * FROM machine_state;"

# View bottle time rewards
sqlite3 /home/raspi/rvm/rvm.db "SELECT * FROM bottles ORDER BY time_minutes;"

# Reset a specific user's session
sqlite3 /home/raspi/rvm/rvm.db "UPDATE users SET wifi_active = 0, accumulated_time = 0, session_started = NULL WHERE mac = 'AA:BB:CC:DD:EE:FF';"

# Reset everything (full wipe)
rm /home/raspi/rvm/rvm.db
python3 -c "import db"   # Recreates tables and bottle data
```

---

## Running as systemd Services

For auto-start on boot, create two service files:

### /etc/systemd/system/rvm-portal.service
```ini
[Unit]
Description=P.E.T-O Captive Portal
After=network-online.target NetworkManager.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/raspi/rvm
ExecStart=/home/raspi/rvm/venv/bin/python3 portal.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### /etc/systemd/system/rvm-main.service
```ini
[Unit]
Description=P.E.T-O Main Controller
After=network-online.target rvm-portal.service
Wants=rvm-portal.service

[Service]
Type=simple
WorkingDirectory=/home/raspi/rvm
ExecStart=/home/raspi/rvm/venv/bin/python3 main_integrated.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable rvm-portal rvm-main
sudo systemctl start rvm-portal rvm-main

# Check status
sudo systemctl status rvm-portal
sudo systemctl status rvm-main

# View logs
sudo journalctl -u rvm-portal -f
sudo journalctl -u rvm-main -f
```
