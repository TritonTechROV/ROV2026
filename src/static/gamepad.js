/* notes on the 046d-c21d-Logitech:
 * - The controller has a backswitch with a X and D label, X will suffix the controller
 *   with "Gamepad F310", this mode will treat the left/right triggers as button signals. (on or off)
 *   On the other hand, the D label, suffixed with "Gamepad F310", will treat the triggers
 *   as analog signals. This is why there are RT/LT labels for axes and buttons.
 * - There is also a mode button right under the back button in the center of the controller, this will
 *   swap the D-Pad and the left-joystick, meaning the D-Pad will show up as left-joystick analog signals,
 *   while the left-joystick will show up as button D-Pad buttons. This swapped state is indicated by a green
 *   light next to the mode button
 * - overall, please keep the controller with the backswitch on the X side and the mode toggle to be off
 */

var buttonLabels = [
    "A",     // 0
    "B",     // 1
    "Y",     // 2
    "X",     // 3
    "LB",    // 4
    "RB",    // 5
    "LT",    // 6 → Left Trigger
    "RT",    // 7 → Right Trigger
    "BACK",  // 8
    "START", // 9
    "LS",    // 10 → left stick press
    "RS",    // 11 → right stick press
    "DU",    // 12 D-pad Up
    "DD",    // 13 D-pad Down
    "DL",    // 14 D-pad Left
    "DR",    // 15 D-pad Right
    "HOME"   // 16
];

/*
  lower x value = more left
  lower y value = more down
*/
var axisLabels = [
    "LS X",   // 0 → Left stick horizontal
    "LS Y",   // 1 → Left stick vertical
    "RS X",   // 2 → Right stick horizontal
    "RS Y",   // 3 → Right stick vertical
    "LT",     // 4 → Left Trigger Analog
    "RT"      // 5 → Right Trigger Analog
];

var haveEvents = 'GamepadEvent' in window;
var haveWebkitEvents = 'WebKitGamepadEvent' in window;
var controllers = {};
var rAF = window.mozRequestAnimationFrame ||
    window.webkitRequestAnimationFrame ||
    window.requestAnimationFrame;

function connecthandler(e) {
    addgamepad(e.gamepad);
}

function addgamepad(gamepad) {
    controllers[gamepad.index] = gamepad;

    var d = document.createElement("div");
    d.setAttribute("id", "controller" + gamepad.index);

    var t = document.createElement("h1");
    t.appendChild(document.createTextNode("gamepad: " + gamepad.id));
    d.appendChild(t);
    var b = document.createElement("div");
    b.className = "buttons";
    for (var i = 0; i < gamepad.buttons.length; i++) {
        var e = document.createElement("span");
        e.className = "button";
        e.innerHTML = buttonLabels[i] || ("B" + i);
        b.appendChild(e);
    }
    d.appendChild(b);
    var a = document.createElement("div");
    a.className = "axes";
    for (i = 0; i < gamepad.axes.length; i++) {
        // axis container for both label and bar
        var axisContainer = document.createElement("div");
        axisContainer.className = "axis-container";

        // axis bar
        var e = document.createElement("meter");
        e.className = "axis";
        e.setAttribute("min", "-1");
        e.setAttribute("max", "1");
        e.setAttribute("value", "0");

        // label for axis
        var label = document.createElement("div");
        label.className = "axis-label";
        label.innerText = axisLabels[i] || ("Axis " + i);

        // add elements to container
        axisContainer.appendChild(label);
        axisContainer.appendChild(e);

        a.appendChild(axisContainer);
    }
    d.appendChild(a);
    document.getElementById("start").style.display = "none";
    document.getElementById("controller-display").appendChild(d);
    rAF(updateStatus);
}

function disconnecthandler(e) {
    removegamepad(e.gamepad);
}

function removegamepad(gamepad) {
    var d = document.getElementById("controller" + gamepad.index);
    document.body.removeChild(d);
    delete controllers[gamepad.index];
}

function updateStatus() {
    scangamepads();
    for (j in controllers) {
        var controller = controllers[j];
        var d = document.getElementById("controller" + j);
        var buttons = d.getElementsByClassName("button");
        for (var i = 0; i < controller.buttons.length; i++) {
            var b = buttons[i];
            var val = controller.buttons[i];
            var pressed = val == 1.0;
            var touched = false;
            if (typeof (val) == "object") {
                pressed = val.pressed;
                if ('touched' in val) {
                    touched = val.touched;
                }
                val = val.value;
            }
            var pct = Math.round(val * 100) + "%";
            b.style.backgroundSize = pct + " " + pct;

            b.className = "button";
            if (pressed) {
                b.className += " pressed";
            }
            if (touched) {
                b.className += " touched";
            }
        }

        var axes = d.getElementsByClassName("axis");
        for (var i = 0; i < controller.axes.length; i++) {
            var a = axes[i];
            a.innerHTML = i + ": " + controller.axes[i].toFixed(4);
            a.setAttribute("value", controller.axes[i]);
        }
    }
    // printStatus();
    rAF(updateStatus);
}

function scangamepads() {
    var gamepads = navigator.getGamepads ? navigator.getGamepads() : (navigator.webkitGetGamepads ? navigator.webkitGetGamepads() : []);
    for (var i = 0; i < gamepads.length; i++) {
        if (gamepads[i] && (gamepads[i].index in controllers)) {
            controllers[gamepads[i].index] = gamepads[i];
        }
    }
}

var prev = {};
function printStatus() {
    var gamepads = navigator.getGamepads();

    if (gamepads.length == 0)
        return "no gamepads detected :(";

    for (idx in gamepads) {
        const gp = gamepads[idx];
        // skip null values
        if (!gp) continue;

        // initialize prev values
        if (!prev[idx]) {
            prev[idx] = {
                buttons: [],
                axes: []
            };
        }

        // buttons
        gp.buttons.forEach((b, i) => {
            if (prev[idx].buttons[i] !== b.value) {
                console.log(
                    i + ";",
                    buttonLabels[i] + ":",
                    b.value
                )
            }
        });

        // axes
        gp.axes.forEach((a, i) => {
            if (prev[idx].axes[i] !== a) {
                console.log(
                    i + ";",
                    axisLabels[i] + ":",
                    a
                )
            }
        });

        // update previous values
        prev[gp.index].buttons = gp.buttons.map(b => b.value);
        prev[gp.index].axes = [...gp.axes];
    }
}


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

if (haveEvents) {
    window.addEventListener("gamepadconnected", connecthandler);
    window.addEventListener("gamepaddisconnected", disconnecthandler);
} else if (haveWebkitEvents) {
    window.addEventListener("webkitgamepadconnected", connecthandler);
    window.addEventListener("webkitgamepaddisconnected", disconnecthandler);
} else {
    setInterval(scangamepads, 500);
}
