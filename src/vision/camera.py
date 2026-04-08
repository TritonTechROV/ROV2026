import cv2
import numpy as np

TARGET_COLOR_LOWER = np.array([100, 150, 50])
TARGET_COLOR_UPPER = np.array([140, 255, 255])

RESOLUTION_PIXELS_WIDTH = 1920
RESOLUTION_PIXELS_HEIGHT = 1080

cam = cv2.VideoCapture(0)
print("Camera opened:", cam.isOpened())

cam.set(cv2.CAP_PROP_FRAME_WIDTH, RESOLUTION_PIXELS_WIDTH)
cam.set(cv2.CAP_PROP_FRAME_HEIGHT, RESOLUTION_PIXELS_HEIGHT)

def generate_frames():
    while True:
        ret, frame = cam.read()

        if not ret:
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

        success, buffer = cv2.imencode(".jpg", frame)
        if not success:
            continue

        frame_bytes = buffer.tobytes()

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )
