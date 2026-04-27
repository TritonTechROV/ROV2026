function app_setup(data) {
    let lastData = {};
    function getStatus() {
        const gp = navigator.getGamepads()[0];
        if (!gp) return;

        const current = {
            buttons: gp.buttons.map(b => b.value),
            axes: gp.axes
        };

        if (JSON.stringify(current) !== JSON.stringify(lastData)) {
            lastData = current;
            socket.emit("controller", current);
        }
    }

    const socket = io();
    socket.on("connect", () => {
        console.log("Connected!");
        setInterval(getStatus, 50);
    });

    window.addEventListener("gamepadconnected", () => {
        console.log("Gamepad connected");
    });
}

fetch("/data")
    .then(response => response.json())
    .then(result => {
        app_setup(result);
        console.log(result);
    });
