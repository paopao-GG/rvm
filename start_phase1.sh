#!/bin/bash
# RVM Phase 1 Startup Script

echo "============================================================"
echo "RVM Phase 1 - Starting System"
echo "============================================================"
echo

# Check if hotspot is running
echo "Checking hotspot status..."
if nmcli connection show --active | grep -q "Hotspot"; then
    echo "✓ Hotspot is running"
else
    echo "⚠ Hotspot not running, starting..."
    sudo nmcli connection up Hotspot
    if [ $? -eq 0 ]; then
        echo "✓ Hotspot started"
    else
        echo "✗ Failed to start hotspot"
        exit 1
    fi
fi
echo

# Check IP forwarding
echo "Checking IP forwarding..."
if [ "$(cat /proc/sys/net/ipv4/ip_forward)" = "1" ]; then
    echo "✓ IP forwarding enabled"
else
    echo "⚠ Enabling IP forwarding..."
    sudo sysctl -w net.ipv4.ip_forward=1 > /dev/null
    echo "✓ IP forwarding enabled"
fi
echo

# Kill old processes
echo "Stopping old processes..."
sudo pkill -f portal.py 2>/dev/null && echo "  Stopped old portal.py"
pkill -f main_integrated.py 2>/dev/null && echo "  Stopped old main_integrated.py"
sleep 1
echo

# Start portal server
echo "Starting portal server..."
cd /home/raspi/rvm
sudo python3 portal.py > /tmp/portal.log 2>&1 &
PORTAL_PID=$!
sleep 2

if sudo ss -tulpn | grep -q ':80'; then
    echo "✓ Portal server running (PID: $PORTAL_PID)"
else
    echo "✗ Portal server failed to start"
    echo "  Check /tmp/portal.log for errors"
    exit 1
fi
echo

# Start main script
echo "Starting main script..."
python3 main_integrated.py > /tmp/main.log 2>&1 &
MAIN_PID=$!
echo "✓ Main script running (PID: $MAIN_PID)"
echo

# Show status
echo "============================================================"
echo "System Status"
echo "============================================================"
echo "Portal Server:   PID $PORTAL_PID  (http://10.42.0.1)"
echo "Main Script:     PID $MAIN_PID"
echo
echo "Logs:"
echo "  Portal: tail -f /tmp/portal.log"
echo "  Main:   tail -f /tmp/main.log"
echo
echo "Database: /home/raspi/rvm/rvm.db"
echo
echo "To stop:"
echo "  sudo pkill -f portal.py"
echo "  pkill -f main_integrated.py"
echo "============================================================"
echo
echo "✅ Phase 1 system is running!"
echo
