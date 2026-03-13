"""
Dual YOLO Verification Module
Combines custom NCNN model with built-in YOLO COCO bottle detection
"""

from ultralytics import YOLO
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class DualBottleVerifier:
    """
    Dual verification using custom NCNN model + built-in YOLO COCO model.
    Provides higher reliability by requiring both models to detect a bottle.
    """

    def __init__(self, custom_model_path: str = "best_ncnn_model",
                 custom_conf: float = 0.60,
                 builtin_model: str = "yolov8n.pt",
                 builtin_conf: float = 0.50,
                 mode: str = "dual"):
        """
        Args:
            custom_model_path: Path to your custom NCNN model
            custom_conf: Confidence threshold for custom model
            builtin_model: Built-in YOLO model (yolov8n.pt, yolov8s.pt, yolov8m.pt)
            builtin_conf: Confidence threshold for built-in model
            mode: Verification mode - "dual" (both must detect), "fallback", or "custom_only"
        """
        self.custom_conf = custom_conf
        self.builtin_conf = builtin_conf
        self.mode = mode
        self.BOTTLE_CLASS_ID = 39  # COCO dataset bottle class

        # Load custom model
        logger.info(f"Loading custom model: {custom_model_path}")
        self.custom_model = YOLO(custom_model_path, task='segment')
        logger.info("✓ Custom model loaded")

        # Load built-in model if needed
        self.builtin_model = None
        if mode in ["dual", "fallback"]:
            logger.info(f"Loading built-in model: {builtin_model}")
            self.builtin_model = YOLO(builtin_model)
            logger.info("✓ Built-in model loaded")

    def verify(self, frame) -> Tuple[bool, dict]:
        """
        Verify if frame contains a bottle using configured mode.

        Args:
            frame: Image frame from camera

        Returns:
            Tuple of (verified: bool, info: dict)
            info contains: {
                'custom_detected': bool,
                'builtin_detected': bool,
                'custom_conf': float,
                'builtin_conf': float,
                'method': str
            }
        """
        # Run custom model
        custom_results = self.custom_model.predict(
            frame,
            imgsz=640,
            conf=self.custom_conf,
            max_det=1,
            verbose=False,
            half=False
        )[0]

        custom_detected = False
        custom_conf = 0.0
        if custom_results.boxes is not None and len(custom_results.boxes) > 0:
            custom_detected = True
            custom_conf = float(custom_results.boxes[0].conf[0])

        # If custom_only mode, return immediately
        if self.mode == "custom_only":
            return custom_detected, {
                'custom_detected': custom_detected,
                'builtin_detected': False,
                'custom_conf': custom_conf,
                'builtin_conf': 0.0,
                'method': 'custom_only'
            }

        # Run built-in model
        builtin_results = self.builtin_model.predict(
            frame,
            imgsz=640,
            conf=self.builtin_conf,
            classes=[self.BOTTLE_CLASS_ID],
            max_det=1,
            verbose=False,
            half=False
        )[0]

        builtin_detected = False
        builtin_conf = 0.0
        if builtin_results.boxes is not None and len(builtin_results.boxes) > 0:
            builtin_detected = True
            builtin_conf = float(builtin_results.boxes[0].conf[0])

        # Determine final verification based on mode
        if self.mode == "dual":
            # Both must detect
            verified = custom_detected and builtin_detected
            method = "dual_verification"
        else:  # fallback
            # Custom first, builtin as fallback
            verified = custom_detected or builtin_detected
            method = "custom" if custom_detected else "builtin_fallback"

        info = {
            'custom_detected': custom_detected,
            'builtin_detected': builtin_detected,
            'custom_conf': custom_conf,
            'builtin_conf': builtin_conf,
            'method': method
        }

        return verified, info


# ── Simple usage example ────────────────────────────────────────

if __name__ == "__main__":
    import cv2

    # Initialize verifier
    verifier = DualBottleVerifier(mode="dual")

    # Open camera
    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Verify bottle
        verified, info = verifier.verify(frame)

        # Display result
        if verified:
            print(f"✓ VERIFIED! Custom: {info['custom_conf']:.2f}, "
                  f"Built-in: {info['builtin_conf']:.2f} ({info['method']})")
        else:
            print(f"✗ Not verified - Custom: {info['custom_detected']}, "
                  f"Built-in: {info['builtin_detected']}")

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
