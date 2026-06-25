import glob
import subprocess
import cv2
import numpy as np
import time
import threading
from threading import Lock

# =============================================================================
# CONFIGURATION
# =============================================================================

# --- USB Camera (V4L2 + OpenCV, color detection) ---
def _find_usb_camera() -> str:
    for dev in sorted(glob.glob("/dev/video*")):
        try:
            out = subprocess.check_output(
                ["v4l2-ctl", "--device", dev, "--list-formats"],
                stderr=subprocess.DEVNULL, timeout=1, text=True,
            )
            if "MJPG" in out:
                print(f"[usb_camera] found at {dev}")
                return dev
        except Exception:
            continue
    raise RuntimeError("No MJPEG-capable USB camera found on any /dev/video* device")

USB_DEVICE    = _find_usb_camera()
WIDTH         = 1920   # capture resolution (must be a native camera resolution)
HEIGHT        = 1080
FPS           = 30
OUT_WIDTH     = 960    # scaled output resolution
OUT_HEIGHT    = 540

# --- CSI Camera (libcamera GStreamer, passthrough only) ---
CSI_DEVICE   = "/base/axi/pcie@1000120000/rp1/i2c@88000/ov5647@36"
CSI_WIDTH    = 960
CSI_HEIGHT   = 540
CSI_FPS      = 30

# --- Color Target (HSV, OpenCV scale: H 0-179, S 0-255, V 0-255) ---
TARGET_HUE_MIN = 160
TARGET_HUE_MAX = 10
TARGET_SAT_MIN = 50
TARGET_SAT_MAX = 140
TARGET_VAL_MIN = 100
TARGET_VAL_MAX = 255

# --- Detection ---
MIN_CONTOUR_AREA = 300  # pixels²

# --- Overlay colours (BGR) ---
BOX_COLOR    = (0,   255,   0)
CENTER_COLOR = (0,     0, 255)
LABEL_COLOR  = (255, 255, 255)

# =============================================================================
# INTERNAL STATE
# =============================================================================

_cam  = None
_lock = Lock()

_latest_encoded: "bytes | None" = None
_encoded_lock   = Lock()
_capture_started = False
_capture_lock    = Lock()

_latest_raw_frame: "np.ndarray | None" = None
_raw_frame_lock  = Lock()
_latest_contour_bboxes: list = []
_bboxes_lock     = Lock()


# =============================================================================
# CAMERA OPEN / STATUS
# =============================================================================

def _gst_pipeline() -> str:
    return (
        f"v4l2src device={USB_DEVICE} ! "
        f"image/jpeg,width={WIDTH},height={HEIGHT},framerate={FPS}/1 ! "
        "jpegdec ! "
        f"videoscale ! video/x-raw,width={OUT_WIDTH},height={OUT_HEIGHT} ! "
        "videoconvert ! "
        "appsink drop=true max-buffers=1 sync=false"
    )


def open_camera() -> None:
    global _cam
    with _lock:
        if _cam is not None:
            _cam.release()
        _cam = cv2.VideoCapture(_gst_pipeline(), cv2.CAP_GSTREAMER)
        print(f"[usb_camera] opened: {_cam.isOpened()}")


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


# =============================================================================
# COLOR MASKING
# =============================================================================

def _color_mask(hsv: np.ndarray) -> np.ndarray:
    h_min, h_max = TARGET_HUE_MIN, TARGET_HUE_MAX
    lo = (TARGET_SAT_MIN, TARGET_VAL_MIN)
    hi = (TARGET_SAT_MAX, TARGET_VAL_MAX)

    if h_min <= h_max:
        return cv2.inRange(hsv,
                           np.array([h_min, *lo]),
                           np.array([h_max, *hi]))

    # Hue wrap-around (e.g. red)
    m_lo = cv2.inRange(hsv, np.array([0,     *lo]), np.array([h_max, *hi]))
    m_hi = cv2.inRange(hsv, np.array([h_min, *lo]), np.array([179,   *hi]))
    return cv2.bitwise_or(m_lo, m_hi)


# =============================================================================
# DRAWING
# =============================================================================

def _draw_detections(frame: np.ndarray, contours: list) -> None:
    for contour in contours:
        if cv2.contourArea(contour) < MIN_CONTOUR_AREA:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        cx, cy = x + w // 2, y + h // 2
        cv2.rectangle(frame, (x, y), (x + w, y + h), BOX_COLOR, 2)
        cv2.circle(frame, (cx, cy), 6, CENTER_COLOR, -1)
        cv2.putText(
            frame, f"({cx}, {cy})",
            (x, max(30, y - 10)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, LABEL_COLOR, 2,
        )


# =============================================================================
# MJPEG HELPERS
# =============================================================================

def _encode(frame: np.ndarray) -> bytes | None:
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        return None
    return b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"


def _placeholder() -> np.ndarray:
    return np.zeros((480, 854, 3), dtype=np.uint8)


# =============================================================================
# BACKGROUND CAPTURE THREAD
# =============================================================================

_last_debug_time = 0

def _run_capture():
    global _latest_encoded, _last_debug_time
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

        hsv      = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        now = time.time()
        if now - _last_debug_time >= 2.0:
            _last_debug_time = now
            cy, cx = frame.shape[0] // 2, frame.shape[1] // 2
            h, s, v = hsv[cy, cx]
            print(f"[hsv_debug] center pixel → H={h} S={s} V={v}  "
                  f"(std: H={h*2}° S={s/255*100:.1f}% V={v/255*100:.1f}%)")

        mask     = _color_mask(hsv)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        valid_bboxes = [
            list(cv2.boundingRect(c))
            for c in contours
            if cv2.contourArea(c) >= MIN_CONTOUR_AREA
        ]
        with _raw_frame_lock:
            global _latest_raw_frame
            _latest_raw_frame = frame.copy()
        with _bboxes_lock:
            global _latest_contour_bboxes
            _latest_contour_bboxes = valid_bboxes

        _draw_detections(frame, contours)

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


# =============================================================================
# PUBLIC GENERATOR
# =============================================================================

def generate_frames():
    """Yield MJPEG frames with color-detection overlays. Multiple callers safe."""
    _ensure_capture_thread()
    while True:
        with _encoded_lock:
            frame = _latest_encoded
        if frame:
            yield frame
        time.sleep(1 / 30)


def take_main_snapshot() -> "tuple[bytes | None, list]":
    """Return (jpeg_bytes, bboxes) from the latest main camera frame.

    bboxes is a list of [x, y, w, h] ints (one per detected contour).
    Returns (None, []) if no frame has been captured yet.
    """
    _ensure_capture_thread()
    with _raw_frame_lock:
        raw = _latest_raw_frame
    if raw is None:
        return None, []
    with _bboxes_lock:
        bboxes = list(_latest_contour_bboxes)
    annotated = raw.copy()
    contours_approx = [
        np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], dtype=np.int32).reshape(-1, 1, 2)
        for x, y, w, h in bboxes
    ]
    _draw_detections(annotated, contours_approx)
    ok, buf = cv2.imencode(".jpg", annotated)
    if not ok:
        return None, bboxes
    return buf.tobytes(), bboxes
