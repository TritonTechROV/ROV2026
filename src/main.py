from pathlib import Path

from flask import Flask, Response, render_template

from vision.camera import generate_frames

app = Flask(__name__)

@app.route("/")
def index():
        return render_template("dashboard.html")

@app.route("/video_feed")
def video_feed():
	return Response(
		generate_frames(),
		mimetype="multipart/x-mixed-replace; boundary=frame",
	)

if __name__ == "__main__":
	app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
