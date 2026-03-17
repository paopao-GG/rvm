#!/usr/bin/env python3
"""
Dual YOLO Model Test - Custom NCNN + Built-in COCO
Tests both custom bottle model and YOLOv8 COCO bottle detection
"""

import cv2
import time
from ultralytics import YOLO

# ── Configuration ──────────────────────────────────────────────
# Custom NCNN model (your trained model)
CUSTOM_MODEL_PATH = "best_ncnn_model"
CUSTOM_CLASS_NAMES = ["coke_litro", "coke_mismo", "water_bottle-1L", "water_bottle-350mL", "water_bottle-500mL"]
CUSTOM_CONF = 0.60

# Built-in YOLO COCO model
BUILTIN_MODEL = "yolov8n.pt"  # Options: yolov8n.pt (nano, fastest), yolov8s.pt (small), yolov8m.pt (medium)
BUILTIN_CONF = 0.50  # Lower confidence for generic bottle detection
BOTTLE_CLASS_ID = 39  # COCO dataset class ID for "bottle"

# Verification mode
MODE = "dual"  # Options: "dual" (both must detect), "fallback" (builtin if custom fails), "parallel" (show both)

print("="*70)
print("Dual YOLO Model Test - Custom NCNN + Built-in COCO")
print("="*70)
print(f"Mode: {MODE.upper()}")
print(f"\nCustom Model: {CUSTOM_MODEL_PATH} (conf: {CUSTOM_CONF})")
print(f"Built-in Model: {BUILTIN_MODEL} (conf: {BUILTIN_CONF})")
print(f"\nPress 'q' to quit, 'm' to change mode")
print("="*70)

# Load models
print(f"\nLoading custom model from {CUSTOM_MODEL_PATH}...")
custom_model = YOLO(CUSTOM_MODEL_PATH, task='segment')
print("✓ Custom model loaded")

print(f"Loading built-in model {BUILTIN_MODEL}...")
builtin_model = YOLO(BUILTIN_MODEL)
print("✓ Built-in model loaded\n")

# Open camera
print("Opening camera...")
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
cap.set(cv2.CAP_PROP_FPS, 30)

if not cap.isOpened():
    print("ERROR: Cannot open camera")
    exit(1)

print("✓ Camera opened\n")
print("Starting live detection...")

# FPS tracking
fps_start_time = time.time()
fps_counter = 0
fps = 0

# Mode cycling
modes = ["dual", "fallback", "parallel"]
mode_idx = modes.index(MODE)

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame")
            break

        h, w = frame.shape[:2]

        # Create split view for parallel mode
        if MODE == "parallel":
            frame_custom = frame.copy()
            frame_builtin = frame.copy()
        else:
            frame_custom = frame
            frame_builtin = frame

        # ── Run Custom NCNN Model ──────────────────────────────
        custom_results = custom_model.predict(
            frame_custom,
            imgsz=640,
            conf=CUSTOM_CONF,
            max_det=5,
            verbose=False,
            half=False
        )[0]

        custom_detected = False
        custom_count = 0
        if custom_results.boxes is not None and len(custom_results.boxes) > 0:
            for box in custom_results.boxes:
                cls_id = int(box.cls[0])
                if cls_id >= len(CUSTOM_CLASS_NAMES):
                    continue

                custom_detected = True
                custom_count += 1
                box_conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                # Draw on custom frame
                cv2.rectangle(frame_custom, (x1, y1), (x2, y2), (0, 255, 0), 2)
                label = f"CUSTOM: {CUSTOM_CLASS_NAMES[cls_id]} {box_conf:.2f}"
                cv2.putText(frame_custom, label, (x1, y1 - 5),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # ── Run Built-in YOLO COCO Model ───────────────────────
        builtin_results = builtin_model.predict(
            frame_builtin,
            imgsz=640,
            conf=BUILTIN_CONF,
            classes=[BOTTLE_CLASS_ID],  # Only detect "bottle" class
            max_det=5,
            verbose=False,
            half=False
        )[0]

        builtin_detected = False
        builtin_count = 0
        if builtin_results.boxes is not None and len(builtin_results.boxes) > 0:
            for box in builtin_results.boxes:
                builtin_detected = True
                builtin_count += 1
                box_conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                # Draw on builtin frame
                cv2.rectangle(frame_builtin, (x1, y1), (x2, y2), (255, 0, 255), 2)
                label = f"BUILTIN: bottle {box_conf:.2f}"
                cv2.putText(frame_builtin, label, (x1, y1 - 25),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 2)

        # ── Determine final detection based on mode ────────────
        if MODE == "dual":
            # Both must detect
            final_detected = custom_detected and builtin_detected
            verification_status = "✓ BOTH DETECTED" if final_detected else \
                                 f"Custom: {custom_detected}, Built-in: {builtin_detected}"
            display_frame = frame_custom

        elif MODE == "fallback":
            # Use custom, fallback to builtin
            final_detected = custom_detected or builtin_detected
            if custom_detected:
                verification_status = "✓ CUSTOM DETECTED"
                display_frame = frame_custom
            elif builtin_detected:
                verification_status = "⚠ BUILTIN FALLBACK"
                display_frame = frame_builtin
            else:
                verification_status = "✗ NONE DETECTED"
                display_frame = frame_custom

        else:  # parallel
            # Show both side by side
            final_detected = custom_detected or builtin_detected
            # Resize frames to half width
            frame_custom_resized = cv2.resize(frame_custom, (w//2, h))
            frame_builtin_resized = cv2.resize(frame_builtin, (w//2, h))
            display_frame = cv2.hconcat([frame_custom_resized, frame_builtin_resized])

            # Add labels
            cv2.putText(display_frame, "CUSTOM MODEL", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(display_frame, "BUILT-IN MODEL", (w//2 + 10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
            verification_status = f"Custom: {custom_detected}, Built-in: {builtin_detected}"

        # Calculate FPS
        fps_counter += 1
        if fps_counter >= 10:
            fps = fps_counter / (time.time() - fps_start_time)
            fps_counter = 0
            fps_start_time = time.time()

        # ── Draw info overlay ──────────────────────────────────
        if MODE != "parallel":
            # Background for info
            cv2.rectangle(display_frame, (0, 0), (w, 110), (0, 0, 0), -1)

            # Info text
            cv2.putText(display_frame, f"Mode: {MODE.upper()}", (10, 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            cv2.putText(display_frame, f"FPS: {fps:.1f}", (10, 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.putText(display_frame, f"Custom: {custom_count} | Built-in: {builtin_count}", (10, 75),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.putText(display_frame, verification_status, (10, 100),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # Status message at bottom
            status_color = (0, 255, 0) if final_detected else (128, 128, 128)
            status_msg = "✓ VERIFIED!" if final_detected else "No bottle detected"
            cv2.putText(display_frame, status_msg, (10, h - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)

        # Show frame
        cv2.imshow("Dual YOLO Test (Press 'q' quit, 'm' change mode)", display_frame)

        # Handle key presses
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("\nQuitting...")
            break
        elif key == ord('m'):
            mode_idx = (mode_idx + 1) % len(modes)
            MODE = modes[mode_idx]
            print(f"\nSwitched to mode: {MODE.upper()}")

except KeyboardInterrupt:
    print("\nInterrupted by user")

finally:
    cap.release()
    cv2.destroyAllWindows()
    print("Camera released")
    print("="*70)
