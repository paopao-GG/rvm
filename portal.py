#!/usr/bin/env python3
"""
RVM Captive Portal - Production Implementation
Phase 1: Barcode scanning, AI verification, time allocation, WiFi portal
No servo motors yet - just bottle verification and time tracking
"""

import subprocess
import threading
import time
import logging
from typing import Optional, Tuple
from flask import Flask, request, render_template_string, redirect, jsonify, send_from_directory
from datetime import datetime, timedelta

import db
from utils import format_time, validate_ip_address

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/tmp/rvm_portal.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ── HTML Templates ─────────────────────────────────────────────────

PORTAL_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>P.E.T-O WiFi Portal</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
            margin: 0;
        }
        .container {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            max-width: 400px;
            margin: 0 auto;
        }
        h1 { margin-bottom: 20px; font-size: 28px; }
        .status {
            font-size: 18px;
            margin: 20px 0;
        }
        .time-display {
            font-size: 48px;
            font-weight: bold;
            margin: 20px 0;
            color: #4CAF50;
        }
        .info {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 10px;
            padding: 15px;
            margin: 15px 0;
            font-size: 14px;
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
            width: 100%;
        }
        button:hover { transform: scale(1.05); }
        button.secondary { background: #2196F3; }
        button.danger { background: #f44336; }
        button:disabled {
            background: #999;
            cursor: not-allowed;
            transform: none;
        }
        .warning {
            background: rgba(255, 152, 0, 0.3);
            border-radius: 10px;
            padding: 15px;
            margin: 15px 0;
        }
        .logo {
            max-width: 300px;
            width: 100%;
            margin: 0 auto 20px;
            border-radius: 10px;
        }
        .rate-table {
            background: rgba(255, 255, 255, 0.15);
            border-radius: 10px;
            padding: 15px;
            margin: 20px 0;
            font-size: 13px;
            text-align: left;
        }
        .rate-table h3 {
            text-align: center;
            margin-top: 0;
            margin-bottom: 15px;
            font-size: 16px;
        }
        .rate-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 10px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        .rate-row:last-child {
            border-bottom: none;
        }
        .rate-volume {
            font-weight: bold;
        }
        .rate-time {
            color: white;
            font-weight: bold;
        }
    </style>
    <script>
        // Auto-refresh page every 2 seconds to update countdown
        {% if wifi_active %}
        setTimeout(() => location.reload(), 2000);
        {% endif %}
    </script>
</head>
<body>
    <div class="container">
        <img src="/peto.jpg" alt="P.E.T-O Logo" class="logo">
        <h1>P.E.T-O WI-FI</h1>

        <!-- Rate Table -->
        <div class="rate-table">
            <h3>📊 WiFi Time Rates</h3>
            <div class="rate-row">
                <span class="rate-volume">100mL</span>
                <span class="rate-time">1 min</span>
            </div>
            <div class="rate-row">
                <span class="rate-volume">200mL</span>
                <span class="rate-time">2 min</span>
            </div>
            <div class="rate-row">
                <span class="rate-volume">230mL</span>
                <span class="rate-time">2.3 min</span>
            </div>
            <div class="rate-row">
                <span class="rate-volume">250mL</span>
                <span class="rate-time">2.5 min</span>
            </div>
            <div class="rate-row">
                <span class="rate-volume">280mL</span>
                <span class="rate-time">2.8 min</span>
            </div>
            <div class="rate-row">
                <span class="rate-volume">290mL</span>
                <span class="rate-time">3.2 min</span>
            </div>
            <div class="rate-row">
                <span class="rate-volume">330mL</span>
                <span class="rate-time">3.3 min</span>
            </div>
            <div class="rate-row">
                <span class="rate-volume">350mL</span>
                <span class="rate-time">3.5 min</span>
            </div>
            <div class="rate-row">
                <span class="rate-volume">500mL</span>
                <span class="rate-time">5 min</span>
            </div>
            <div class="rate-row">
                <span class="rate-volume">600mL</span>
                <span class="rate-time">6 min</span>
            </div>
            <div class="rate-row">
                <span class="rate-volume">750mL</span>
                <span class="rate-time">7.5 min</span>
            </div>
            <div class="rate-row">
                <span class="rate-volume">1000mL (1L)</span>
                <span class="rate-time">10 min</span>
            </div>
            <div class="rate-row">
                <span class="rate-volume">1250mL</span>
                <span class="rate-time">12.5 min</span>
            </div>
            <div class="rate-row">
                <span class="rate-volume">1500mL (1.5L)</span>
                <span class="rate-time">15 min</span>
            </div>
            <div class="rate-row">
                <span class="rate-volume">2000mL (2L)</span>
                <span class="rate-time">20 min</span>
            </div>
        </div>

        {% if wifi_active and machine_locked_to_me %}
            <!-- WiFi Active + Inserting Bottles -->
            <div class="status">
                <p>✅ WiFi Active</p>
                <p>🔒 Inserting Bottles</p>
            </div>
            <div class="time-display">{{ remaining_time }}</div>
            <div class="info">
                <p>Scan bottles at the machine to add more time!</p>
                <small>Time updates automatically as you insert</small>
            </div>
            <form method="POST" action="/done_inserting">
                <button type="submit" class="secondary">Done Inserting ✅</button>
            </form>

        {% elif wifi_active %}
            <!-- WiFi Active - Show Countdown -->
            <div class="status">
                <p>✅ Internet Access Active</p>
            </div>
            <div class="time-display">{{ remaining_time }}</div>
            <div class="info">
                <p>Enjoy your WiFi!</p>
                <small>Time remaining updates automatically</small>
            </div>
            <form method="POST" action="/lock_machine">
                <button type="submit" class="secondary">Insert More Bottles ♻️</button>
            </form>

        {% elif machine_locked_to_me %}
            <!-- Machine locked to this user - Show accumulated time -->
            <div class="status">
                <p>🔒 Machine Ready</p>
                <p>Scan bottles at the machine</p>
            </div>
            <div class="time-display">{{ accumulated_time }}</div>
            <div class="info">
                <p>You have {{ accumulated_time_text }} accumulated</p>
                <small>Insert more bottles to earn more time</small>
            </div>
            <form method="POST" action="/start_wifi">
                <button type="submit">Done - Start WiFi 🚀</button>
            </form>
            <form method="POST" action="/cancel">
                <button type="submit" class="danger">Cancel</button>
            </form>

        {% elif machine_in_use %}
            <!-- Machine locked to someone else -->
            <div class="status">
                <p>⏳ Machine In Use</p>
            </div>
            <div class="warning">
                <p>Someone else is currently using the machine</p>
                <small>Please wait and try again in a moment</small>
            </div>
            <form method="POST" action="/lock_machine">
                <button type="submit">Insert Bottles</button>
            </form>

        {% else %}
            <!-- Idle state - Ready to start -->
            <div class="status">
                <p>👋 Welcome!</p>
                <p>Insert bottles to earn WiFi time</p>
            </div>
            <div class="info">
                <p>How it works:</p>
                <small>
                    1. Tap "Insert Bottles"<br>
                    2. Scan bottles at the machine<br>
                    3. Each bottle adds time<br>
                    4. Tap "Start WiFi" when done
                </small>
            </div>
            <form method="POST" action="/lock_machine">
                <button type="submit">Insert Bottles 🍾</button>
            </form>
        {% endif %}

        <div class="info" style="margin-top: 30px;">
            <small>Your MAC: {{ client_mac }}</small>
        </div>
    </div>
</body>
</html>
"""

SUCCESS_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
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
        <h1>{{ emoji }} {{ title }}</h1>
        <p>{{ message }}</p>
        <p><small>Redirecting back to portal...</small></p>
    </div>
</body>
</html>
"""


# ── Helper Functions ───────────────────────────────────────────────

def get_client_mac() -> str:
    """
    Get the MAC address of the client from the request.

    Security: Validates IP address format before using in subprocess commands.

    Returns:
        MAC address string (uppercase) or "UNKNOWN" if unable to determine
    """
    client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)

    # Security: Validate IP address format to prevent command injection
    if not validate_ip_address(client_ip):
        logger.warning(f"Invalid IP address format: {client_ip}")
        return "UNKNOWN"

    try:
        # Use ip neigh (more reliable on modern systems)
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
        logger.warning(f"Error getting MAC for {client_ip}: {e}")

    return "UNKNOWN"


def allow_mac_internet(mac: str) -> bool:
    """
    Add iptables rule to allow MAC address through.

    Args:
        mac: MAC address to allow

    Returns:
        True if successful, False otherwise
    """
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
            logger.info("✅ Allowed MAC: %s", mac)
        else:
            logger.debug("MAC already allowed: %s", mac)

        return True
    except subprocess.CalledProcessError as e:
        logger.error("Failed to allow MAC %s: %s", mac, e)
        return False


def revoke_mac_internet(mac: str) -> bool:
    """
    Remove iptables rule for MAC address.

    Args:
        mac: MAC address to revoke

    Returns:
        True if successful, False otherwise
    """
    try:
        result = subprocess.run(
            ['iptables', '-D', 'FORWARD', '-m', 'mac', '--mac-source', mac, '-j', 'ACCEPT'],
            capture_output=True
        )
        if result.returncode == 0:
            logger.info("❌ Revoked MAC: %s", mac)
            return True
        else:
            # Rule might not exist (already deleted), which is OK
            logger.debug("iptables delete returned %d for MAC %s (rule may not exist)", result.returncode, mac)
            return True
    except Exception as e:
        logger.error("Error revoking MAC %s: %s", mac, e)
        return False


# ── Flask Routes ───────────────────────────────────────────────────

@app.route('/')
def portal():
    """Main portal page."""
    client_mac = get_client_mac()
    if client_mac == "UNKNOWN":
        return "Error: Could not determine your MAC address", 500

    # Ensure user exists
    db.create_user(client_mac)
    db.update_last_seen(client_mac)

    user = db.get_user(client_mac)
    machine_state = db.get_machine_state()

    # Determine state
    wifi_active = user['wifi_active'] == 1
    machine_locked_to_me = (machine_state['active_mac'] == client_mac) if machine_state else False
    machine_in_use = (machine_state['active_mac'] and machine_state['active_mac'] != client_mac) if machine_state else False

    # Calculate display values
    remaining_seconds = db.get_remaining_time(client_mac) if wifi_active else 0
    accumulated_seconds = user['accumulated_time']
    accumulated_time_display = format_time(accumulated_seconds)

    return render_template_string(
        PORTAL_PAGE,
        client_mac=client_mac,
        wifi_active=wifi_active,
        machine_locked_to_me=machine_locked_to_me,
        machine_in_use=machine_in_use,
        remaining_time=format_time(remaining_seconds),
        accumulated_time=accumulated_time_display,
        accumulated_time_text=accumulated_time_display
    )


@app.route('/lock_machine', methods=['POST'])
def lock_machine():
    """Lock the machine to this user for bottle insertion."""
    client_mac = get_client_mac()
    if client_mac == "UNKNOWN":
        logger.warning("Lock machine failed - unknown MAC address")
        return "Error: Could not determine your MAC address", 500

    success = db.lock_machine(client_mac)

    if success:
        logger.info("🔒 Machine locked to %s", client_mac)
        return render_template_string(
            SUCCESS_PAGE,
            emoji="🔒",
            title="Machine Locked",
            message="Go to the machine and start scanning bottles!"
        )
    else:
        logger.warning("Machine lock failed for %s - already in use", client_mac)
        return render_template_string(
            SUCCESS_PAGE,
            emoji="⏳",
            title="Machine In Use",
            message="Someone else is using the machine. Please wait."
        )


@app.route('/cancel', methods=['POST'])
def cancel():
    """Cancel bottle insertion and release machine lock."""
    client_mac = get_client_mac()
    machine_state = db.get_machine_state()

    if machine_state and machine_state['active_mac'] == client_mac:
        db.release_machine()
        logger.info("Machine lock released by %s (cancelled)", client_mac)

    return redirect('/')


@app.route('/done_inserting', methods=['POST'])
def done_inserting():
    """Release machine lock without stopping WiFi (used when inserting while WiFi is active)."""
    client_mac = get_client_mac()
    machine_state = db.get_machine_state()

    if machine_state and machine_state['active_mac'] == client_mac:
        db.release_machine()
        logger.info("Machine lock released by %s (done inserting, WiFi stays active)", client_mac)

    return redirect('/')


@app.route('/start_wifi', methods=['POST'])
def start_wifi():
    """Start WiFi session (activate internet access)."""
    client_mac = get_client_mac()
    if client_mac == "UNKNOWN":
        logger.warning("Start WiFi failed - unknown MAC address")
        return "Error: Could not determine your MAC address", 500

    user = db.get_user(client_mac)
    machine_state = db.get_machine_state()

    # Verify this user has the machine lock
    if not machine_state or machine_state['active_mac'] != client_mac:
        logger.warning("Start WiFi denied for %s - no machine lock", client_mac)
        return "Error: You don't have the machine lock", 403

    # Check if user has accumulated time
    if user['accumulated_time'] <= 0:
        logger.warning("Start WiFi denied for %s - no accumulated time", client_mac)
        return render_template_string(
            SUCCESS_PAGE,
            emoji="❌",
            title="No Time",
            message="You need to scan at least one bottle first!"
        )

    # Release machine lock
    db.release_machine()
    logger.debug("Machine lock released by %s (starting WiFi)", client_mac)

    # Start WiFi session
    db.start_wifi_session(client_mac)

    # Add iptables rule
    success = allow_mac_internet(client_mac)

    if success:
        total_seconds = user['accumulated_time']
        time_display = format_time(total_seconds)
        logger.info("🚀 WiFi started for %s - %s", client_mac, time_display)
        return render_template_string(
            SUCCESS_PAGE,
            emoji="✅",
            title="WiFi Active!",
            message=f"You have {time_display} of internet access"
        )
    else:
        logger.error("Failed to activate internet for %s", client_mac)
        return "Error: Failed to activate internet", 500


# Captive portal detection endpoints
@app.route('/generate_204')
@app.route('/gen_204')
@app.route('/hotspot-detect.html')
@app.route('/library/test/success.html')
@app.route('/ncsi.txt')
@app.route('/success.txt')
def captive_portal_detect():
    """Handle captive portal detection from phones."""
    return redirect('/', code=302)


# Logo image
@app.route('/peto.jpg')
def logo():
    """Serve the P.E.T-O logo image."""
    return send_from_directory('/home/raspi/rvm', 'peto.jpg')


# ── Background Session Monitor ─────────────────────────────────────

def session_monitor() -> None:
    """Background thread to check for expired sessions and revoke access."""
    logger.info("🔄 Session monitor started (checking every 5 seconds)")

    while True:
        try:
            # Get all active WiFi users and check their remaining time
            with db.get_db() as conn:
                active_users = conn.execute(
                    "SELECT mac FROM users WHERE wifi_active = 1"
                ).fetchall()

            for row in active_users:
                mac = row['mac']
                remaining = db.get_remaining_time(mac)

                # Log remaining time for debugging when low
                if remaining <= 30:
                    logger.debug(f"User {mac[-8:]}: {remaining}s remaining")

                # Revoke if time has run out
                if remaining <= 0:
                    logger.info(f"⏰ Time expired for {mac[-8:]} - revoking access")
                    revoke_mac_internet(mac)
                    db.stop_wifi_session(mac)

            # Also check for inactive users (24h timeout)
            cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
            with db.get_db() as conn:
                inactive_users = conn.execute(
                    "SELECT mac FROM users WHERE (last_seen < ? OR last_seen IS NULL) AND wifi_active = 1",
                    (cutoff,)
                ).fetchall()

            for row in inactive_users:
                mac = row['mac']
                logger.info(f"⏰ Inactive user timeout: {mac[-8:]}")
                revoke_mac_internet(mac)
                db.stop_wifi_session(mac)

        except Exception as e:
            logger.exception("Error in session monitor: %s", e)

        # Check every 5 seconds for faster expiration detection
        time.sleep(5)


# ── Main ───────────────────────────────────────────────────────────

if __name__ == '__main__':
    logger.info("="*60)
    logger.info("RVM Captive Portal - Phase 1 Starting")
    logger.info("="*60)
    logger.info("Database initialized")

    # Start background session monitor
    monitor_thread = threading.Thread(target=session_monitor, daemon=True)
    monitor_thread.start()

    logger.info("Starting portal on http://0.0.0.0:80")
    logger.info("Prerequisites: 1) Hotspot running 2) iptables configured 3) main_integrated.py running")
    logger.info("View logs: tail -f /tmp/rvm_portal.log")
    logger.info("="*60)

    # Run on port 80 (requires sudo)
    # Security Note: MAC-based authentication can be spoofed. Use additional auth for production.
    app.run(host='0.0.0.0', port=80, debug=False)
