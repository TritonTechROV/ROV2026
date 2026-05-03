from controller import Controller

from pathlib import Path
import logging, json

from flask import Flask, Response, jsonify, render_template
from flask_socketio import SocketIO

from thruster_controller import set_outputs_from_controls
from vision.camera import generate_frames, is_camera_connected

# setup - logger
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("pi")

# setup - config consts
BASE_DIR = Path(__file__).resolve().parent
CERT_DIR = BASE_DIR / "certs"

HOST = "0.0.0.0"
PORT = 5000

# flask - create app
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

@app.route("/data")
def data():
        with open("src/config/xbox.json") as f:
                labels = json.load(f)
        return jsonify(labels)


@app.route("/video_feed")
def video_feed():
	return Response(
		generate_frames(),
		mimetype="multipart/x-mixed-replace; boundary=frame",
	)

@app.route("/camera_status")
def camera_status():
	return jsonify({"connected": is_camera_connected()})


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

def deadband(value, threshold=DEADBAND_THRESHOLD):
        if abs(value) <= threshold:
                return 0.0
        sign = 1.0 if value > 0 else -1.0
        return ((abs(value) - threshold) / (1.0 - threshold)) * sign

@socketio.on('controller')
def handle_controller(data):
	gpad.buttons = data.get("buttons")
	gpad.axes = data.get("axes")

	axes = gpad.axes or []
	x = deadband(axes[0] if len(axes) > 0 else 0.0)
	y = -(deadband(axes[1] if len(axes) > 1 else 0.0))
	yaw = YAW_WEIGHT * (deadband(axes[2] if len(axes) > 2 else 0.0))
	z = deadband(axes[3] if len(axes) > 3 else 0.0)
	roll = 0.0
	if len(axes) > 5:
		roll = ROLL_WEIGHT * (deadband(axes[5] if len(axes) > 5 else 0.0) - deadband(axes[4] if len(axes) > 4 else 0.0))

	set_outputs_from_controls([x, y, z, roll, yaw])

if __name__ == "__main__":
    extra_files = [str(path) for path in iter_watched_files()]
    socketio.run(
            app,
            host=HOST,
            port=PORT,
            ssl_context=(CERT_DIR / "cert.pem", CERT_DIR / "key.pem"),
            debug=False,
            use_reloader=True,
            allow_unsafe_werkzeug=True,
            extra_files=extra_files
    )
