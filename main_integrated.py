#!/usr/bin/env python3
"""
RVM Main Script - Phase 2 Integration
Barcode scanning + AI verification + 3 servos + Load cell + Time allocation

Flow:
1. User connects to WiFi
2. User presses "Insert Bottles" on portal
3. User scans barcode (QR code)
4. User shows bottle to camera - AI verification (checks if real bottle)
5. If verified:
   a. Servo 1 (intake door) opens and STAYS OPEN
   b. Monitor load cell for weight change (5 second timeout)
   c. If weight detected:
      - Add WiFi time to user's account
      - Open servo 2 (exit door) for 5s, then close
   d. If no weight detected after 5s:
      - Close servo 3 (reject door) to push item out
      - Servo 3 default state is OPEN, closing it routes to reject path
   e. Close intake door (servo 1)
6. Repeat: scan next bottle until user taps "Done" on portal

Note: Time is ONLY credited if weight is detected (bottle actually inserted).
Servo 3 is normally OPEN, and CLOSES to reject items (not opens).
"""

import cv2
import time
import threading
import logging
from enum import Enum
from typing import Optional, Tuple
from ultralytics import YOLO
from datetime import datetime

import db
from utils import format_time

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/tmp/rvm_main_integrated.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

try:
    import evdev
    from evdev import ecodes
    HAS_EVDEV = True
except ImportError:
    HAS_EVDEV = False
    print("WARNING: evdev not installed — barcode scanner disabled")

try:
    from adafruit_servokit import ServoKit
    import board
    import busio
    HAS_SERVOKIT = True
except ImportError:
    HAS_SERVOKIT = False
    logger.warning("adafruit-servokit not installed — servo control disabled")

try:
    from RPLCD.i2c import CharLCD
    HAS_LCD = True
except ImportError:
    HAS_LCD = False
    logger.warning("RPLCD not installed — LCD disabled")

try:
    from hx711 import HX711
    HAS_HX711 = True
except ImportError:
    HAS_HX711 = False
    logger.warning("hx711 not installed — load cell disabled")


# ── Config ────────────────────────────────────────────────────────
# Built-in YOLO COCO model for generic bottle detection
MODEL_PATH = "yolov8n.pt"  # Built-in YOLOv8 nano (fastest)
BOTTLE_CLASS_ID = 39       # COCO dataset class ID for "bottle"

VERIFY_TIMEOUT = 30     # seconds to wait for AI bottle detection
VERIFY_CONF = 0.75      # minimum confidence for AI verification (lower for generic detection)

# LCD Display Messages (DRY - Define once, use everywhere)
LCD_MSG_READY = "Ready"
LCD_MSG_INSERT_BOTTLES = "Tap 'Insert Bottles'"
LCD_MSG_ON_YOUR_PHONE = "on your phone"
LCD_MSG_SESSION_ACTIVE = "Session Active"
LCD_MSG_SCAN_BOTTLE = "Scan bottle"
LCD_MSG_SCAN_NEXT = "Scan next bottle"
LCD_MSG_SESSION_ENDED = "Session Ended"
LCD_MSG_THANK_YOU = "Thank you!"
LCD_MSG_USER_CANCELLED = "User cancelled"
LCD_MSG_WAITING = "Waiting for user..."
LCD_MSG_RVM_READY = "RVM Ready"
LCD_MSG_UNKNOWN_BOTTLE = "Unknown Bottle"
LCD_MSG_TRY_AGAIN = "Try again"
LCD_MSG_VERIFYING = "Verifying..."
LCD_MSG_SHOW_TO_CAMERA = "Show bottle to camera"
LCD_MSG_CAMERA_ERROR = "Camera Error"
LCD_MSG_BOTTLE_VERIFIED = "Bottle Verified!"
LCD_MSG_DROP_BOTTLE = "Drop bottle now"
LCD_MSG_NO_BOTTLE = "No Bottle Detected"
LCD_MSG_PETO_READY = "P.E.T-O Ready"
LCD_MSG_CONNECT_TO = "connect to"
LCD_MSG_WIFI_NAME = "P.E.T.-O WI-FI"
LCD_MSG_GO_TO = "go to"
LCD_MSG_GATEWAY_IP = "10.42.0.1"

# Hardware configuration
# PCA9685 servo controller (I2C0 on GPIO 0/1)
# Note: LCD uses I2C1 (GPIO 2/3), PCA9685 uses separate I2C0 bus
# Requires: dtoverlay=i2c0-pi5 in /boot/firmware/config.txt
# Wiring: PCA9685 SCL→GPIO1 (Pin 28), SDA→GPIO0 (Pin 27)
SERVO1_CHANNEL = 1      # Intake door servo (channel 1 on PCA9685)
SERVO2_CHANNEL = 15     # Exit door servo (channel 15 on PCA9685)
SERVO3_CHANNEL = 14     # Reject/backup servo (channel 14 on PCA9685)

# Continuous rotation servo parameters (MG995 clones)
# These are NOT position servos - they use timed rotation
SERVO_STOP = 91         # Angle that stops servo rotation (calibrated for servos 1 & 2)
SERVO3_STOP = 92        # Angle that stops servo 3 rotation (calibrated separately)

# Servo 1 (Intake door) - REVERSED direction
SERVO1_OPEN_SPEED = 130  # Angle/speed to open intake door (REVERSED)
SERVO1_CLOSE_SPEED = 60  # Angle/speed to close intake door (REVERSED)

# Servo 2 (Exit door) - REVERSED direction
SERVO2_OPEN_SPEED = 130  # Angle/speed to open exit door (REVERSED)
SERVO2_CLOSE_SPEED = 60  # Angle/speed to close exit door (REVERSED)

# Servo 3 (Reject door) - MUCH wider rotation
SERVO3_OPEN_SPEED = 20   # Angle/speed to open reject door (much wider)
SERVO3_CLOSE_SPEED = 160 # Angle/speed to close reject door (much wider)

# Timing for door rotation (seconds) - calibrated from test_open_close.py
SERVO_OPEN_TIME = 0.3   # Time to rotate servo open
SERVO_CLOSE_TIME = 0.3  # Time to rotate servo closed

# Timing for door operations
SERVO2_OPEN_SECS = 5    # Servo 2 stays open (seconds)
WEIGHT_TIMEOUT = 5      # Seconds to wait for weight detection before opening servo 3

# Load cell configuration (HX711)
LOAD_CELL_DT_PIN = 5    # HX711 DOUT pin (BCM)
LOAD_CELL_SCK_PIN = 6   # HX711 PD_SCK pin (BCM)
LOAD_CELL_GAIN = 128    # HX711 gain (128 = max for 1kg load cell)
LOAD_CELL_SCALE = 10    # Calibration scale factor
LOAD_CELL_SAMPLES = 10  # Number of samples to average
WEIGHT_CHANGE_THRESHOLD = 1000  # Raw value change threshold to detect bottle (adjust based on testing)
WEIGHT_CONFIRM_COUNT = 3        # Consecutive readings above threshold to confirm weight (filters noise)

# Map barcode strings to bottle types (fill in real barcodes)
BARCODE_MAP = {
    "4800100123456": "water_bottle-500mL",
    "4800014147083": "water_bottle-350mL",
    "4800602087937": "water_bottle-1L",
    "4800100456789": "coke_2L",
    "4801981118502": "coke_mismo",
    "8997035600010": "pocari_350mL",
    "4801981116270": "sprite_1.5L",
    "4801981116171": "royal_1.5L",
    "4800049720121": "natures_spring_1000ml",
}

# Map bottle types to LCD display names (volume only)
BOTTLE_DISPLAY = {
    "water_bottle-500mL": "500mL",
    "water_bottle-350mL": "350mL",
    "water_bottle-1L": "1L",
    "coke_2L": "2L",
    "coke_mismo": "280mL",
    "pocari_350mL": "350mL",
    "sprite_1.5L": "1.5L",
    "royal_1.5L": "1.5L",
    "natures_spring_1000ml": "1L",
    "coke_litro": "1L",
}


def find_barcode_match(scanned: str) -> Optional[str]:
    """
    Find matching barcode from BARCODE_MAP, handling partial/clipped scans.

    Scanner often clips 1-2 digits from start or end, so we match:
    - Exact match (13 digits)
    - Last 11-12 digits (suffix match)
    - First 11-12 digits (prefix match)

    Args:
        scanned: Barcode string from scanner (may be partial)

    Returns:
        Matched bottle type string, or None if no match found
    """
    # Try exact match first
    if scanned in BARCODE_MAP:
        logger.debug(f"Exact barcode match: {scanned}")
        return BARCODE_MAP[scanned]

    # If barcode is 11-12 digits, try suffix matching (most common clip pattern)
    if 11 <= len(scanned) <= 12:
        for full_barcode, bottle_type in BARCODE_MAP.items():
            # Check if scanned is suffix of full barcode
            if full_barcode.endswith(scanned):
                logger.info(f"Matched clipped barcode: {scanned} -> {full_barcode} ({bottle_type})")
                return bottle_type
            # Check if scanned is prefix of full barcode
            if full_barcode.startswith(scanned):
                logger.info(f"Matched clipped barcode: {scanned} -> {full_barcode} ({bottle_type})")
                return bottle_type
            # Check if scanned is contained in full barcode (middle match)
            if scanned in full_barcode:
                logger.info(f"Matched partial barcode: {scanned} -> {full_barcode} ({bottle_type})")
                return bottle_type

    logger.warning(f"No match found for barcode: {scanned} ({len(scanned)} digits)")
    return None

# evdev keycode → character mapping
_KEY_MAP = {
    # Number row
    ecodes.KEY_0: '0', ecodes.KEY_1: '1', ecodes.KEY_2: '2', ecodes.KEY_3: '3',
    ecodes.KEY_4: '4', ecodes.KEY_5: '5', ecodes.KEY_6: '6', ecodes.KEY_7: '7',
    ecodes.KEY_8: '8', ecodes.KEY_9: '9',
    # Numpad
    ecodes.KEY_KP0: '0', ecodes.KEY_KP1: '1', ecodes.KEY_KP2: '2', ecodes.KEY_KP3: '3',
    ecodes.KEY_KP4: '4', ecodes.KEY_KP5: '5', ecodes.KEY_KP6: '6', ecodes.KEY_KP7: '7',
    ecodes.KEY_KP8: '8', ecodes.KEY_KP9: '9',
    # Letters
    ecodes.KEY_A: 'A', ecodes.KEY_B: 'B', ecodes.KEY_C: 'C', ecodes.KEY_D: 'D',
    ecodes.KEY_E: 'E', ecodes.KEY_F: 'F', ecodes.KEY_G: 'G', ecodes.KEY_H: 'H',
    ecodes.KEY_I: 'I', ecodes.KEY_J: 'J', ecodes.KEY_K: 'K', ecodes.KEY_L: 'L',
    ecodes.KEY_M: 'M', ecodes.KEY_N: 'N', ecodes.KEY_O: 'O', ecodes.KEY_P: 'P',
    ecodes.KEY_Q: 'Q', ecodes.KEY_R: 'R', ecodes.KEY_S: 'S', ecodes.KEY_T: 'T',
    ecodes.KEY_U: 'U', ecodes.KEY_V: 'V', ecodes.KEY_W: 'W', ecodes.KEY_X: 'X',
    ecodes.KEY_Y: 'Y', ecodes.KEY_Z: 'Z',
    # Symbols
    ecodes.KEY_MINUS: '-', ecodes.KEY_DOT: '.', ecodes.KEY_SLASH: '/',
    ecodes.KEY_SPACE: ' ', ecodes.KEY_KPDOT: '.', ecodes.KEY_KPMINUS: '-',
    ecodes.KEY_KPSLASH: '/',
} if HAS_EVDEV else {}


# ── State Machine ─────────────────────────────────────────────────

class RVMState(Enum):
    """RVM state machine states"""
    IDLE = 1           # Waiting for machine lock
    LOCKED = 2         # Machine locked, waiting for barcode
    VERIFYING = 3      # AI verification in progress
    PROCESSING = 4     # Door open, bottle being inserted


# ── Servo Controller (Continuous Rotation) ───────────────────────

class ServoController:
    """
    Controls a CONTINUOUS ROTATION servo motor via PCA9685.
    Uses timed rotation instead of position control.
    """

    def __init__(self, kit: Optional['ServoKit'], channel: int, stop_angle: int,
                 open_speed: int, close_speed: int, open_time: float,
                 close_time: float, name: str = "servo") -> None:
        """
        Args:
            kit: ServoKit instance (shared across all servos) or None if hardware unavailable
            channel: PCA9685 channel number (0-15)
            stop_angle: Angle that stops the servo (e.g., 91°)
            open_speed: Angle to rotate for opening (e.g., 60°)
            close_speed: Angle to rotate for closing (e.g., 120°)
            open_time: Seconds to rotate when opening
            close_time: Seconds to rotate when closing
            name: Descriptive name for logging
        """
        self.kit = kit
        self.channel = channel
        self.stop_angle = stop_angle
        self.open_speed = open_speed
        self.close_speed = close_speed
        self.open_time = open_time
        self.close_time = close_time
        self.name = name

        # Initialize to stopped position
        if self.kit:
            try:
                self.stop()
                logger.info("Servo '%s': initialized on channel %d (continuous rotation, stop=%d°)",
                           name, channel, stop_angle)
            except Exception as e:
                logger.error("Servo '%s': init failed (%s)", name, e)
        else:
            logger.warning("Servo '%s': ServoKit not available", name)

    def open(self) -> None:
        """
        Rotate servo to open door (timed rotation).
        Rotates for open_time seconds, then stops.
        """
        if self.kit:
            try:
                logger.debug("Servo '%s': OPENING (rotate at %d° for %.1fs)",
                           self.name, self.open_speed, self.open_time)
                self.kit.servo[self.channel].angle = self.open_speed
                time.sleep(self.open_time)
                self.stop()
                logger.debug("Servo '%s': OPEN complete", self.name)
            except Exception as e:
                logger.error("Servo '%s': open failed (%s)", self.name, e)
        else:
            logger.debug("Servo '%s': [simulated] OPEN", self.name)

    def close(self) -> None:
        """
        Rotate servo to close door (timed rotation).
        Rotates for close_time seconds, then stops.
        """
        if self.kit:
            try:
                logger.debug("Servo '%s': CLOSING (rotate at %d° for %.1fs)",
                           self.name, self.close_speed, self.close_time)
                self.kit.servo[self.channel].angle = self.close_speed
                time.sleep(self.close_time)
                self.stop()
                logger.debug("Servo '%s': CLOSED complete", self.name)
            except Exception as e:
                logger.error("Servo '%s': close failed (%s)", self.name, e)
        else:
            logger.debug("Servo '%s': [simulated] CLOSED", self.name)

    def stop(self) -> None:
        """Stop servo rotation immediately."""
        if self.kit:
            try:
                self.kit.servo[self.channel].angle = self.stop_angle
                logger.debug("Servo '%s': STOPPED (%d°)", self.name, self.stop_angle)
            except Exception as e:
                logger.error("Servo '%s': stop failed (%s)", self.name, e)

    def cleanup(self) -> None:
        """Stop servo rotation."""
        if self.kit:
            try:
                self.stop()
                logger.info("Servo '%s': cleaned up (stopped)", self.name)
            except Exception as e:
                logger.warning("Servo '%s': cleanup error (%s)", self.name, e)


# ── LCD Display ───────────────────────────────────────────────────

class LCDDisplay:
    """4x20 I2C LCD display with graceful fallback."""

    def __init__(self) -> None:
        self.lcd = None
        if HAS_LCD:
            try:
                self.lcd = CharLCD('PCF8574', 0x27, cols=20, rows=4)
                self.lcd.clear()
                logger.info("LCD: initialized")
            except Exception as e:
                logger.warning(f"LCD: init failed ({e}), running without LCD")
        else:
            logger.warning("LCD: RPLCD not available, running without LCD")

    def display(self, line1: str = "", line2: str = "", line3: str = "", line4: str = "") -> None:
        """
        Display up to 4 lines on 20x4 LCD.
        Lines are automatically truncated to 20 characters.
        """
        if not self.lcd:
            return  # Silent fail if hardware unavailable

        try:
            self.lcd.clear()
            self.lcd.cursor_pos = (0, 0)
            self.lcd.write_string(line1[:20])
            if line2:
                self.lcd.cursor_pos = (1, 0)
                self.lcd.write_string(line2[:20])
            if line3:
                self.lcd.cursor_pos = (2, 0)
                self.lcd.write_string(line3[:20])
            if line4:
                self.lcd.cursor_pos = (3, 0)
                self.lcd.write_string(line4[:20])
        except Exception as e:
            logger.warning(f"LCD error: {e}")


# ── LCD Helper Functions ─────────────────────────────────────────

def show_session_active(lcd: LCDDisplay, mac: str) -> None:
    """Display session active screen with user's MAC address."""
    lcd.display(
        line1=LCD_MSG_SESSION_ACTIVE,
        line2=f"MAC: {mac[-8:]}",
        line4=LCD_MSG_SCAN_BOTTLE
    )


def show_ready_screen(lcd: LCDDisplay) -> None:
    """Display WiFi connection instructions."""
    lcd.display(
        line1=LCD_MSG_CONNECT_TO,
        line2=LCD_MSG_WIFI_NAME,
        line3=LCD_MSG_GO_TO,
        line4=LCD_MSG_GATEWAY_IP
    )


def show_session_ended(lcd: LCDDisplay) -> None:
    """Display session ended screen."""
    lcd.display(
        line1=LCD_MSG_SESSION_ENDED,
        line2=LCD_MSG_THANK_YOU
    )


# ── Barcode Scanner ───────────────────────────────────────────────

def find_scanner() -> Optional['evdev.InputDevice']:
    """Find the barcode scanner among /dev/input/ devices."""
    if not HAS_EVDEV:
        return None
    found = None
    for path in evdev.list_devices():
        dev = evdev.InputDevice(path)
        name_lower = dev.name.lower()
        if any(kw in name_lower for kw in ("barcode", "scanner", "mh-et", "wch")):
            found = dev
            break
        dev.close()
    if found:
        return found
    print("Available input devices:")
    for path in evdev.list_devices():
        dev = evdev.InputDevice(path)
        print(f"  {dev.path}: {dev.name}")
        dev.close()
    return None


def wait_for_barcode(device: 'evdev.InputDevice', timeout: Optional[float] = None) -> Optional[str]:
    """
    Block until a barcode is scanned. Returns the barcode string.
    If timeout is specified and no barcode is scanned, returns None.
    """
    buffer = []
    start_time = time.time()
    last_key_time = start_time

    for event in device.read_loop():
        current_time = time.time()

        if timeout and (current_time - start_time) > timeout:
            return None

        if event.type != ecodes.EV_KEY or event.value != 1:
            continue

        # Clear buffer if more than 2 seconds since last keypress (stale data)
        if buffer and (current_time - last_key_time) > 2.0:
            logger.debug("Clearing stale barcode buffer")
            buffer.clear()

        last_key_time = current_time

        if event.code in (ecodes.KEY_ENTER, ecodes.KEY_KPENTER):
            barcode = ''.join(buffer)
            buffer.clear()
            # Validate barcode (11-13 characters for typical barcodes, allowing for clipped scans)
            if barcode and 11 <= len(barcode) <= 13:
                logger.debug(f"Barcode scanned: {barcode} ({len(barcode)} chars)")
                return barcode
            elif barcode:
                logger.warning(f"Barcode invalid length, ignoring: {barcode} ({len(barcode)} chars, need 11-13)")
        else:
            ch = _KEY_MAP.get(event.code)
            if ch:
                buffer.append(ch)


# ── Camera Thread ─────────────────────────────────────────────────

class CameraThread:
    """Threaded camera capture so frame reading doesn't block inference."""

    def __init__(self, src: int = 0) -> None:
        self.cap = cv2.VideoCapture(src)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.ret, self.frame = self.cap.read()
        self.lock = threading.Lock()
        self.stopped = False

    def start(self):
        threading.Thread(target=self._update, daemon=True).start()
        return self

    def _update(self):
        while not self.stopped:
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.frame = frame
                    self.ret = ret
            else:
                time.sleep(0.001)

    def read(self):
        with self.lock:
            if self.frame is None:
                return self.ret, None
            return self.ret, self.frame.copy()

    def stop(self):
        self.stopped = True
        self.cap.release()

    def isOpened(self):
        return self.cap.isOpened()


# ── Inference Helper ──────────────────────────────────────────────

def run_inference(model: YOLO, frame, conf: float) -> Tuple:
    """Run YOLO inference for bottle detection. Returns (frame, detected)."""
    # Only detect bottles (class 39 in COCO)
    results = model.predict(frame, imgsz=640, conf=conf,
                            classes=[BOTTLE_CLASS_ID],  # Filter for bottles only
                            max_det=1, verbose=False, half=False)[0]
    detected = False
    if results.boxes is not None and len(results.boxes) > 0:
        for box in results.boxes:
            detected = True
            box_conf = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            # Draw bounding box in green for detected bottle
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
            cv2.putText(frame, f"BOTTLE {box_conf:.2f}",
                        (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    return frame, detected


# ── Main ──────────────────────────────────────────────────────────

def main() -> None:
    """Main RVM control loop."""
    logger.info("="*60)
    logger.info("RVM Main Script - Phase 2 Starting")
    logger.info("="*60)

    logger.info("Loading built-in YOLO model: %s", MODEL_PATH)
    logger.info("(First run will download the model - may take a moment)")
    model = YOLO(MODEL_PATH)  # Built-in detection model
    logger.info("Model loaded successfully - generic bottle detection enabled")

    scanner_dev = find_scanner()
    if scanner_dev:
        logger.info("Barcode scanner connected: %s", scanner_dev.name)
        scanner_dev.grab()
    else:
        logger.warning("Barcode scanner not found, running without scanner")

    lcd = LCDDisplay()

    # Initialize PCA9685 ServoKit on I2C0 (GPIO 0/1)
    # Requires: dtoverlay=i2c0-pi5 in /boot/firmware/config.txt
    kit = None
    if HAS_SERVOKIT:
        try:
            # Use I2C bus 0 (GPIO 0/1 on RPi 5 with i2c0-pi5 overlay)
            i2c_bus = busio.I2C(board.D1, board.D0)  # SCL=GPIO1, SDA=GPIO0
            kit = ServoKit(channels=16, i2c=i2c_bus, address=0x40)
            logger.info("PCA9685: initialized on I2C0 (GPIO 0/1, 16 channels)")
        except Exception as e:
            logger.error("PCA9685 init failed: %s", e)
    else:
        logger.warning("ServoKit not available, running without servos")

    # Initialize all three servo motors
    servo1 = ServoController(kit, SERVO1_CHANNEL, SERVO_STOP,
                            SERVO1_OPEN_SPEED, SERVO1_CLOSE_SPEED,
                            SERVO_OPEN_TIME, SERVO_CLOSE_TIME, "intake")

    servo2 = ServoController(kit, SERVO2_CHANNEL, SERVO_STOP,
                            SERVO2_OPEN_SPEED, SERVO2_CLOSE_SPEED,
                            SERVO_OPEN_TIME, SERVO_CLOSE_TIME, "exit")

    servo3 = ServoController(kit, SERVO3_CHANNEL, SERVO3_STOP,
                            SERVO3_OPEN_SPEED, SERVO3_CLOSE_SPEED,
                            SERVO_OPEN_TIME, SERVO_CLOSE_TIME, "reject")

    # Initialize load cell (HX711)
    hx = None
    if HAS_HX711:
        try:
            hx = HX711(dout_pin=LOAD_CELL_DT_PIN, pd_sck_pin=LOAD_CELL_SCK_PIN, gain=LOAD_CELL_GAIN)
            # Test read to verify load cell is connected
            test_data = hx.get_raw_data(times=3)
            if not test_data:
                raise RuntimeError("No data from load cell")
            logger.info("Load cell: initialized (DT=GPIO%d, SCK=GPIO%d, test read: %.0f)",
                       LOAD_CELL_DT_PIN, LOAD_CELL_SCK_PIN, sum(test_data) / len(test_data))
        except Exception as e:
            logger.error("Load cell init failed: %s", e)
            hx = None
    else:
        logger.warning("HX711 not available, running without load cell")

    # Set servo 3 (reject door) to default OPEN position
    # It will be closed to reject items when no weight is detected
    logger.info("Setting servo 3 (reject) to default OPEN position")
    servo3.open()

    lcd.display(LCD_MSG_PETO_READY, LCD_MSG_WAITING)

    logger.info("System ready. Press Ctrl+C to quit.")
    logger.info("View logs: tail -f /tmp/rvm_main_integrated.log")

    try:
        while True:
            # ── Step 1: Wait for machine to be locked ────────────
            show_ready_screen(lcd)
            logger.debug("Waiting for machine lock...")

            while True:
                machine_state = db.get_machine_state()
                if machine_state and machine_state['active_mac']:
                    active_mac = machine_state['active_mac']
                    logger.info("🔒 Machine locked to %s", active_mac)
                    show_session_active(lcd, active_mac)
                    break
                time.sleep(0.5)  # Poll every 0.5s for faster response

            # ── Step 2: Wait for barcode scan (with timeout check) ───
            while True:
                # Check if machine is still locked (poll more frequently)
                machine_state = db.get_machine_state()
                if not machine_state or not machine_state['active_mac']:
                    logger.info("Machine lock released by user - session ended")
                    show_session_ended(lcd)
                    time.sleep(2)
                    break

                active_mac = machine_state['active_mac']

                # Check frequently without blocking on barcode scan
                logger.debug("Waiting for barcode scan...")

                if scanner_dev:
                    barcode = wait_for_barcode(scanner_dev, timeout=0.2)
                    if not barcode:
                        # Timeout - check machine state again (every 0.2s for fast LCD updates)
                        continue
                else:
                    barcode = input("No scanner — type barcode manually: ").strip()

                logger.info("Barcode scanned: %s", barcode)

                # Find matching bottle type (handles partial/clipped barcodes)
                scanned_type = find_barcode_match(barcode)
                if not scanned_type:
                    logger.warning("Unknown barcode rejected: %s", barcode)
                    lcd.display(
                        line1=LCD_MSG_UNKNOWN_BOTTLE,
                        line2=LCD_MSG_TRY_AGAIN,
                        line4=f"Barcode: {barcode[:12]}"
                    )
                    time.sleep(2)
                    show_session_active(lcd, active_mac)
                    continue

                bottle_time = db.get_bottle_time(scanned_type)
                logger.info("Barcode accepted: %s -> %s (%.1f min)", barcode, scanned_type, bottle_time)

                # ── Step 3: Open camera and verify with AI ───────────
                bottle_display = BOTTLE_DISPLAY.get(scanned_type, scanned_type)
                lcd.display(
                    line1=LCD_MSG_VERIFYING,
                    line2=bottle_display,
                    line4=LCD_MSG_SHOW_TO_CAMERA
                )
                logger.info("Starting AI verification for %s", scanned_type)

                cam = CameraThread(0).start()
                if not cam.isOpened():
                    logger.error("Failed to open camera")
                    lcd.display(
                        line1=LCD_MSG_CAMERA_ERROR,
                        line2=LCD_MSG_TRY_AGAIN
                    )
                    time.sleep(2)
                    show_session_active(lcd, active_mac)
                    continue

                logger.debug("Camera opened, warming up...")
                time.sleep(0.3)  # let camera warm up

                verified = False
                verify_start = time.time()

                while time.time() - verify_start < VERIFY_TIMEOUT:
                    # Check if session was cancelled during verification
                    machine_state = db.get_machine_state()
                    if not machine_state or not machine_state['active_mac']:
                        logger.info("Machine lock released during verification")
                        cam.stop()
                        cv2.destroyAllWindows()
                        lcd.display(
                            line1=LCD_MSG_SESSION_ENDED,
                            line2=LCD_MSG_USER_CANCELLED
                        )
                        time.sleep(1.5)
                        lcd.display(LCD_MSG_RVM_READY, LCD_MSG_WAITING)
                        time.sleep(0.5)
                        break

                    ret, frame = cam.read()
                    if not ret or frame is None:
                        continue

                    frame, detected = run_inference(model, frame, VERIFY_CONF)

                    # Show status overlay
                    remaining = max(0, VERIFY_TIMEOUT - (time.time() - verify_start))
                    h = frame.shape[0]
                    cv2.putText(frame, f"Verifying: {scanned_type} ({remaining:.0f}s)",
                                (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    cv2.imshow("RVM - Bottle Detection", frame)
                    cv2.waitKey(1)

                    if detected:
                        verified = True
                        elapsed = time.time() - verify_start
                        logger.info("Bottle detected by AI (%.2fs)", elapsed)
                        break

                # Check if we broke out due to session end
                machine_state = db.get_machine_state()
                if not machine_state or not machine_state['active_mac']:
                    # Session ended during verification - skip the rest
                    cam.stop()
                    cv2.destroyAllWindows()
                    break

                cam.stop()
                cv2.destroyAllWindows()

                if not verified:
                    elapsed = time.time() - verify_start
                    logger.warning("AI verification timeout after %.2fs - no bottle detected", elapsed)

                # ── Step 4: Open Intake Door (After AI Verification) ─
                if verified:
                    bottle_display = BOTTLE_DISPLAY.get(scanned_type, scanned_type)

                    # Prepare time calculation for later use
                    whole_minutes = int(bottle_time)
                    decimal_part = bottle_time - whole_minutes
                    additional_seconds = int(decimal_part * 100)
                    bottle_seconds = (whole_minutes * 60) + additional_seconds
                    bottle_time_display = format_time(bottle_seconds)

                    logger.info("✓ Bottle verified by AI: %s (%s potential time)", scanned_type, bottle_time_display)

                    lcd.display(
                        line1=LCD_MSG_BOTTLE_VERIFIED,
                        line2=bottle_display,
                        line3=LCD_MSG_DROP_BOTTLE
                    )
                    time.sleep(1.5)

                    # ── Step 5: Open Intake Door and Keep Open ───────────
                    logger.info("Opening intake door (servo 1) - keeping open")
                    lcd.display(
                        line1=LCD_MSG_DROP_BOTTLE,
                        line2="Intake door open",
                        line3="Insert bottle now..."
                    )
                    servo1.open()
                    logger.info("Intake door open, monitoring weight...")

                    # ── Step 6: Monitor load cell for weight change ──────
                    weight_detected = False
                    baseline_weight = None

                    if hx:
                        try:
                            # Tare: reset + take multiple baseline readings for stability
                            hx.reset()
                            time.sleep(0.3)
                            # Take 3 separate tare readings and average them
                            tare_readings = []
                            for _ in range(3):
                                d = hx.get_raw_data(times=LOAD_CELL_SAMPLES)
                                if d:
                                    tare_readings.append(sum(d) / len(d))
                                time.sleep(0.05)
                            baseline_weight = sum(tare_readings) / len(tare_readings) if tare_readings else 0
                            logger.info("Load cell tared (3x avg). Baseline: %.0f (raw)", baseline_weight)

                            lcd.display(
                                line1=LCD_MSG_DROP_BOTTLE,
                                line2="Monitoring weight...",
                                line3=f"Waiting {WEIGHT_TIMEOUT}s"
                            )

                            confirm_count = 0  # Consecutive readings above threshold
                            weight_start = time.time()
                            while time.time() - weight_start < WEIGHT_TIMEOUT:
                                current_data = hx.get_raw_data(times=LOAD_CELL_SAMPLES)
                                current_weight = sum(current_data) / len(current_data) if current_data else 0
                                weight_change = abs(current_weight - baseline_weight)

                                logger.debug("Weight: %.0f (change: %.0f, confirm: %d/%d)",
                                           current_weight, weight_change, confirm_count, WEIGHT_CONFIRM_COUNT)

                                if weight_change >= WEIGHT_CHANGE_THRESHOLD:
                                    confirm_count += 1
                                    if confirm_count >= WEIGHT_CONFIRM_COUNT:
                                        weight_detected = True
                                        elapsed = time.time() - weight_start
                                        logger.info("✓ Weight confirmed! Change: %.0f (%d consecutive, %.2fs)",
                                                   weight_change, confirm_count, elapsed)
                                        break
                                else:
                                    if confirm_count > 0:
                                        logger.debug("Weight dropped below threshold, resetting (was %d/%d)",
                                                   confirm_count, WEIGHT_CONFIRM_COUNT)
                                    confirm_count = 0

                                time.sleep(0.1)
                        except Exception as e:
                            logger.error("Load cell error: %s", e)
                            weight_detected = False
                    else:
                        # No load cell - cannot detect weight, reject item
                        logger.error("❌ No load cell available - cannot verify bottle insertion!")
                        logger.error("   Bottle will be rejected. Check HX711 wiring:")
                        logger.error("   - DT (data) → GPIO %d", LOAD_CELL_DT_PIN)
                        logger.error("   - SCK (clock) → GPIO %d", LOAD_CELL_SCK_PIN)
                        logger.error("   - VCC → 5V, GND → GND")
                        time.sleep(WEIGHT_TIMEOUT)
                        weight_detected = False  # Cannot detect without load cell

                    # ── Step 7: Route bottle and add time based on weight ─
                    if weight_detected:
                        # Bottle detected - add time and send to exit
                        logger.info("✓ Bottle inserted! Adding %s to %s", bottle_time_display, active_mac)

                        # Add time to user's session (only after weight detected)
                        db.add_time_to_user(active_mac, bottle_time)

                        # Refresh machine lock (reset timeout)
                        db.refresh_machine_lock(active_mac)

                        # Get updated total
                        user = db.get_user(active_mac)
                        total_seconds = user['accumulated_time']
                        total_time_display = format_time(total_seconds)

                        logger.info("Total accumulated time for %s: %s", active_mac, total_time_display)

                        lcd.display(
                            line1=bottle_display,
                            line2=f"Accepted! +{bottle_time_display}",
                            line4=f"Total: {total_time_display}"
                        )
                        time.sleep(2)

                        # Open exit door (servo 2)
                        logger.info("Opening exit door (servo 2) for %ds", SERVO2_OPEN_SECS)
                        lcd.display(
                            line1="Processing bottle...",
                            line2="Exit door opening",
                            line4=f"Total: {total_time_display}"
                        )
                        servo2.open()
                        time.sleep(SERVO2_OPEN_SECS)
                        servo2.close()
                        logger.info("Exit door closed")

                    else:
                        # No weight detected - reject flow
                        logger.warning("No weight detected after %ds - rejecting item", WEIGHT_TIMEOUT)
                        lcd.display(
                            line1="No bottle detected",
                            line2="Rejecting item..."
                        )
                        # Step 1: Reject servo triggers for 5 seconds
                        servo3.close()
                        logger.info("Servo 3 closed (rejecting)")
                        time.sleep(5)
                        # Step 2: Exit servo opens for 5 seconds
                        servo2.open()
                        logger.info("Servo 2 opened (exit for rejected item)")
                        time.sleep(5)
                        # Step 3: All servos close
                        servo2.close()
                        servo3.open()  # Return to default OPEN position
                        logger.info("All servos closed (reject flow complete)")

                    # Close intake door (servo 1) after processing
                    servo1.close()
                    logger.info("Intake door closed")

                    # Re-tare load cell after each bottle cycle
                    if hx:
                        try:
                            hx.reset()
                            time.sleep(0.2)
                            logger.info("Load cell re-tared after bottle cycle")
                        except Exception as e:
                            logger.warning("Load cell re-tare failed: %s", e)

                    # Show session active screen
                    if weight_detected:
                        lcd.display(
                            line1=LCD_MSG_SESSION_ACTIVE,
                            line2=f"MAC: {active_mac[-8:]}",
                            line4=LCD_MSG_SCAN_NEXT
                        )
                    else:
                        lcd.display(
                            line1="Item rejected",
                            line2="No weight detected",
                            line4=LCD_MSG_SCAN_NEXT
                        )
                        time.sleep(2)
                        show_session_active(lcd, active_mac)

                else:
                    logger.warning("Verification failed - bottle rejected for %s", active_mac)
                    lcd.display(
                        line1=LCD_MSG_NO_BOTTLE,
                        line2=LCD_MSG_TRY_AGAIN,
                        line4=LCD_MSG_SHOW_TO_CAMERA
                    )
                    time.sleep(2)
                    show_session_active(lcd, active_mac)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received - shutting down")
    except Exception as e:
        logger.exception("Unexpected error in main loop: %s", e)
        raise
    finally:
        logger.info("Shutting down system...")
        lcd.display("System Stopped")
        servo1.cleanup()
        servo2.cleanup()
        servo3.cleanup()
        if hx:
            try:
                hx.power_down()
                logger.info("Load cell powered down")
            except Exception as e:
                logger.warning("Load cell cleanup error: %s", e)
        if scanner_dev:
            try:
                scanner_dev.ungrab()
                logger.debug("Scanner ungrabbed")
            except OSError:
                pass
        cv2.destroyAllWindows()
        logger.info("System stopped")
        logger.info("="*60)


if __name__ == "__main__":
    main()
