from pathlib import Path

from flask import Flask, Response, jsonify, render_template
from flask_socketio import SocketIO

from vision.camera import generate_frames, is_camera_connected

BASE_DIR = Path(__file__).resolve().parent
app = Flask(
	__name__,
	template_folder=str(BASE_DIR / "templates"),
	static_folder=str(BASE_DIR / "static"),
)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.jinja_env.auto_reload = True
socketio = SocketIO(app, cors_allowed_origins="*")


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


@socketio.on('connect')
def handle_connect():
        print("Client connected")

@socketio.on('controller')
def handle_controller(data):
        print("Controller data:", data)


@app.route("/")
def index():
	return render_template("dashboard.html")

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


if __name__ == "__main__":
    extra_files = [str(path) for path in iter_watched_files()]
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=True, extra_files=extra_files)
    socketio.run(app, port=5000, debug=False, use_reloader=False)
