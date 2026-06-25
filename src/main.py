from controller import Controller

from pathlib import Path
import logging, json, threading, urllib.request, ssl

import base64, math
from flask import Flask, Response, jsonify, render_template, request
from flask_socketio import SocketIO

from thruster_controller import set_outputs_from_controls, set_servo_angle
from vision.camera import generate_frames, take_main_snapshot
from vision.bottom_camera import generate_frames as generate_bottom_frames, take_snapshot

# setup - logger
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("pi")

# setup - config consts
BASE_DIR = Path(__file__).resolve().parent
CERT_DIR = BASE_DIR / "certs"

HOST = "0.0.0.0"
PORT = 5000
OPERATOR_PORT = 5001

# flask - create app (driver interface)
app = Flask(
	__name__,
	template_folder=str(BASE_DIR / "templates"),
	static_folder=str(BASE_DIR / "static"),
)
# flask - config
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.jinja_env.auto_reload = True

# socketio - setup
socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode="threading"
)

# flask - operator app (port 5001)
operator_app = Flask(
    "operator",
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
operator_app.config["TEMPLATES_AUTO_RELOAD"] = True
operator_app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

@operator_app.route("/")
def operator_index():
    return render_template("operator.html")

@operator_app.route("/main_video_feed")
def operator_main_video_feed():
    return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

@operator_app.route("/bottom_video_feed")
def operator_bottom_video_feed():
    return Response(generate_bottom_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

@operator_app.route("/main_snapshot", methods=["POST"])
def operator_main_snapshot():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(f"https://localhost:{PORT}/main_snapshot", method="POST")
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            return jsonify(json.loads(resp.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 503

@operator_app.route("/snapshot", methods=["POST"])
def operator_snapshot():
    # Proxy to the main app (port 5000) which owns the camera in its process.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(f"https://localhost:{PORT}/snapshot", method="POST")
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            return jsonify(json.loads(resp.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 503

def iter_watched_files():
	for path in BASE_DIR.rglob("*"):
		if not path.is_file():
			continue
		if "__pycache__" in path.parts:
			continue
		yield path


def get_source_revision() -> int:
	latest = 0
	for path in iter_watched_files():
		mtime = path.stat().st_mtime_ns
		if mtime > latest:
			latest = mtime
	return latest


@app.route("/")
def index():
	return render_template("index.html")

@app.route("/camera")
def camera():
        return render_template("camera.html")

_current_dimensions = {
    "centerBoxHeight": 0.8,
    "leftBoxWidth": 0.75,
    "rightBoxWidth": 0.5,
}

H_FOV_PX = 960
V_FOV_PX = 540
H_FOV_RAD = 110 * 3.14159 / 180
V_FOV_RAD = 63 * 3.14159 / 180
TAG_SIZE = 0.1 # m

def process_main_snapshot_bboxes(bboxes: list) -> None:
    """Process bounding boxes from the main camera and update _current_dimensions.

    bboxes: list of [x, y, w, h] pixel coordinates from color-detection contours.
    Edit _current_dimensions in place with computed measurements.
    """

    top = min(bboxes, key=lambda b: b[1], default=None)
    left = min(bboxes, key=lambda b: b[0], default=None)
    right = max(bboxes, key=lambda b: b[0], default=None)
    bottom = max(bboxes, key=lambda b: b[2] * b[3], default=None)

    if bottom is None:
        return

    focal_x = (H_FOV_PX / 2) / math.tan(H_FOV_RAD / 2)
    distance = TAG_SIZE * focal_x / bottom[2]

    bottom_center_x = bottom[0] + bottom[2] / 2
    bottom_center_y = bottom[1] + bottom[3] / 2

    left_center_x = left[0] + left[2] / 2 if left else 0
    right_center_x = right[0] + right[2] / 2 if right else H_FOV_PX
    top_center_y = top[1] + top[3] / 2 if top else 0

    focal_y = (V_FOV_PX / 2) / math.tan(V_FOV_RAD / 2)

    dist_to_left  = (bottom_center_x - left_center_x)  * distance / focal_x * 1.3
    dist_to_right = (right_center_x - bottom_center_x)  * distance / focal_x * 1.3
    dist_to_top   = (bottom_center_y - top_center_y)    * distance / focal_y * 1.6

    _current_dimensions["distance"] = distance
    _current_dimensions["leftBoxWidth"] = dist_to_left
    _current_dimensions["rightBoxWidth"] = dist_to_right
    _current_dimensions["centerBoxHeight"] = dist_to_top


@app.route("/dimensions")
def send_dimensions():
    return jsonify(_current_dimensions)

@app.route("/main_snapshot", methods=["POST"])
def main_snapshot():
    jpeg_bytes, bboxes = take_main_snapshot()
    if jpeg_bytes is None:
        return jsonify({"error": "main camera not available"}), 503
    process_main_snapshot_bboxes(bboxes)
    image_b64 = base64.b64encode(jpeg_bytes).decode()
    return jsonify({"image": image_b64, "bboxes": bboxes, "dimensions": _current_dimensions})

@app.route("/data")
def data():
    with open("src/config/xbox.json") as f:
        labels = json.load(f)
    return jsonify(labels)

@app.route("/main_video_feed")
def main_video_feed():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )

@app.route("/bottom_video_feed")
def bottom_video_feed():
    return Response(
        generate_bottom_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )

@app.route("/snapshot", methods=["POST"])
def snapshot():
    jpeg_bytes, detections = take_snapshot()
    if jpeg_bytes is None:
        return jsonify({"error": "camera not available"}), 503
    image_b64 = base64.b64encode(jpeg_bytes).decode()
    return jsonify({"image": image_b64, "detections": detections})

@app.route("/main_camera_status")
def camera_status():
	return jsonify({"connected": True})


@app.route("/__source_revision")
def source_revision():
	return jsonify({"revision": str(get_source_revision())})

@socketio.on('connect')
def handle_connect():
        log.info("Client connected")

# intilize empty class for controller handler
gpad = Controller()
YAW_WEIGHT = 0.5
ROLL_WEIGHT = 0.5
DEADBAND_THRESHOLD = 0.1

servo_pwm = 1200

def deadband(value, threshold=DEADBAND_THRESHOLD):
        if abs(value) <= threshold:
                return 0.0
        sign = 1.0 if value > 0 else -1.0
        return ((abs(value) - threshold) / (1.0 - threshold)) * sign

@socketio.on('controller')
def handle_controller(data):
	global servo_pwm
	gpad.buttons = data.get("buttons")
	gpad.axes = data.get("axes")

	axes = gpad.axes or []
	x = deadband(axes[0] if len(axes) > 0 else 0.0)
	y = -(deadband(axes[1] if len(axes) > 1 else 0.0))
	yaw = YAW_WEIGHT * (deadband(axes[2] if len(axes) > 2 else 0.0))
	z = deadband(axes[3] if len(axes) > 3 else 0.0)

	lt = gpad.button('LT') if len(gpad.buttons) > gpad.BUTTON_INDEX['LT'] else 0.0
	rt = gpad.button('RT') if len(gpad.buttons) > gpad.BUTTON_INDEX['RT'] else 0.0
	roll = ROLL_WEIGHT * (rt - lt)

	set_outputs_from_controls([x, y, z, roll, yaw])

	lb = gpad.button('LB') if len(gpad.buttons) > gpad.BUTTON_INDEX['LB'] else 0
	rb = gpad.button('RB') if len(gpad.buttons) > gpad.BUTTON_INDEX['RB'] else 0

	new_pwm = servo_pwm
	if rb:
		new_pwm = 1200
	elif lb:
		new_pwm = 600

	if new_pwm != servo_pwm:
		servo_pwm = new_pwm
		set_servo_angle(servo_pwm)

if __name__ == "__main__":
    import subprocess, atexit, os, signal
    from werkzeug.serving import make_server

    ssl_ctx = (CERT_DIR / "cert.pem", CERT_DIR / "key.pem")

    # Start the Vite frontend dev server alongside the Flask server.
    # Only launch it from the parent/monitor process so it survives werkzeug
    # reloader restarts without trying to rebind port 5002 each time.
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        frontend_dir = BASE_DIR / "frontend"
        vite_proc = subprocess.Popen(["npm", "run", "dev"], cwd=str(frontend_dir))

        def _kill_vite():
            if vite_proc.poll() is None:
                vite_proc.terminate()
                vite_proc.wait()

        atexit.register(_kill_vite)

        def _sigterm_handler(signum, frame):
            _kill_vite()
            raise SystemExit(0)

        signal.signal(signal.SIGTERM, _sigterm_handler)

        # Start operator interface on port 5001 in a background thread.
        # Only in the parent process so it doesn't double-bind on reloader restart.
        operator_server = make_server(HOST, OPERATOR_PORT, operator_app, threaded=True, ssl_context=ssl_ctx)
        operator_thread = threading.Thread(target=operator_server.serve_forever, daemon=True)
        operator_thread.start()
        log.info("Operator interface running on https://%s:%d", HOST, OPERATOR_PORT)

    extra_files = [str(path) for path in iter_watched_files()]
    socketio.run(
            app,
            host=HOST,
            port=PORT,
            ssl_context=ssl_ctx,
            debug=False,
            use_reloader=True,
            allow_unsafe_werkzeug=True,
            extra_files=extra_files
    )
