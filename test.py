import serial

ser = serial.Serial("/dev/ttyUSB1", 115200, timeout = 1)
while True:
	ser.write("set fl 0.75\n".encode("ascii"))
