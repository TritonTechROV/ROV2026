import cv2
import numpy as np
import time
from threading import Lock

CSI_DEVICE = "/base/axi/pcie@1000120000/rp1/i2c@88000/ov5647@36"
CSI_WIDTH  = 960
CSI_HEIGHT = 540
CSI_FPS    = 30

_cam  = None
_lock = Lock()


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


def generate_frames():
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

        frame = cv2.rotate(frame, cv2.ROTATE_180)
        encoded = _encode(frame)
        if encoded:
            yield encoded
