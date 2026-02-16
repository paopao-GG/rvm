# RVM System Architecture

- The device is a reverse vending machine where users place empty bottles in exchange of free wifi

## Hardware

| Component | Purpose |
|-----------|---------|
| Raspberry Pi 5 | Main controller, wifi hotspot |
| Ethernet cable | Connects RPi to router/modem for internet (WAN) |
| Barcode Scanner | Identifies bottle type via barcode |
| USB Webcam | AI bottle verification |
| Servo Motor | Intake door — opens to let user drop the bottle in |
| 4x20 I2C LCD | Displays status messages to the user |

Note: gpiozero PWM may have jitter on RPi 5. If servo movement is unreliable, use a PCA9685 I2C servo driver board as a fallback.

## Software

| Component | Purpose |
|-----------|---------|
| nmcli (NetworkManager) | Creates the RPi wifi hotspot (native to Bookworm) |
| dnsmasq | DHCP server + DNS redirect for captive portal |
| iptables | Blocks/allows internet per user (MAC address), NAT forwarding |
| Flask web server | Captive portal page (runs on RPi) |
| SQLite | Stores user sessions (MAC, time remaining, last seen) |
| Python main script | Handles scanning, AI, servo, and writes to SQLite |
| gpiozero | Controls servo motor via GPIO |
| RPLCD | Controls the 4x20 I2C LCD |

## User Flow

1. User connects to the RPi's hotspot ("RVM-WiFi")
    - phone detects captive portal and opens the Flask portal page
    - portal shows "Insert bottle to get WiFi time" with an "Insert Bottles" button
    - LCD displays "Ready"

2. User taps "Insert Bottles" on the portal page
    - if no one else is using the machine, their MAC is locked as the active session
    - if the machine is in use, portal shows "Machine in use — please wait"
    - LCD shows "Session active — scan bottle"

3. User scans the barcode of the bottle
    - if the barcode is registered in the system, proceed to step 4
    - if not, LCD shows "Unknown bottle" and the user can try again

4. AI verification — camera turns on for 10 seconds
    - AI checks if the object is shaped like a bottle (low confidence threshold, any bottle shape passes)
    - if verified, servo (intake door) opens for 5 seconds, user drops bottle in, servo closes
    - the time corresponding to that bottle is added to the user's session in SQLite
    - LCD shows "Bottle accepted! +XX min"
    - if not verified, LCD shows "No bottle detected" and rejects

5. User can keep inserting more bottles (repeats steps 3-4), time keeps accumulating

6. When done, user taps "Done / Start WiFi" on the portal page
    - the machine session is released (other users can now use it)
    - the RPi adds an iptables rule to allow the user's MAC address through
    - a countdown timer starts on the portal page showing remaining time
    - user can now browse the internet

7. When time runs out
    - the RPi removes the iptables rule, re-blocking the user's MAC
    - user is redirected back to the captive portal page
    - user can insert more bottles to get more time

## Session Persistence

- if a user disconnects from wifi and reconnects, their MAC still has remaining time in SQLite
- sessions expire after 1 day of inactivity (last_seen not updated for 24 hours)
- the machine session (who is actively inserting bottles) auto-releases after 5 minutes of no scans

## Bottle Time Table

| Bottle | Time |
|--------|------|
| water_bottle-500mL | 30 minutes |
| water_bottle-350mL | 10 minutes |
| water_bottle-1L | 45 minutes |
| coke_2L | 75 minutes |
| coke_mismo | 10 minutes |
| pocari_350mL | 10 minutes |
| sprite_1.5L | 60 minutes |
| royal_1.5L | 60 minutes |
| natures_spring_1000ml | 45 minutes |

## How the Captive Portal Works

1. RPi connects to a router via ethernet for internet access
2. nmcli creates a wifi hotspot ("RVM-WiFi") using the built-in wifi chip
3. iptables enables NAT (masquerade) to forward hotspot traffic to the ethernet interface
4. iptables blocks all internet traffic by default — only allowed MACs get through
5. dnsmasq assigns IP addresses and redirects all DNS queries to the RPi
6. when a user connects, their phone's captive portal detection triggers (Flask responds to probe URLs with a 302 redirect)
7. the portal page is served on the RPi (e.g. `192.168.4.1:80`)
8. users are identified by their MAC address — no login needed
9. when a user earns time and taps "Start WiFi", an iptables rule allows their MAC through
10. a background thread checks every 60 seconds and removes expired users (time ran out or 1-day inactivity)

## Integration (Main Script + Flask)

Both the main Python script and the Flask web server share a **SQLite database**:

- **Flask** handles: portal UI, user sessions, iptables rules, session expiry
- **Main script** handles: barcode scanning, AI verification, servo control, LCD display
- **SQLite** stores: user MAC, accumulated time, active session flag, last_seen timestamp

Flow:
1. User taps "Insert Bottles" on portal → Flask writes active_session = user's MAC to SQLite
2. Main script reads active_session from SQLite to know who is inserting
3. When a bottle is verified, main script writes +time to that user's row in SQLite
4. User taps "Start WiFi" → Flask reads their accumulated time, adds iptables rule, clears active_session

Both run as separate systemd services on boot.

## Anti-Abuse

- AI verification prevents scanning a barcode without showing a real bottle
- servo only opens after AI confirms — user can't dump non-bottles in
- one-at-a-time machine access prevents session confusion
- **known gap**: without a load cell, a user could scan a barcode, show a bottle to the camera, then not actually drop it in. The AI can't tell if the bottle was inserted after the door opens. Adding a load cell later would close this gap.

## LCD Messages

| State | LCD Display |
|-------|-------------|
| Idle | "Ready" |
| Session started | "Session active — scan bottle" |
| Barcode accepted | "Bottle: [type] — verifying..." |
| AI verified | "[type] accepted! +XX min" |
| AI failed | "No bottle detected — try again" |
| Unknown barcode | "Unknown bottle — try again" |
| Session released | "Done! Enjoy your WiFi" |
| Machine in use | "In use — please wait" |

## Deployment

- `rvm-main.service` — systemd service for the Python main script (scanning, AI, servo, LCD)
- `rvm-portal.service` — systemd service for the Flask captive portal
- both start on boot, restart on failure

## Future Additions

- **Load cell (HX711)** + **Servo 2 (drop door)**: after servo 1 closes, load cell confirms bottle was inserted, then servo 2 opens to release into collection bin. This closes the anti-abuse gap.
