# Captive Portal Test Setup Guide

This guide walks through setting up a test captive portal on Raspberry Pi 5 (Bookworm).

## Overview

The test flow:
1. User connects to RPi hotspot → no internet access
2. Phone detects captive portal, opens portal_test.py
3. User clicks "Insert Bottle" button
4. iptables rule added → user now has internet access

---

## Step 1: Create the WiFi Hotspot

Using NetworkManager (native to Bookworm):

### Option A: Open Hotspot (No Password) - Recommended

```bash
# Delete any existing hotspot first (if you already created one)
sudo nmcli connection delete Hotspot 2>/dev/null || true

# Create config file directly (avoids nmcli security quirks)
cat > /tmp/hotspot.nmconnection << 'EOF'
[connection]
id=Hotspot
type=wifi
autoconnect=yes

[wifi]
ssid=RVM-WiFi
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

# Verify it's running (should show mode=ap, no security settings)
nmcli connection show Hotspot | grep -E "ssid|mode"
```

### Option B: Hotspot with Password

```bash
# Quick command (generates random password if not specified)
sudo nmcli device wifi hotspot ifname wlan0 ssid RVM-WiFi password bottle123

# Verify it's running
nmcli connection show
```

The hotspot should appear as "Hotspot" in the connection list.

To stop it later:
```bash
sudo nmcli connection down Hotspot
```

To start it again:
```bash
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

# Redirect all DNS queries to this RPi
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

# BLOCK all forwarding by default (this is the key — no internet until we allow it)
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
```

To clear all rules (if you mess up):
```bash
sudo iptables -F
sudo iptables -t nat -F
sudo iptables -P FORWARD ACCEPT
```

---

## Step 4: Install Flask and Run the Portal

```bash
cd /home/raspi/rvm

# Install Flask (if not already installed)
pip install flask

# Run the test portal (requires sudo for port 80)
sudo python3 portal_test.py
```

You should see:
```
============================================================
RVM Captive Portal Test Server
============================================================

Starting on http://0.0.0.0:80

Make sure you have:
  1. Hotspot running (nmcli)
  2. dnsmasq redirecting DNS
  3. iptables blocking by default

Run with: sudo python3 portal_test.py
============================================================

 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:80
 * Running on http://10.42.0.1:80
```

---

## Step 5: Test from Your Phone

1. **Connect to "RVM-WiFi"** hotspot on your phone
   - If you used Option A (open hotspot): just connect, no password needed
   - If you used Option B (password): enter `bottle123`
2. Your phone should **automatically open** the captive portal page
   - If it doesn't, open a browser and visit any HTTP site (e.g. `http://example.com`)
3. You should see the portal page showing "❌ No Internet Access"
4. **Click "Insert Bottle (Test)"**
5. You should see "✅ Access Granted!" and now have internet access
6. Try browsing — it should work!

---

## Troubleshooting

### Phone doesn't open portal automatically

**Symptom:** Phone connects but doesn't show portal page

**Fix:** Make sure dnsmasq is running and redirecting DNS:
```bash
sudo systemctl status dnsmasq
```

Test DNS redirection from another device connected to the hotspot:
```bash
nslookup google.com
# Should return 10.42.0.1 (the RPi's IP)
```

### Portal page shows but "Insert Bottle" doesn't give internet

**Symptom:** Button works but still no internet access

**Check iptables rules:**
```bash
sudo iptables -L FORWARD -v -n
```

You should see a rule like:
```
ACCEPT  all  --  *  *  0.0.0.0/0  0.0.0.0/0  MAC XX:XX:XX:XX:XX:XX
```

**Check if the MAC was added:**
```bash
# Replace with your phone's MAC
sudo iptables -C FORWARD -m mac --mac-source AA:BB:CC:DD:EE:FF -j ACCEPT
echo $?  # Should print 0 if rule exists
```

**Check NAT:**
```bash
sudo iptables -t nat -L -v -n
```

You should see a MASQUERADE rule in POSTROUTING.

### "Error: Could not determine your MAC address"

**Symptom:** Portal shows "UNKNOWN" for your MAC

**Fix:** Install `arp` or use `ip neigh`:
```bash
# Check if arp works
arp -a

# Or use ip neigh
ip neigh show
```

The script tries both — if neither works, you may need to adjust the `get_client_mac()` function.

---

## How It Works

1. **Hotspot (nmcli):** Creates a WiFi network on `wlan0`, assigns IPs via DHCP (10.42.0.x)
2. **dnsmasq:** Intercepts all DNS queries and returns the RPi's IP (10.42.0.1) for every domain
3. **iptables:** Blocks all forwarding by default. When you click the button, the script adds a rule to allow your phone's MAC address through.
4. **NAT (masquerade):** Translates hotspot traffic (10.42.0.x) to the RPi's ethernet IP so it can reach the internet

---

## Next Steps

Once this test works:
1. Integrate with the main scanning script (main.py)
2. Add SQLite for persistent sessions
3. Add time limits and expiry
4. Add systemd services for auto-start on boot
