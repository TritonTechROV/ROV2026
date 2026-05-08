import logging
import glob
import serial
import threading

log = logging.getLogger("pi")

# thruster IDs
# 1: front left
# 2: front right
# 3: mid left
# 4: mid right
# 5: back left
# 6: back right
CONTROLS_TO_THRUSTER_TRANSFORMATION = [
        [1, 1, 0, 0 , -1], # thruster 1 [x, y, z, roll (right tilt positive), yaw (counterclockwise positive)]
        [-1, 1, 0, 0, 1],
        [0, 0, 1, 1, 0],
        [0, 0, 1, -1, 0],
        [-1, 1, 0, 0, -1],
        [1, 1, 0, 0, 1]
]

THRUSTER_NAMES = ["fl", "fr", "ml", "mr", "bl", "br"]

SERIAL_PATH = "/dev/ttyUSB1"
ser = None
serial_lock = threading.Lock()
# Ramping configuration
RAMP_RATE = 1.0 # max change in speed units per second (0..1)
RAMP_FREQUENCY = 20.0  # Hz, how often to update outputs

# runtime ramp state
_ramp_lock = threading.Lock()
_current_speeds = [0.0 for _ in THRUSTER_NAMES]
_target_speeds = [0.0 for _ in THRUSTER_NAMES]
_ramp_thread = None
_ramp_thread_running = False


def find_and_open_serial():
        paths = []
        paths.extend(sorted(glob.glob("/dev/ttyUSB*")))
        paths.extend(sorted(glob.glob("/dev/ttyACM*")))
        if SERIAL_PATH not in paths:
                paths.append(SERIAL_PATH)

        for p in paths:
                try:
                        s = serial.Serial(p, 115200, timeout=1)
                        log.info("Opened thruster serial on %s", p)
                        return s
                except Exception as exc:
                        log.debug("Could not open %s: %s", p, exc)

        log.warning("No thruster serial device found among: %s", paths)
        return None


def get_serial_connection():
        global ser
        if ser is not None and getattr(ser, 'is_open', True):
                return ser
        ser = find_and_open_serial()
        return ser

def matrix_vector_mult(matrix, vector):
        result = []
        for row in matrix:
                axis_sum = 0.0
                for i in range(len(row)):
                        axis_sum += row[i] * vector[i]
                result.append(axis_sum)
        return result

def normalize_outputs(outputs):
        max_magnitude = max(abs(output) for output in outputs)
        if max_magnitude > 1:
                outputs = [output / max_magnitude for output in outputs]
        return outputs

def clamp_outputs(outputs):
        MAX_SUM = 4.0
        s = 0.0

        # absolute sum
        for i in range(len(outputs)):
                s += abs(outputs[i])

        if s == 0:
                return outputs

        if s > MAX_SUM:
                scalar = MAX_SUM / s
                for i in range(len(outputs)):
                        outputs[i] = outputs[i] * scalar

        return outputs

# controls: [x, y, z, roll (right tilt positive), yaw (counterclockwise positive)]
def set_outputs_from_controls(controls):
        outputs = matrix_vector_mult(CONTROLS_TO_THRUSTER_TRANSFORMATION, controls)
        outputs = normalize_outputs(outputs)
        outputs = clamp_outputs(outputs)
        # set targets for ramping thread instead of immediately writing to serial
        with _ramp_lock:
                for i in range(len(outputs)):
                        _target_speeds[i] = float(outputs[i])
        start_ramp_thread()

        print(f"Controls: {controls}, Thruster targets: {outputs}")

def send_to_thruster(thruster, speed):
        with serial_lock:
                command = f"set {thruster} {speed:.4f}\n".encode("ascii")
                log.info("Sending thruster command: %s %.4f", thruster, speed)
                connection = get_serial_connection()
                if connection is None:
                        log.warning("No serial connection available for thruster commands")
                        return

                try:
                        connection.write(command)
                        response = connection.readline().decode("ascii", errors="replace").strip()
                        if response:
                                log.info("ESP32 response: %s", response)
                except serial.SerialException as exc:
                        log.warning("Serial error when writing to %s: %s", getattr(connection, 'port', '<unknown>'), exc)
                # set <thruster> <float [-1, 1]>
                # -1 backwards, 1 forwards, 0 stopped


def _ramp_loop():
        global _current_speeds, _target_speeds, _ramp_thread_running
        _ramp_thread_running = True
        period = 1.0 / RAMP_FREQUENCY
        last = None
        try:
                while True:
                        now = time.time()
                        if last is None:
                                dt = period
                        else:
                                dt = now - last
                                if dt <= 0:
                                        dt = period
                        last = now

                        max_delta = RAMP_RATE * dt
                        to_send = []
                        with _ramp_lock:
                                for i in range(len(_current_speeds)):
                                        t = _target_speeds[i]
                                        c = _current_speeds[i]
                                        diff = t - c
                                        if abs(diff) <= max_delta:
                                                c = t
                                        else:
                                                c += max_delta if diff > 0 else -max_delta
                                        # clip to [-1, 1]
                                        if c > 1.0:
                                                c = 1.0
                                        if c < -1.0:
                                                c = -1.0
                                        if abs(c - _current_speeds[i]) > 0.0005:
                                                _current_speeds[i] = c
                                                to_send.append((THRUSTER_NAMES[i], c))

                        # send outside ramp lock
                        for thruster, speed in to_send:
                                send_to_thruster(thruster, speed)

                        time.sleep(period)
        finally:
                _ramp_thread_running = False


def start_ramp_thread():
        global _ramp_thread
        if _ramp_thread is not None and _ramp_thread.is_alive():
                return
        # lazy import of time to avoid unused import earlier
        import time
        # assign time into module scope for loop
        globals()['time'] = time
        _ramp_thread = threading.Thread(target=_ramp_loop, daemon=True)
        _ramp_thread.start()