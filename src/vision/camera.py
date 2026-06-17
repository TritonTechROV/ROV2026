import cv2
import numpy as np
import time
from threading import Lock

# =============================================================================
# CONFIGURATION
# =============================================================================

# --- USB Camera (V4L2 + OpenCV, color detection) ---
USB_DEVICE   = "/dev/video0"
WIDTH        = 1920
HEIGHT       = 1080
FPS          = 30

# --- CSI Camera (libcamera GStreamer, passthrough only) ---
CSI_DEVICE   = "/base/axi/pcie@1000120000/rp1/i2c@88000/ov5647@36"
CSI_WIDTH    = 960
CSI_HEIGHT   = 540
CSI_FPS      = 30

# --- Color Target (HSV) ---
TARGET_HUE_MIN = 178
TARGET_HUE_MAX = 5
TARGET_SAT_MIN = 120
TARGET_SAT_MAX = 250
TARGET_VAL_MIN = 50
TARGET_VAL_MAX = 255

# --- Detection ---
MIN_CONTOUR_AREA = 400  # pixels²

# --- Overlay colours (BGR) ---
BOX_COLOR    = (0,   255,   0)
CENTER_COLOR = (0,     0, 255)
LABEL_COLOR  = (255, 255, 255)

# =============================================================================
# INTERNAL STATE
# =============================================================================

_cam  = None
_lock = Lock()


# =============================================================================
# CAMERA OPEN / STATUS
# =============================================================================

def _gst_pipeline() -> str:
    return (
        f"v4l2src device={USB_DEVICE} ! "
        f"image/jpeg,width={WIDTH},height={HEIGHT},framerate={FPS}/1 ! "
        "jpegdec ! videoconvert ! appsink"
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
# PUBLIC GENERATOR
# =============================================================================

def generate_frames():
    """Yield MJPEG frames with color-detection overlays."""
    while True:
        if not is_connected():
            yield _encode(_placeholder())
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
            yield _encode(_placeholder())
            time.sleep(0.2)
            continue

        hsv      = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask     = _color_mask(hsv)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        _draw_detections(frame, contours)

        encoded = _encode(frame)
        if encoded:
            yield encoded
