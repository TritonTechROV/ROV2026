window.addEventListener("DOMContentLoaded", function () {
    const firstTabButton = document.querySelector(".tab .tablinks");
    if (firstTabButton) {
        firstTabButton.click();
    }
});

(function liveReload() {
    let currentRevision = null;
    let sawBackendDisconnect = false;
    const mainStream = document.getElementById("main-camera-stream");
    const mainStatus = document.getElementById("main-camera-status");

    function showCameraDisconnected() {
        mainStream.style.display = "none";
        mainStatus.style.display = "block";
    }

    function showCameraConnected() {
        mainStream.style.display = "inline-block";
        mainStatus.style.display = "none";
    }

    function restartStream() {
        mainStream.src = "/main_video_feed?t=" + Date.now();
    }

    async function refreshCameraStatus() {
        try {
            const response = await fetch("/main_camera_status", {
                cache: "no-store",
            });
            if (!response.ok) {
                showCameraDisconnected();
                return;
            }

            const payload = await response.json();
            if (payload.connected) {
                showCameraConnected();
                if (!mainStream.complete || mainStream.naturalWidth === 0) {
                    restartStream();
                }
            } else {
                showCameraDisconnected();
            }
        } catch (error) {
            showCameraDisconnected();
        }
    }

    mainStream.addEventListener("error", showCameraDisconnected);

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
