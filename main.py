"""
Reverse Vending Machine — Barcode + AI Bottle Verification + Relay
Raspberry Pi 5 | NCNN Model | MH-ET Live Scanner V3 | 5V Relay via GPIO

Flow: Scan barcode → Open camera → AI verifies bottle → Relay opens → Repeat
"""

import cv2
import time
import threading
import logging
from datetime import datetime
from ultralytics import YOLO

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/tmp/rvm_main.log'),
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
    from gpiozero import OutputDevice
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False
    print("WARNING: gpiozero not installed — relay disabled")

# ── Config ────────────────────────────────────────────────────────
MODEL_PATH = "best_ncnn_model"
CLASS_NAMES = ["coke_litro", "coke_mismo", "water_bottle-1L", "water_bottle-350mL", "water_bottle-500mL"]
COLORS = [(0, 0, 255), (0, 128, 255), (255, 0, 0), (255, 255, 0), (255, 0, 255)]

RELAY_PIN = 22          # BCM pin (wire via NPN transistor to 5V relay)
RELAY_OPEN_SECS = 5     # how long relay stays open
VERIFY_TIMEOUT = 10     # seconds to wait for AI bottle detection
VERIFY_CONF = 0.50      # minimum confidence for AI verification

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


# ── Barcode Scanner (blocking read, same as test_scanner.py) ─────

def find_scanner():
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


def wait_for_barcode(device):
    """Block until a barcode is scanned. Returns the barcode string."""
    buffer = []
    for event in device.read_loop():
        if event.type != ecodes.EV_KEY or event.value != 1:
            continue
        if event.code in (ecodes.KEY_ENTER, ecodes.KEY_KPENTER):
            barcode = ''.join(buffer)
            buffer.clear()
            if barcode:
                return barcode
        else:
            ch = _KEY_MAP.get(event.code)
            if ch:
                buffer.append(ch)


# ── Relay Control ─────────────────────────────────────────────────

class RelayController:
    """Controls a 5V relay via GPIO (through NPN transistor)."""

    def __init__(self, pin=RELAY_PIN):
        self.relay = None
        if HAS_GPIO:
            try:
                self.relay = OutputDevice(pin, active_high=True, initial_value=False)
                print(f"Relay: initialized on GPIO{pin}")
            except Exception as e:
                print(f"Relay: GPIO init failed ({e}), running without relay")
        else:
            print("Relay: gpiozero not available, running without relay")

    def on(self):
        if self.relay:
            self.relay.on()
        else:
            print("Relay: [simulated] ON")

    def off(self):
        if self.relay:
            self.relay.off()
        else:
            print("Relay: [simulated] OFF")

    def cleanup(self):
        if self.relay:
            self.relay.off()
            self.relay.close()


# ── Camera Thread ─────────────────────────────────────────────────

class CameraThread:
    """Threaded camera capture so frame reading doesn't block inference."""

    def __init__(self, src=0):
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

def run_inference(model, frame, conf):
    """Run YOLO inference and annotate frame. Returns (frame, detected)."""
    results = model.predict(frame, imgsz=640, conf=conf,
                            max_det=1, verbose=False, half=False)[0]
    detected = False
    if results.boxes is not None and len(results.boxes) > 0:
        for box in results.boxes:
            cls_id = int(box.cls[0])
            if cls_id >= len(CLASS_NAMES):
                continue
            detected = True
            box_conf = float(box.conf[0])
            color = COLORS[cls_id % len(COLORS)]
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, f"{CLASS_NAMES[cls_id]} {box_conf:.2f}",
                        (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    return frame, detected


# ── Main ──────────────────────────────────────────────────────────

def main():
    logger.info("="*60)
    logger.info("RVM System Starting")
    logger.info("="*60)

    logger.info("Loading NCNN model from %s", MODEL_PATH)
    model = YOLO(MODEL_PATH, task='segment')
    logger.info("Model loaded successfully")

    scanner_dev = find_scanner()
    if scanner_dev:
        logger.info("Barcode scanner connected: %s", scanner_dev.name)
        scanner_dev.grab()
    else:
        logger.warning("Barcode scanner not found, running without scanner")

    relay = RelayController()

    logger.info("System ready. Waiting for bottles...")
    print("System ready. Ctrl+C to quit.\n")

    try:
        while True:
            # ── Step 1: Wait for barcode scan (blocking, no camera) ──
            logger.debug("Waiting for barcode scan...")
            print("Waiting for barcode scan...")
            if scanner_dev:
                barcode = wait_for_barcode(scanner_dev)
            else:
                barcode = input("No scanner — type barcode manually: ").strip()

            logger.info("Barcode scanned: %s", barcode)
            print(f"Scanned: {barcode}")

            if barcode not in BARCODE_MAP:
                logger.warning("Unknown barcode rejected: %s", barcode)
                print(f"Unknown barcode: {barcode}\n")
                continue

            scanned_type = BARCODE_MAP[barcode]
            logger.info("Barcode accepted: %s -> %s", barcode, scanned_type)
            print(f"Barcode accepted: {scanned_type}")

            # ── Step 2: Open camera and verify with AI ───────────────
            logger.info("Starting AI verification for %s", scanned_type)
            print("Opening camera for verification...")
            cam = CameraThread(0).start()
            if not cam.isOpened():
                logger.error("Failed to open camera")
                print("Error: Could not open camera!\n")
                continue

            logger.debug("Camera opened, warming up...")
            time.sleep(0.3)  # let camera warm up

            verified = False
            verify_start = time.time()

            while time.time() - verify_start < VERIFY_TIMEOUT:
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

            cam.stop()
            cv2.destroyAllWindows()

            if not verified:
                elapsed = time.time() - verify_start
                logger.warning("AI verification timeout after %.2fs - no bottle detected", elapsed)

            # ── Step 3: Relay control ────────────────────────────────
            if verified:
                logger.info("Bottle verified! Opening relay for %ds", RELAY_OPEN_SECS)
                print(f"Bottle verified! Opening relay for {RELAY_OPEN_SECS}s")
                relay.on()
                time.sleep(RELAY_OPEN_SECS)
                relay.off()
                logger.info("Relay closed. Cycle complete.")
                print("Relay closed.")
            else:
                logger.warning("Verification failed - bottle rejected")
                print("Verification failed — no bottle detected.")

            logger.debug("-" * 60)
            print()  # blank line before next cycle

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        print("\nStopping...")
    except Exception as e:
        logger.exception("Unexpected error in main loop: %s", e)
        raise
    finally:
        logger.info("Shutting down system...")
        relay.cleanup()
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
