import serial
import threading

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

SERIAL_PATH = "/dev/ttyUSB1"
ser = serial.Serial(SERIAL_PATH, 115200, timeout = 1)
serial_lock = threading.Lock()

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

# controls: [x, y, z, roll (right tilt positive), yaw (counterclockwise positive)]
def set_outputs_from_controls(controls):
        outputs = matrix_vector_mult(CONTROLS_TO_THRUSTER_TRANSFORMATION, controls)
        outputs = normalize_outputs(outputs)
        for i in range(len(outputs)):
                send_to_thruster(i + 1, outputs[i])

def send_to_thruster(thruster, speed):
        with serial_lock:
                # dev path | uart rate mhz(?) | 1(ms?) timeout
                ser.write(f"set {thruster} {speed:.4f}\n".encode("ascii"))
                # set <thruster> <float [-1, 1]>
                # -1 backwards, 1 forwards, 0 stopped
