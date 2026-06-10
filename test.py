import cv2
from flask import Flask, Response

app = Flask(__name__)

# Camera parameters
WIDTH = 640
HEIGHT = 480
FPS = 30

def _build_gstreamer_pipeline() -> str:
    """Builds the GStreamer pipeline string for libcamerasrc."""
    return (
        "libcamerasrc ! "
        f"video/x-raw,width={WIDTH},height={HEIGHT},framerate={FPS}/1 ! "
        "videoconvert ! "
        "videoscale ! "
        "video/x-raw,format=BGR ! "
        "appsink drop=true max-buffers=1 sync=false"
    )

def generate_frames():
    """Generator function to pull frames from OpenCV and encode as JPEG."""
    pipeline = _build_gstreamer_pipeline()
    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

    if not cap.isOpened():
        raise RuntimeError("Failed to open camera with GStreamer pipeline.")

    try:
        while True:
            success, frame = cap.read()
            if not success:
                break
            
            # Compress to JPEG for HTTP transmission
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue
                
            frame_bytes = buffer.tobytes()

            # Yield multipart stream boundary
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    finally:
        cap.release()

@app.route('/video_feed')
def video_feed():
    """Route returning the multipart video stream."""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    # host='0.0.0.0' exposes the port to the external network
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
