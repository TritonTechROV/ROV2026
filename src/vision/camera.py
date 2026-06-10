import cv2
import numpy as np
import time
from threading import Lock

# =============================================================================
# CONFIGURATION
# =============================================================================

# --- Camera ---
CAMERA_INDEX = 0        # /dev/videoN index
WIDTH        = 1920     # Capture width in pixels
HEIGHT       = 1080     # Capture height in pixels
FPS          = 30       # Capture framerate

# --- Color Target (HSV space) ---
# Hue: 0–179. Set HUE_MIN > HUE_MAX to wrap around 180 (e.g. for red).
# Saturation / Value: 0–255.
TARGET_HUE_MIN = 178
TARGET_HUE_MAX = 5
TARGET_SAT_MIN = 120
TARGET_SAT_MAX = 250
TARGET_VAL_MIN = 50
TARGET_VAL_MAX = 255 

# --- Detection ---
# Contours whose pixel area is AT OR ABOVE this value will each get their own
# bounding box drawn. Contours below this value are ignored entirely.
MIN_CONTOUR_AREA = 400  # pixels²

# --- Overlay colours (BGR) ---
BOX_COLOR    = (0,   255,   0)   # Bounding box
CENTER_COLOR = (0,     0, 255)   # Center dot
LABEL_COLOR  = (255, 255, 255)   # Coordinate text

# =============================================================================
# CAMERA
# =============================================================================

cam         = None
CAMERA_LOCK = Lock()

def _build_gstreamer_pipeline() -> str:
    return (
        "libcamerasrc camera-name=/base/axi/pcie@1000120000/rp1/i2c@88000/ov5647@36 ! "
        "video/x-raw, width=960, height=540, framerate=30/1, format=YUY2 ! "
        "videoconvert ! "
        "video/x-raw, format=BGR ! "
        "appsink drop=true max-buffers=1 sync=false"
    )

def open_camera() -> None:
    global cam
    with CAMERA_LOCK:
        if cam is not None:
            cam.release()
        cam = cv2.VideoCapture(_build_gstreamer_pipeline(), cv2.CAP_GSTREAMER)
        print("Camera opened:", cam.isOpened())


def is_camera_connected() -> bool:
    global cam
    if cam is None:
        open_camera()

    with CAMERA_LOCK:
        connected = cam is not None and cam.isOpened()

    if not connected:
        open_camera()
        with CAMERA_LOCK:
            connected = cam is not None and cam.isOpened()

    return connected


# =============================================================================
# COLOR MASKING
# =============================================================================

def get_color_mask(
    hsv_img: np.ndarray,
    h_min: int, h_max: int,
    s_min: int, s_max: int,
    v_min: int, v_max: int,
) -> np.ndarray:
    """
    Return a binary mask for pixels matching the given HSV range.
    Handles hue wrap-around automatically when h_min > h_max (e.g. red).
    """
    if h_min <= h_max:
        lower = np.array([h_min, s_min, v_min])
        upper = np.array([h_max, s_max, v_max])
        return cv2.inRange(hsv_img, lower, upper)

    # Wrap-around: split into [0 … h_max] ∪ [h_min … 179]
    mask_low  = cv2.inRange(hsv_img, np.array([0,     s_min, v_min]),
                                     np.array([h_max, s_max, v_max]))
    mask_high = cv2.inRange(hsv_img, np.array([h_min, s_min, v_min]),
                                     np.array([179,   s_max, v_max]))
    return cv2.bitwise_or(mask_low, mask_high)


# =============================================================================
# DRAWING
# =============================================================================

def draw_detections(frame: np.ndarray, contours: list) -> None:
    """
    Draw a bounding box, center dot, and coordinate label for every contour
    whose area meets or exceeds MIN_CONTOUR_AREA.
    """
    for contour in contours:
        if cv2.contourArea(contour) < MIN_CONTOUR_AREA:
            continue

        x, y, w, h = cv2.boundingRect(contour)
        cx, cy = x + w // 2, y + h // 2

        cv2.rectangle(frame, (x, y), (x + w, y + h), BOX_COLOR, 2)
        cv2.circle(frame, (cx, cy), 6, CENTER_COLOR, -1)
        cv2.putText(
            frame,
            f"({cx}, {cy})",
            (x, max(30, y - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            LABEL_COLOR,
            2,
        )


# =============================================================================
# FRAME GENERATION
# =============================================================================

def _encode_mjpeg(frame: np.ndarray) -> bytes | None:
    success, buffer = cv2.imencode(".jpg", frame)
    if not success:
        return None
    return (
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n\r\n"
        + buffer.tobytes()
        + b"\r\n"
    )


def _placeholder_frame() -> np.ndarray:
    """Black frame returned while the camera is unavailable."""
    return np.zeros((480, 854, 3), dtype=np.uint8)


def generate_frames():
    """
    Infinite generator that yields MJPEG-encoded frames.
    Each frame has bounding boxes drawn around every detected color blob
    that is at least MIN_CONTOUR_AREA pixels² in size.
    """
    while True:
        if not is_camera_connected():
            open_camera()
            yield _encode_mjpeg(_placeholder_frame())
            time.sleep(0.5)
            continue

        with CAMERA_LOCK:
            local_cam = cam

        if local_cam is None:
            time.sleep(0.2)
            continue

        ret, frame = local_cam.read()
        if not ret:
            open_camera()
            yield _encode_mjpeg(_placeholder_frame())
            time.sleep(0.2)
            continue

        # Detect target colour
        hsv      = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask     = get_color_mask(
            hsv,
            TARGET_HUE_MIN, TARGET_HUE_MAX,
            TARGET_SAT_MIN, TARGET_SAT_MAX,
            TARGET_VAL_MIN, TARGET_VAL_MAX,
        )
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        draw_detections(frame, contours)

        encoded = _encode_mjpeg(frame)
        if encoded:
            yield encoded