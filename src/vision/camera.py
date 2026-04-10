import cv2
import numpy as np
import time
from threading import Lock

TARGET_COLOR_LOWER = np.array([100, 150, 50])
TARGET_COLOR_UPPER = np.array([140, 255, 255])

RESOLUTION_PIXELS_WIDTH = 1920
RESOLUTION_PIXELS_HEIGHT = 1080
CAMERA_INDEX = 0

cam = None
CAMERA_LOCK = Lock()


def open_camera() -> None:
    global cam

    with CAMERA_LOCK:
        if cam is not None:
            cam.release()

        cam = cv2.VideoCapture(CAMERA_INDEX)

        if cam.isOpened():
            cam.set(cv2.CAP_PROP_FRAME_WIDTH, RESOLUTION_PIXELS_WIDTH)
            cam.set(cv2.CAP_PROP_FRAME_HEIGHT, RESOLUTION_PIXELS_HEIGHT)

        print("Camera opened:", cam.isOpened())


def is_camera_connected() -> bool:
    if cam is None:
        open_camera()

    with CAMERA_LOCK:
        connected = cam is not None and cam.isOpened()

    if not connected:
        open_camera()
        with CAMERA_LOCK:
            connected = cam is not None and cam.isOpened()

    return connected


def encode_mjpeg_frame(frame: np.ndarray):
    success, buffer = cv2.imencode(".jpg", frame)
    if not success:
        return None

    frame_bytes = buffer.tobytes()
    return (
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
    )


def generate_status_frame() -> np.ndarray:
    frame = np.zeros((480, 854, 3), dtype=np.uint8)
    return frame

def generate_frames():
    while True:
        if not is_camera_connected():
            open_camera()
            placeholder = encode_mjpeg_frame(generate_status_frame())
            if placeholder is not None:
                yield placeholder
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
            placeholder = encode_mjpeg_frame(generate_status_frame())
            if placeholder is not None:
                yield placeholder
            time.sleep(0.2)
            continue

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, TARGET_COLOR_LOWER, TARGET_COLOR_UPPER)
        contours, _ = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if len(contours) > 0:
            c = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(c)
            center_x = x + w // 2
            center_y = y + h // 2

            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.circle(frame, (center_x, center_y), 6, (0, 0, 255), -1)
            cv2.putText(
                frame,
                f"({center_x}, {center_y})",
                (x, max(30, y - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2
            )

        encoded = encode_mjpeg_frame(frame)
        if encoded is None:
            continue

        yield encoded
