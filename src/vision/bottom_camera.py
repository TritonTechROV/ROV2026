import cv2
import numpy as np
import time
import threading
from pathlib import Path
from threading import Lock
from ultralytics import YOLO


CSI_DEVICE = "/base/axi/pcie@1000120000/rp1/i2c@88000/ov5647@36"
CSI_WIDTH  = 960
CSI_HEIGHT = 540
CSI_FPS    = 30

_MODEL_PATH = Path(__file__).parent / "crab_ncnn_model"

_cam           = None
_lock          = Lock()
_model         = None
_model_checked = False

_latest_frame: "np.ndarray | None" = None
_frame_lock    = Lock()

_latest_encoded: "bytes | None" = None
_encoded_lock   = Lock()
_capture_started = False
_capture_lock    = Lock()


def _load_model() -> YOLO | None:
    global _model, _model_checked
    if _model is not None:
        return _model
    if _model_checked:
        return None
    _model_checked = True
    if not _MODEL_PATH.is_dir():
        print(f"[bottom_camera] crab model not found at {_MODEL_PATH} — detection disabled")
        return None
    _model = YOLO(str(_MODEL_PATH), task="detect")
    print(f"[bottom_camera] loaded crab model from {_MODEL_PATH}")
    return _model


def _gst_pipeline() -> str:
    return (
        f"libcamerasrc camera-name={CSI_DEVICE} ! "
        f"video/x-raw, width={CSI_WIDTH}, height={CSI_HEIGHT}, framerate={CSI_FPS}/1, format=YUY2 ! "
        "videoconvert ! "
        "video/x-raw, format=BGR ! "
        "appsink drop=true max-buffers=1 sync=false"
    )


def open_camera() -> None:
    global _cam
    with _lock:
        if _cam is not None:
            _cam.release()
        _cam = cv2.VideoCapture(_gst_pipeline(), cv2.CAP_GSTREAMER)
        print(f"[bottom_camera] opened: {_cam.isOpened()}")


def is_connected() -> bool:
    global _cam
    if _cam is None:
        open_camera()
    with _lock:
        ok = _cam is not None and _cam.isOpened()
    if not ok:
        open_camera()
        with _lock:
            ok = _cam is not None and _cam.isOpened()
    return ok


def _encode(frame: np.ndarray) -> bytes | None:
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        return None
    return b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"


def _placeholder() -> np.ndarray:
    return np.zeros((480, 854, 3), dtype=np.uint8)


SNAPSHOT_CONF = 0.06


def _annotate(frame: np.ndarray, conf: float = SNAPSHOT_CONF) -> tuple[np.ndarray, list[dict]]:
    """Run YOLO inference and draw boxes. Returns (annotated_frame, detections)."""
    model = _load_model()
    if model is None:
        return frame, []

    results = model(frame, conf=conf, verbose=False)[0]
    detections = []
    for box in results.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        conf_val = float(box.conf[0])
        cls  = int(box.cls[0])
        label = f"{model.names[cls]} {conf_val:.2f}"
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        detections.append({"class": model.names[cls], "confidence": conf_val, "bbox": [x1, y1, x2, y2]})
    return frame, detections


def take_snapshot() -> tuple[bytes | None, list[dict]]:
    """Run inference on the latest cached frame; never touches the camera directly."""
    with _frame_lock:
        frame = _latest_frame.copy() if _latest_frame is not None else None
    if frame is None:
        return None, []
    annotated, detections = _annotate(frame)
    ok, buf = cv2.imencode(".jpg", annotated)
    if not ok:
        return None, []
    return buf.tobytes(), detections


def _run_capture():
    global _latest_encoded, _latest_frame
    while True:
        if not is_connected():
            with _encoded_lock:
                _latest_encoded = _encode(_placeholder())
            time.sleep(0.5)
            continue

        with _lock:
            local = _cam

        if local is None:
            time.sleep(0.2)
            continue

        ret, frame = local.read()
        if not ret:
            open_camera()
            with _encoded_lock:
                _latest_encoded = _encode(_placeholder())
            time.sleep(0.2)
            continue

        frame = cv2.rotate(frame, cv2.ROTATE_180)
        with _frame_lock:
            _latest_frame = frame.copy()
        encoded = _encode(frame)
        if encoded:
            with _encoded_lock:
                _latest_encoded = encoded


def _ensure_capture_thread():
    global _capture_started
    with _capture_lock:
        if not _capture_started:
            _capture_started = True
            threading.Thread(target=_run_capture, daemon=True).start()


def generate_frames():
    """Yield MJPEG frames. Multiple callers safe."""
    _ensure_capture_thread()
    while True:
        with _encoded_lock:
            frame = _latest_encoded
        if frame:
            yield frame
        time.sleep(1 / 30)
