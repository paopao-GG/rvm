#!/usr/bin/env python3
"""
Test Built-in YOLO Model - Live Camera Feed
Tests YOLOv8 COCO pre-trained model for generic bottle detection
"""

import cv2
import time
from ultralytics import YOLO

# ── Configuration ──────────────────────────────────────────────
BUILTIN_MODEL = "yolov8n.pt"  # Options: yolov8n.pt (fastest), yolov8s.pt, yolov8m.pt
CONFIDENCE = 0.50  # 50% confidence threshold for generic bottle detection
BOTTLE_CLASS_ID = 39  # COCO dataset class ID for "bottle"

print("="*60)
print("YOLO Built-in Model Test - Generic Bottle Detection")
print("="*60)
print(f"Model: {BUILTIN_MODEL}")
print(f"Confidence: {CONFIDENCE} (50%)")
print(f"Detection: COCO 'bottle' class only")
print("\nPress 'q' to quit")
print("="*60)

# Load YOLO model
print(f"\nLoading built-in model {BUILTIN_MODEL}...")
print("(First run will download the model - may take a moment)")
model = YOLO(BUILTIN_MODEL)
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

        # Run YOLO inference - ONLY detect bottles (class 39)
        results = model.predict(
            frame,
            imgsz=640,
            conf=CONFIDENCE,
            classes=[BOTTLE_CLASS_ID],  # Filter for bottles only
            max_det=5,  # Detect up to 5 bottles
            verbose=False,
            half=False
        )[0]

        # Process detections
        detected_count = 0
        bottles = []
        if results.boxes is not None and len(results.boxes) > 0:
            for box in results.boxes:
                detected_count += 1
                box_conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                bottles.append({
                    'bbox': (x1, y1, x2, y2),
                    'conf': box_conf
                })

                # Draw bounding box (magenta for built-in model)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 255), 3)

                # Draw label with confidence
                label = f"BOTTLE {box_conf:.2f}"
                label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)

                # Background for text
                cv2.rectangle(frame, (x1, y1 - label_size[1] - 10),
                            (x1 + label_size[0] + 10, y1), (255, 0, 255), -1)

                # Text
                cv2.putText(frame, label, (x1 + 5, y1 - 5),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Calculate FPS
        fps_counter += 1
        if fps_counter >= 10:
            fps = fps_counter / (time.time() - fps_start_time)
            fps_counter = 0
            fps_start_time = time.time()

        # Draw info overlay
        h, w = frame.shape[:2]

        # Background for info
        cv2.rectangle(frame, (0, 0), (w, 110), (0, 0, 0), -1)

        # Info text
        cv2.putText(frame, f"Built-in YOLO (COCO)", (10, 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(frame, f"Confidence: {CONFIDENCE} (50%)", (10, 75),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(frame, f"Bottles Detected: {detected_count}", (10, 100),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

        # Status message at bottom
        status_color = (0, 255, 0) if detected_count > 0 else (128, 128, 128)
        status_msg = f"✓ {detected_count} BOTTLE(S) DETECTED!" if detected_count > 0 else "No bottle detected"
        cv2.putText(frame, status_msg, (10, h - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)

        # Show frame
        cv2.imshow("Built-in YOLO Test - Generic Bottle Detection (Press 'q' to quit)", frame)

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
