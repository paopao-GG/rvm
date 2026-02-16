#!/usr/bin/env python3
"""
Minimal RVM Captive Portal — Testing Only

Flow:
1. User connects to RPi hotspot (no internet yet)
2. Phone opens captive portal automatically
3. User clicks "Insert Bottle" (simulates earning wifi)
4. Internet access granted via iptables

Requirements:
- RPi running as hotspot (nmcli/NetworkManager)
- dnsmasq configured to redirect DNS to this RPi
- iptables blocking traffic by default
- This Flask app running on port 80
"""

import subprocess
from flask import Flask, request, render_template_string, redirect
from datetime import datetime

app = Flask(__name__)

# In-memory storage for testing (in production, use SQLite)
allowed_macs = {}

# HTML Templates
PORTAL_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>RVM WiFi Portal</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            padding: 50px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
            margin: 0;
        }
        .container {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            max-width: 400px;
            margin: 0 auto;
        }
        h1 {
            margin-bottom: 20px;
        }
        .status {
            font-size: 18px;
            margin: 20px 0;
        }
        button {
            background: #4CAF50;
            color: white;
            border: none;
            padding: 15px 30px;
            font-size: 18px;
            border-radius: 10px;
            cursor: pointer;
            margin: 10px;
            transition: transform 0.2s;
        }
        button:hover {
            transform: scale(1.05);
        }
        button.danger {
            background: #f44336;
        }
        .info {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 10px;
            padding: 15px;
            margin: 20px 0;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🍾 RVM WiFi Portal</h1>
        <div class="status">
            {% if has_access %}
                <p>✅ Internet Access Active</p>
                <p class="info">Your MAC: {{ client_mac }}</p>
                <form method="POST" action="/revoke">
                    <button type="submit" class="danger">Revoke Access (Test)</button>
                </form>
            {% else %}
                <p>❌ No Internet Access</p>
                <p class="info">Your MAC: {{ client_mac }}</p>
                <form method="POST" action="/grant">
                    <button type="submit">Insert Bottle (Test)</button>
                </form>
            {% endif %}
        </div>
        <div class="info">
            <small>Test portal — clicking the button simulates bottle insertion</small>
        </div>
    </div>
</body>
</html>
"""

SUCCESS_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Access Granted</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="2;url=/">
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            padding: 50px;
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            color: white;
            min-height: 100vh;
            margin: 0;
        }
        .container {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
        }
        h1 { font-size: 48px; margin: 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>✅ Access Granted!</h1>
        <p>You can now browse the internet</p>
        <p><small>Redirecting back to portal...</small></p>
    </div>
</body>
</html>
"""

def get_client_mac():
    """Get the MAC address of the client from the request."""
    client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)

    try:
        # Use arp to get MAC from IP
        result = subprocess.run(
            ['arp', '-n', client_ip],
            capture_output=True,
            text=True,
            timeout=2
        )

        # Parse arp output: IP HWtype HWaddress Flags Mask Iface
        for line in result.stdout.split('\n'):
            if client_ip in line:
                parts = line.split()
                if len(parts) >= 3:
                    mac = parts[2]
                    if ':' in mac:  # Validate it looks like a MAC
                        return mac.upper()

        # Fallback: try ip neigh (modern alternative to arp)
        result = subprocess.run(
            ['ip', 'neigh', 'show', client_ip],
            capture_output=True,
            text=True,
            timeout=2
        )
        for line in result.stdout.split('\n'):
            if 'lladdr' in line:
                parts = line.split()
                mac_idx = parts.index('lladdr') + 1
                if mac_idx < len(parts):
                    mac = parts[mac_idx]
                    return mac.upper()

    except Exception as e:
        print(f"Error getting MAC for {client_ip}: {e}")

    return "UNKNOWN"

def allow_mac_internet(mac):
    """Add iptables rule to allow MAC address through."""
    try:
        # Check if rule already exists
        check = subprocess.run(
            ['iptables', '-C', 'FORWARD', '-m', 'mac', '--mac-source', mac, '-j', 'ACCEPT'],
            capture_output=True
        )

        if check.returncode != 0:  # Rule doesn't exist, add it
            subprocess.run(
                ['iptables', '-I', 'FORWARD', '1', '-m', 'mac', '--mac-source', mac, '-j', 'ACCEPT'],
                check=True
            )
            print(f"✅ Allowed MAC: {mac}")
            return True
        else:
            print(f"ℹ️  MAC already allowed: {mac}")
            return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to allow MAC {mac}: {e}")
        return False

def revoke_mac_internet(mac):
    """Remove iptables rule for MAC address."""
    try:
        # Try to delete the rule (may fail if it doesn't exist, that's OK)
        subprocess.run(
            ['iptables', '-D', 'FORWARD', '-m', 'mac', '--mac-source', mac, '-j', 'ACCEPT'],
            capture_output=True
        )
        print(f"❌ Revoked MAC: {mac}")
        return True
    except Exception as e:
        print(f"Error revoking MAC {mac}: {e}")
        return False

def check_mac_allowed(mac):
    """Check if MAC is allowed through iptables."""
    try:
        result = subprocess.run(
            ['iptables', '-C', 'FORWARD', '-m', 'mac', '--mac-source', mac, '-j', 'ACCEPT'],
            capture_output=True
        )
        return result.returncode == 0
    except:
        return False

@app.route('/')
def portal():
    """Main portal page."""
    client_mac = get_client_mac()
    has_access = check_mac_allowed(client_mac)

    return render_template_string(
        PORTAL_PAGE,
        client_mac=client_mac,
        has_access=has_access
    )

@app.route('/grant', methods=['POST'])
def grant_access():
    """Grant internet access (simulates bottle insertion)."""
    client_mac = get_client_mac()

    if client_mac == "UNKNOWN":
        return "Error: Could not determine your MAC address", 500

    success = allow_mac_internet(client_mac)

    if success:
        allowed_macs[client_mac] = datetime.now()
        return render_template_string(SUCCESS_PAGE)
    else:
        return "Error: Failed to grant access", 500

@app.route('/revoke', methods=['POST'])
def revoke_access():
    """Revoke internet access (for testing)."""
    client_mac = get_client_mac()

    if client_mac == "UNKNOWN":
        return "Error: Could not determine your MAC address", 500

    revoke_mac_internet(client_mac)

    if client_mac in allowed_macs:
        del allowed_macs[client_mac]

    return redirect('/')

# Captive portal detection endpoints (for iOS/Android)
@app.route('/generate_204')
@app.route('/gen_204')
@app.route('/hotspot-detect.html')
@app.route('/library/test/success.html')
@app.route('/ncsi.txt')
@app.route('/success.txt')
def captive_portal_detect():
    """Handle captive portal detection from phones."""
    return redirect('/', code=302)

if __name__ == '__main__':
    print("\n" + "="*60)
    print("RVM Captive Portal Test Server")
    print("="*60)
    print("\nStarting on http://0.0.0.0:80")
    print("\nMake sure you have:")
    print("  1. Hotspot running (nmcli)")
    print("  2. dnsmasq redirecting DNS")
    print("  3. iptables blocking by default")
    print("\nRun with: sudo python3 portal_test.py")
    print("="*60 + "\n")

    # Run on port 80 (requires sudo)
    app.run(host='0.0.0.0', port=80, debug=True)
