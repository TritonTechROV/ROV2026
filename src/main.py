from pathlib import Path

from flask import Flask, Response

from vision.camera import generate_frames

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent


@app.route("/")
def index():
	return (BASE_DIR / "dashboard.html").read_text(encoding="utf-8")


@app.route("/video_feed")
def video_feed():
	return Response(
		generate_frames(),
		mimetype="multipart/x-mixed-replace; boundary=frame",
	)


if __name__ == "__main__":
	app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

