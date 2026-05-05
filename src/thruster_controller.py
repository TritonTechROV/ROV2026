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
        MAX_SUM = 2.0
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
        for i in range(len(outputs)):
                send_to_thruster(THRUSTER_NAMES[i], outputs[i])
        
        print(f"Controls: {controls}, Thruster outputs: {outputs}")

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
