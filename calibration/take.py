"""
Calibration Image Capture — Flask Web UI
=========================================
Run:   python capture_calib_images.py
Open:  http://localhost:6000

Click Capture or press SPACE on the page to save frames to calib_images/.
Click Quit or press ESC to stop the server.
"""

import os
import time
import threading
import cv2
from flask import Flask, Response, jsonify, render_template_string

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CAMERA_INDEX   = 0
CAPTURE_WIDTH  = 1920
CAPTURE_HEIGHT = 1080
SAVE_DIR       = "calib_images"
IMG_PREFIX     = "calib"
IMG_EXT        = ".jpg"
JPEG_QUALITY   = 97
FLASK_PORT     = 5001

# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Calibration Capture</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Barlow:wght@300;600&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:      #0a0c0f;
    --surface: #111418;
    --border:  #1e2530;
    --accent:  #00e5ff;
    --accent2: #ff3d71;
    --text:    #c8d6e5;
    --dim:     #4a5568;
    --green:   #00ff88;
    --mono:    'Share Tech Mono', monospace;
    --sans:    'Barlow', sans-serif;
  }

  html, body { height: 100%; background: var(--bg); color: var(--text);
    font-family: var(--sans); font-weight: 300; overflow: hidden; }

  body::after {
    content: ''; position: fixed; inset: 0;
    background: repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,.07) 2px,rgba(0,0,0,.07) 4px);
    pointer-events: none; z-index: 999;
  }

  .layout {
    display: grid;
    grid-template-columns: 1fr 280px;
    grid-template-rows: 48px 1fr;
    height: 100vh;
  }

  header {
    grid-column: 1 / -1;
    display: flex; align-items: center; gap: 16px;
    padding: 0 20px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
  }
  header .logo { font-family: var(--mono); font-size: 13px; color: var(--accent);
    letter-spacing: .12em; text-transform: uppercase; }
  header .sep { flex: 1; }
  .pill { font-family: var(--mono); font-size: 11px; padding: 3px 10px;
    border-radius: 20px; border: 1px solid var(--border); color: var(--dim); letter-spacing: .08em; }
  .pill.live { border-color: var(--green); color: var(--green); }
  .pill.live::before { content: '● '; }

  .feed-wrap { position: relative; background: #000;
    display: flex; align-items: center; justify-content: center; overflow: hidden; }
  .feed-wrap img { width: 100%; height: 100%; object-fit: contain; display: block; }

  .flash { position: absolute; inset: 0; background: #fff; opacity: 0;
    pointer-events: none; transition: opacity 60ms ease-out; }
  .flash.active { opacity: 0.55; }

  .corner { position: absolute; width: 22px; height: 22px;
    border-color: var(--accent); border-style: solid; opacity: .6; }
  .corner.tl { top:12px; left:12px;   border-width: 2px 0 0 2px; }
  .corner.tr { top:12px; right:12px;  border-width: 2px 2px 0 0; }
  .corner.bl { bottom:12px; left:12px;  border-width: 0 0 2px 2px; }
  .corner.br { bottom:12px; right:12px; border-width: 0 2px 2px 0; }

  .sidebar { background: var(--surface); border-left: 1px solid var(--border);
    display: flex; flex-direction: column; padding: 20px 16px; gap: 20px; overflow: hidden; }

  .stat-block { display: flex; flex-direction: column; gap: 10px; }
  .stat { display: flex; flex-direction: column; gap: 2px; padding: 12px;
    background: var(--bg); border: 1px solid var(--border); border-radius: 4px; }
  .stat .label { font-family: var(--mono); font-size: 10px; color: var(--dim);
    letter-spacing: .1em; text-transform: uppercase; }
  .stat .value { font-family: var(--mono); font-size: 22px; color: var(--accent); line-height: 1; }
  .stat .value.small { font-size: 13px; color: var(--text); }

  .divider { height: 1px; background: var(--border); }

  .hint { font-family: var(--mono); font-size: 11px; color: var(--dim); line-height: 1.7; }
  .hint span { color: var(--accent); }

  .btn-group { display: flex; flex-direction: column; gap: 10px; margin-top: auto; }
  .btn { width: 100%; padding: 12px; border: none; border-radius: 3px;
    font-family: var(--mono); font-size: 13px; letter-spacing: .1em; cursor: pointer;
    text-transform: uppercase; transition: filter 120ms, transform 80ms; }
  .btn:active { transform: scale(.97); }
  .btn-capture { background: var(--accent); color: #000; font-weight: 700; }
  .btn-capture:hover { filter: brightness(1.15); }
  .btn-quit { background: transparent; color: var(--accent2); border: 1px solid var(--accent2); }
  .btn-quit:hover { background: rgba(255,61,113,.08); }

  .log-wrap { flex: 1; overflow: hidden; display: flex; flex-direction: column; gap: 6px; }
  .log-label { font-family: var(--mono); font-size: 10px; color: var(--dim);
    letter-spacing: .1em; text-transform: uppercase; }
  #log { flex: 1; overflow-y: auto; display: flex; flex-direction: column-reverse;
    gap: 3px; scrollbar-width: thin; scrollbar-color: var(--border) transparent; }
  .log-entry { font-family: var(--mono); font-size: 11px; color: var(--dim);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .log-entry.ok { color: var(--green); }
</style>
</head>
<body>
<div class="layout">

  <header>
    <span class="logo">◈ ChArUco Capture</span>
    <span class="sep"></span>
    <span class="pill" id="res-pill">{{ width }}×{{ height }}</span>
    <span class="pill live" id="status-pill">LIVE</span>
  </header>

  <div class="feed-wrap">
    <img id="feed" src="/video_feed" alt="camera feed">
    <div class="flash" id="flash"></div>
    <div class="corner tl"></div><div class="corner tr"></div>
    <div class="corner bl"></div><div class="corner br"></div>
  </div>

  <div class="sidebar">
    <div class="stat-block">
      <div class="stat">
        <span class="label">Captured</span>
        <span class="value" id="count">{{ count }}</span>
      </div>
      <div class="stat">
        <span class="label">Save directory</span>
        <span class="value small">{{ save_dir }}/</span>
      </div>
    </div>

    <div class="divider"></div>

    <div class="hint">
      <span>SPACE</span> — capture frame<br>
      <span>ESC</span> &nbsp;— quit server
    </div>

    <div class="log-wrap">
      <span class="log-label">Recent saves</span>
      <div id="log"></div>
    </div>

    <div class="btn-group">
      <button class="btn btn-capture" id="btn-capture" onclick="capture()">⊕ Capture</button>
      <button class="btn btn-quit" onclick="quit()">✕ Quit</button>
    </div>
  </div>

</div>
<script>
  document.addEventListener('keydown', e => {
    if (e.code === 'Space')  { e.preventDefault(); capture(); }
    if (e.code === 'Escape') { quit(); }
  });

  function triggerFlash() {
    const f = document.getElementById('flash');
    f.classList.add('active');
    setTimeout(() => f.classList.remove('active'), 120);
  }

  async function capture() {
    triggerFlash();
    document.getElementById('btn-capture').disabled = true;
    try {
      const r = await fetch('/capture', { method: 'POST' });
      const d = await r.json();
      if (d.ok) {
        document.getElementById('count').textContent = d.count;
        addLog(d.filename, true);
      } else { addLog('capture failed', false); }
    } catch(e) { addLog('error: ' + e.message, false); }
    document.getElementById('btn-capture').disabled = false;
  }

  async function quit() {
    await fetch('/quit', { method: 'POST' }).catch(() => {});
    document.getElementById('status-pill').textContent = 'STOPPED';
    document.getElementById('status-pill').classList.remove('live');
  }

  function addLog(msg, ok) {
    const el = document.createElement('div');
    el.className = 'log-entry' + (ok ? ' ok' : '');
    el.textContent = new Date().toTimeString().slice(0,8) + '  ' + msg;
    document.getElementById('log').prepend(el);
  }
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Camera thread
# ---------------------------------------------------------------------------
class Camera:
    def __init__(self):
        self.cap = cv2.VideoCapture(CAMERA_INDEX)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAPTURE_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_HEIGHT)
        self.actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.lock  = threading.Lock()
        self.frame = None
        self._stop = False
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        while not self._stop:
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.frame = frame
            else:
                time.sleep(0.01)

    def get_frame(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()

    def release(self):
        self._stop = True
        self.cap.release()


def _next_index():
    existing = [f for f in os.listdir(SAVE_DIR) if f.startswith(IMG_PREFIX) and f.endswith(IMG_EXT)]
    nums = []
    for name in existing:
        try: nums.append(int(name[len(IMG_PREFIX):name.rfind(".")]))
        except ValueError: pass
    return max(nums) + 1 if nums else 0


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
os.makedirs(SAVE_DIR, exist_ok=True)
app    = Flask(__name__)
camera = Camera()


def gen_frames():
    while True:
        frame = camera.get_frame()
        if frame is None:
            time.sleep(0.03)
            continue
        ret, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if not ret:
            continue
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")


@app.route("/")
def index():
    return render_template_string(HTML,
        width=camera.actual_w, height=camera.actual_h,
        count=_next_index(), save_dir=SAVE_DIR)


@app.route("/video_feed")
def video_feed():
    return Response(gen_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/capture", methods=["POST"])
def capture():
    frame = camera.get_frame()
    if frame is None:
        return jsonify(ok=False, error="No frame available")
    idx      = _next_index()
    filename = f"{IMG_PREFIX}{idx:04d}{IMG_EXT}"
    path     = os.path.join(SAVE_DIR, filename)
    cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    print(f"  Saved → {path}")
    return jsonify(ok=True, filename=filename, count=idx + 1)


@app.route("/quit", methods=["POST"])
def quit_server():
    def _shutdown():
        time.sleep(0.5)
        camera.release()
        os.kill(os.getpid(), 9)
    threading.Thread(target=_shutdown, daemon=True).start()
    return jsonify(ok=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Camera   : device {CAMERA_INDEX}  ({camera.actual_w}×{camera.actual_h})")
    print(f"Save dir : {os.path.abspath(SAVE_DIR)}/")
    print(f"Open     : http://localhost:{FLASK_PORT}\n")
    app.run(host="0.0.0.0", port=FLASK_PORT, threaded=True)
