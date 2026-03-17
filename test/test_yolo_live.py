#!/usr/bin/env python3
"""
Test YOLO NCNN Model - Live Camera Feed
Debug script for YOLO bottle detection with 85% confidence threshold
"""

import cv2
import time
from ultralytics import YOLO

# ── Configuration (from main_integrated.py) ──────────────────────
MODEL_PATH = "best_ncnn_model"
CLASS_NAMES = ["coke_litro", "coke_mismo", "water_bottle-1L", "water_bottle-350mL", "water_bottle-500mL"]
COLORS = [(0, 0, 255), (0, 128, 255), (255, 0, 0), (255, 255, 0), (255, 0, 255)]
CONFIDENCE = 0.60  # 85% confidence threshold

print("="*60)
print("YOLO NCNN Model Test - Live Detection")
print("="*60)
print(f"Model: {MODEL_PATH}")
print(f"Confidence: {CONFIDENCE} (85%)")
print(f"Classes: {CLASS_NAMES}")
print("\nPress 'q' to quit")
print("="*60)

# Load YOLO model
print(f"\nLoading model from {MODEL_PATH}...")
model = YOLO(MODEL_PATH, task='segment')
print("✓ Model loaded successfully\n")

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

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame")
            break

        # Run YOLO inference
        results = model.predict(
            frame,
            imgsz=640,
            conf=CONFIDENCE,
            max_det=5,  # Detect up to 5 bottles
            verbose=False,
            half=False
        )[0]

        # Process detections
        detected_count = 0
        if results.boxes is not None and len(results.boxes) > 0:
            for box in results.boxes:
                cls_id = int(box.cls[0])
                if cls_id >= len(CLASS_NAMES):
                    continue

                detected_count += 1
                box_conf = float(box.conf[0])
                color = COLORS[cls_id % len(COLORS)]
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                # Draw bounding box
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                # Draw label with confidence
                label = f"{CLASS_NAMES[cls_id]} {box_conf:.2f}"
                label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)

                # Background for text
                cv2.rectangle(frame, (x1, y1 - label_size[1] - 10),
                            (x1 + label_size[0], y1), color, -1)

                # Text
                cv2.putText(frame, label, (x1, y1 - 5),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        # Calculate FPS
        fps_counter += 1
        if fps_counter >= 10:
            fps = fps_counter / (time.time() - fps_start_time)
            fps_counter = 0
            fps_start_time = time.time()

        # Draw info overlay
        h, w = frame.shape[:2]

        # Background for info
        cv2.rectangle(frame, (0, 0), (w, 80), (0, 0, 0), -1)

        # Info text
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"Confidence: {CONFIDENCE} (85%)", (10, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(frame, f"Detected: {detected_count}", (10, 75),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

        # Status message at bottom
        status_color = (0, 255, 0) if detected_count > 0 else (128, 128, 128)
        status_msg = f"✓ BOTTLE DETECTED!" if detected_count > 0 else "No bottle detected"
        cv2.putText(frame, status_msg, (10, h - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)

        # Show frame
        cv2.imshow("YOLO NCNN Test - Live Detection (Press 'q' to quit)", frame)

        # Quit on 'q' key
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("\nQuitting...")
            break

except KeyboardInterrupt:
    print("\nInterrupted by user")

finally:
    cap.release()
    cv2.destroyAllWindows()
    print("Camera released")
    print("="*60)
