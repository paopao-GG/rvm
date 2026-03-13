# Dual YOLO Verification Integration Guide

## What is Dual Verification?

Uses **2 YOLO models** to verify bottles:
1. **Custom NCNN model** - Your trained model (specific bottle types)
2. **Built-in YOLO COCO** - Pre-trained generic "bottle" detector

## Why Use It?

✅ **Higher reliability** - Both models must agree (reduces false positives)
✅ **Fallback option** - Use built-in if custom model fails
✅ **Better fraud prevention** - Harder to fool both models

## Test Scripts

### 1. Test Dual Models (3 modes)
```bash
cd /home/raspi/rvm
python3 test_yolo_dual.py
```

**Modes** (press 'm' to cycle):
- `dual` - Both models must detect (strictest)
- `fallback` - Use built-in if custom fails
- `parallel` - Side-by-side comparison

### 2. Test Single Model
```bash
python3 test_yolo_live.py
```

---

## Integration into main_integrated.py

### Option A: Quick Integration (Recommended)

Replace the verification section in `main_integrated.py` (around line 689-764):

```python
# ── At the top of main_integrated.py ──
from dual_verification import DualBottleVerifier

# ── In main() function, after loading model (around line 567) ──
# Replace:
# model = YOLO(MODEL_PATH, task='segment')

# With:
verifier = DualBottleVerifier(
    custom_model_path=MODEL_PATH,
    custom_conf=VERIFY_CONF,
    builtin_model="yolov8n.pt",  # Fastest (nano)
    builtin_conf=0.50,           # Lower threshold for generic detection
    mode="dual"                  # Options: "dual", "fallback", "custom_only"
)

# ── In verification loop (around line 735) ──
# Replace:
# frame, detected = run_inference(model, frame, VERIFY_CONF)

# With:
verified, info = verifier.verify(frame)

# Update display to show both detections
remaining = max(0, VERIFY_TIMEOUT - (time.time() - verify_start))
h = frame.shape[0]
cv2.putText(frame, f"Custom: {info['custom_conf']:.2f} | Built-in: {info['builtin_conf']:.2f}",
            (10, h - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
cv2.putText(frame, f"Verifying: {scanned_type} ({remaining:.0f}s)",
            (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
cv2.imshow("RVM - Bottle Detection", frame)
cv2.waitKey(1)

# Replace:
# if detected:

# With:
if verified:
    logger.info("✓ DUAL VERIFIED! Custom: %.2f, Built-in: %.2f (%s)",
               info['custom_conf'], info['builtin_conf'], info['method'])
```

### Option B: Manual Integration (Full Control)

Add to configuration section (line 82):
```python
# Dual verification settings
USE_DUAL_VERIFICATION = True
BUILTIN_MODEL = "yolov8n.pt"  # Options: yolov8n.pt, yolov8s.pt, yolov8m.pt
BUILTIN_CONF = 0.50
VERIFICATION_MODE = "dual"  # Options: "dual", "fallback", "custom_only"
```

Load both models in `main()`:
```python
# Load custom model
logger.info("Loading NCNN model from %s", MODEL_PATH)
model = YOLO(MODEL_PATH, task='segment')

# Load built-in model if dual verification enabled
builtin_model = None
if USE_DUAL_VERIFICATION and VERIFICATION_MODE != "custom_only":
    logger.info("Loading built-in YOLO model: %s", BUILTIN_MODEL)
    builtin_model = YOLO(BUILTIN_MODEL)
    logger.info("Dual verification enabled (mode: %s)", VERIFICATION_MODE)
```

Update verification logic:
```python
# Run custom model
frame, custom_detected = run_inference(model, frame, VERIFY_CONF)

# Run built-in model if enabled
builtin_detected = False
if USE_DUAL_VERIFICATION and builtin_model:
    builtin_results = builtin_model.predict(
        frame, imgsz=640, conf=BUILTIN_CONF,
        classes=[39],  # Bottle class in COCO
        max_det=1, verbose=False, half=False
    )[0]

    if builtin_results.boxes is not None and len(builtin_results.boxes) > 0:
        builtin_detected = True
        # Draw built-in detection (optional)
        box = builtin_results.boxes[0]
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 255), 2)

# Determine final verification
if VERIFICATION_MODE == "dual":
    verified = custom_detected and builtin_detected
elif VERIFICATION_MODE == "fallback":
    verified = custom_detected or builtin_detected
else:  # custom_only
    verified = custom_detected

if verified:
    # Continue with bottle processing...
```

---

## Model Options (Built-in)

| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| `yolov8n.pt` | 6 MB | ⚡⚡⚡ Fastest | ⭐⭐ Good |
| `yolov8s.pt` | 22 MB | ⚡⚡ Fast | ⭐⭐⭐ Better |
| `yolov8m.pt` | 52 MB | ⚡ Slower | ⭐⭐⭐⭐ Best |

**Recommendation for Raspberry Pi 5**: Use `yolov8n.pt` (nano) for best speed.

---

## Configuration Tips

### Strict Mode (Prevent Fraud)
```python
mode="dual"
custom_conf=0.70
builtin_conf=0.60
# Both models must detect with high confidence
```

### Balanced Mode
```python
mode="dual"
custom_conf=0.60
builtin_conf=0.50
# Both detect, custom stricter
```

### Fallback Mode (Reliability)
```python
mode="fallback"
custom_conf=0.70
builtin_conf=0.50
# Try custom first, use built-in as backup
```

---

## Testing Checklist

1. ✅ Test with real bottles - should detect
2. ✅ Test with fake/printed images - should reject (dual mode)
3. ✅ Test with empty hands - should reject
4. ✅ Test with other objects - should reject
5. ✅ Check FPS performance (should be >5 FPS on Pi 5)
6. ✅ Test fallback behavior if custom model fails

---

## Performance Impact

- **Custom only**: ~15-20 FPS on Pi 5
- **Dual verification**: ~8-12 FPS on Pi 5 (still acceptable)
- **Verification time**: Adds ~0.5-1 second to detection

The slight performance hit is worth it for improved reliability!
