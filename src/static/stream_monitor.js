window.addEventListener("DOMContentLoaded", function () {
    const firstTabButton = document.querySelector(".tab .tablinks");
    if (firstTabButton) {
        firstTabButton.click();
    }
});

(function liveReload() {
    let currentRevision = null;
    let sawBackendDisconnect = false;
    const stream = document.getElementById("camera-stream");
    const cameraStatus = document.getElementById("camera-status");

    function showCameraDisconnected() {
        stream.style.display = "none";
        cameraStatus.style.display = "block";
    }

    function showCameraConnected() {
        stream.style.display = "inline-block";
        cameraStatus.style.display = "none";
    }

    function restartStream() {
        stream.src = "/video_feed?t=" + Date.now();
    }

    async function refreshCameraStatus() {
        try {
            const response = await fetch("/camera_status", {
                cache: "no-store",
            });
            if (!response.ok) {
                showCameraDisconnected();
                return;
            }

            const payload = await response.json();
            if (payload.connected) {
                showCameraConnected();
                if (!stream.complete || stream.naturalWidth === 0) {
                    restartStream();
                }
            } else {
                showCameraDisconnected();
            }
        } catch (error) {
            showCameraDisconnected();
        }
    }

    stream.addEventListener("error", showCameraDisconnected);

    async function checkRevision() {
        try {
            const response = await fetch("/__source_revision", {
                cache: "no-store",
            });

            if (!response.ok) {
                return;
            }

            const payload = await response.json();
            const nextRevision = String(payload.revision);

            if (sawBackendDisconnect) {
                window.location.reload();
                return;
            }

            if (currentRevision === null) {
                currentRevision = nextRevision;
                return;
            }

            if (nextRevision !== currentRevision) {
                window.location.reload();
            }
        } catch (error) {
            sawBackendDisconnect = true;
        }
    }

    setInterval(checkRevision, 1000);
    checkRevision();
    setInterval(refreshCameraStatus, 2000);
    refreshCameraStatus();
})();
