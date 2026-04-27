from pathlib import Path
import logging, json

from flask import Flask, Response, jsonify, render_template
from flask_socketio import SocketIO

from vision.camera import generate_frames, is_camera_connected

# setup - logger
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("pi")

# setup - paths
BASE_DIR = Path(__file__).resolve().parent
CERT_DIR = BASE_DIR / "certs"

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
	return render_template("dashboard.html")

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

@socketio.on('controller')
def handle_controller(data):
        buttons = data.get("buttons") or []
        axes = data.get("axes") or []
        log.info(f"axes: {axes}")
        log.info(f"buttons: {buttons}")


if __name__ == "__main__":
    extra_files = [str(path) for path in iter_watched_files()]
    socketio.run(
            app,
            host="0.0.0.0",
            port=5000,
            ssl_context=(CERT_DIR / "cert.pem", CERT_DIR / "key.pem"),
            debug=False,
            use_reloader=True,
            allow_unsafe_werkzeug=True,
            extra_files=extra_files
    )
