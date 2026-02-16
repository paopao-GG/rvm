Reverse Vending Machine (RVM) - main.py Code Explanation
========================================================

OVERVIEW
--------
A Reverse Vending Machine system running on Raspberry Pi 5 that:
1. Scans a bottle's barcode to check if it's a registered bottle type
2. Uses AI (YOLO) to visually confirm it's actually a bottle
3. Opens a relay (e.g. to drop the bottle into a bin) if verified

HARDWARE
--------
- Raspberry Pi 5
- MH-ET Live Scanner V3 (USB barcode scanner, acts as HID keyboard)
- 5V Relay Module on GPIO22 (wired via NPN transistor for 3.3V->5V level shift)
- USB Camera (for AI bottle detection)

WIRING
------
TESTED IT AND IT WORKS RAW, DIRECTLY CONNECT THE IN OF THE RELAY TO THE GPIO, NO NEED TRANSISTORS
Relay:
  RPi5 GPIO22 (pin 15) --> 1k resistor --> NPN transistor base
  Transistor collector  --> Relay IN pin
  Transistor emitter    --> GND
  Relay VCC             --> RPi5 5V (pin 2 or 4)
  Relay GND             --> RPi5 GND

If the relay triggers at 3.3V (test first), you can skip the transistor and
wire GPIO22 directly to Relay IN.

Scanner:
  Just plug into any USB port via micro-USB cable.

DEPENDENCIES
------------
  pip install ultralytics opencv-python evdev gpiozero
  sudo apt install python3-lgpio

HOW TO RUN
----------
  python main.py

If the barcode scanner needs exclusive access (grab), run with sudo:
  sudo /home/raspi/rvm/venv/bin/python main.py


PROGRAM FLOW
------------

  +---------------------------+
  |  Load YOLO NCNN model     |
  |  Find barcode scanner     |
  |  Initialize relay GPIO22  |
  +---------------------------+
              |
              v
  +---------------------------+
  |  STEP 1: WAIT FOR SCAN   |  <-- Blocks here, no camera running
  |  (barcode scanner reads)  |
  +---------------------------+
              |
         barcode read
              |
              v
  +---------------------------+
  |  Check BARCODE_MAP        |
  |  Is it a registered       |  -- NO --> print "Unknown barcode", loop back
  |  bottle type?             |
  +---------------------------+
              |
             YES
              |
              v
  +---------------------------+
  |  STEP 2: OPEN CAMERA      |
  |  Run YOLO inference        |  <-- 10 second timeout
  |  Looking for any bottle    |
  |  with confidence >= 0.50   |
  +---------------------------+
              |
        bottle detected?
         /          \
       YES           NO (timeout)
        |              |
        v              v
  +-----------+   +------------------+
  |  STEP 3:  |   | "Verification    |
  |  Relay ON |   |  failed"         |
  |  (5 sec)  |   +------------------+
  |  Relay OFF|            |
  +-----------+            |
        |                  |
        +------+  +--------+
               |  |
               v  v
        (loop back to Step 1)


CODE STRUCTURE
--------------

CONFIG (lines 28-46)
  MODEL_PATH       - Path to YOLO NCNN model folder
  CLASS_NAMES      - Bottle classes the model was trained on
  RELAY_PIN        - GPIO pin number (BCM) for the relay
  RELAY_OPEN_SECS  - How long the relay stays open (5 seconds)
  VERIFY_TIMEOUT   - How long AI has to detect a bottle (10 seconds)
  VERIFY_CONF      - Minimum AI confidence to accept (0.50)
  BARCODE_MAP      - Dictionary mapping barcode strings to bottle type names

_KEY_MAP (lines 48-70)
  Maps Linux evdev keycodes to characters. Includes both number row
  (KEY_0-KEY_9) and numpad (KEY_KP0-KEY_KP9) since the MH-ET scanner
  may output either type depending on its configuration.

find_scanner() (lines 75-94)
  Searches /dev/input/ devices for the barcode scanner by name.
  Looks for keywords: "barcode", "scanner", "mh-et", "wch".
  The MH-ET scanner shows up as "WCH.CN 8 Serial To HID".
  Closes non-matching devices to avoid file descriptor leaks.

wait_for_barcode() (lines 97-111)
  Blocking function that reads HID keyboard events from the scanner.
  Accumulates characters in a buffer until Enter (KEY_ENTER or KEY_KPENTER)
  is pressed, then returns the complete barcode string.
  This runs in the main thread with no camera active to avoid input conflicts.

RelayController (lines 116-145)
  Wraps gpiozero OutputDevice for the relay.
  - on()      : activates the relay
  - off()     : deactivates the relay
  - cleanup() : turns off and releases the GPIO pin
  Gracefully degrades if gpiozero is not available (prints simulated output).

CameraThread (lines 150-188)
  Runs camera capture in a background thread so frame reading doesn't
  block YOLO inference. Uses a lock to safely share frames between
  the capture thread and main thread. Copies frames on read to prevent
  torn reads.

run_inference() (lines 193-210)
  Runs YOLO prediction on a single frame.
  Draws bounding boxes and class labels on detected bottles.
  Returns the annotated frame and a boolean (was a bottle detected?).

main() (lines 215-308)
  The main loop with 3 sequential steps:

  Step 1 - Barcode Scan:
    Blocks on wait_for_barcode(). No camera is running.
    Checks the scanned string against BARCODE_MAP.
    Unknown barcodes are rejected and it loops back.

  Step 2 - AI Verification:
    Opens the camera and runs YOLO inference every frame.
    Shows a live preview with "Verifying: [type] (Xs)" overlay.
    If any registered bottle class is detected with confidence >= 0.50,
    verification passes. Times out after 10 seconds.

  Step 3 - Relay:
    If verified: relay ON for 5 seconds, then OFF.
    If not verified: prints failure message.
    Then loops back to Step 1.


REGISTERED BARCODES
-------------------
  4800100123456 -> water_bottle-500mL
  4800014147083 -> water_bottle-350mL
  4800602087937 -> water_bottle-1L
  4800100456789 -> coke_2L
  4801981118502 -> coke_mismo
  8997035600010 -> pocari_350mL

To add new bottles: scan the barcode with test_scanner.py to get the
exact string, then add it to the BARCODE_MAP dictionary in main.py.


TESTING UTILITIES
-----------------
  test_scanner.py  - Standalone barcode scanner test.
                     Prints exactly what the scanner reads.
                     Use this to find barcode strings for BARCODE_MAP.

  Relay test:
    sudo python -c "
    from gpiozero import OutputDevice
    from time import sleep
    r = OutputDevice(22)
    print('ON'); r.on(); sleep(3)
    print('OFF'); r.off(); r.close()
    "


GRACEFUL DEGRADATION
--------------------
The system runs even without hardware connected:
- No scanner: falls back to manual keyboard input
- No GPIO/relay: prints simulated ON/OFF messages
- No camera: skips verification and loops back
