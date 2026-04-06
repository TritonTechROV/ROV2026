import cv2
import numpy as np
from flask import Flask, Response, render_template_string

app = Flask(__name__)

TARGET_COLOR_LOWER = np.array([100, 150, 50])
TARGET_COLOR_UPPER = np.array([140, 255, 255])

RESOLUTION_PIXELS_WIDTH = 1920
RESOLUTION_PIXELS_HEIGHT = 1080

cam = cv2.VideoCapture(0)
print("Camera opened:", cam.isOpened())

cam.set(cv2.CAP_PROP_FRAME_WIDTH, RESOLUTION_PIXELS_WIDTH)
cam.set(cv2.CAP_PROP_FRAME_HEIGHT, RESOLUTION_PIXELS_HEIGHT)

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Camera Stream</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            background: #111;
            color: white;
        }

        h1 {
            margin-top: 20px;
        }

        img {
            margin-top: 20px;
            max-width: 90%;
            border: 2px solid white;
        }
    </style>
</head>
<body>
    <h1>ROV Camera Stream</h1>
    <img src="/video_feed" alt="Live camera stream">
</body>
</html>
"""

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

@app.route("/")
def index():
    return render_template_string(HTML_PAGE)

@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
