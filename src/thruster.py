import serial

def send_to_thruster(thruster, speed):
        ser_path = "/dev/ttyUSB1"
        # dev path | uart rate mhz(?) | 1(ms?) timeout
        ser = serial.Serial(ser_path, 115200, timeout = 1)
        ser.write(f"set {thruster} {speed}\n".encode("ascii"))
        # set <thruster> <float [-1, 1]>
        # -1 backwards, 1 forwards, 0 stopped
