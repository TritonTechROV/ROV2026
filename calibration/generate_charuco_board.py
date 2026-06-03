import cv2
import cv2.aruco as aruco
import numpy as np
import struct
import zlib

def set_png_dpi(file_path, dpi):
    """Injects pHYs chunk into PNG to set DPI metadata."""
    with open(file_path, 'rb') as f:
        data = f.read()
    ppm = int(dpi / 0.0254) # Pixels per meter
    chunk_type = b'pHYs'
    chunk_data = struct.pack('>IIB', ppm, ppm, 1)
    chunk_crc = zlib.crc32(chunk_type + chunk_data) & 0xffffffff
    chunk = struct.pack('>I', 9) + chunk_type + chunk_data + struct.pack('>I', chunk_crc)
    new_data = data[:33] + chunk + data[33:]
    with open(file_path, 'wb') as f:
        f.write(new_data)

def generate_charuco_board():
    # Configuration
    dpi = 300
    squares_x = 8
    squares_y = 10
    square_length_in = 0.9
    marker_length_in = 0.7
    filename = "charuco_board.png"

    # Calculate pixel dimensions based on DPI
    width_px = int(squares_x * square_length_in * dpi)
    height_px = int(squares_y * square_length_in * dpi)

    # Generate Board
    dictionary = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
    board = aruco.CharucoBoard((squares_x, squares_y), square_length_in, marker_length_in, dictionary)
    board_img = board.generateImage((width_px, height_px))

    # Save and set DPI
    cv2.imwrite(filename, board_img)
    set_png_dpi(filename, dpi)

    print(f"Generated: {filename}")
    print(f"Size: {squares_x * square_length_in}\" x {squares_y * square_length_in}\" ({width_px}x{height_px} px)")
    print(f"DPI: {dpi}")
    print("Tip: Print at 'Actual Size' / 100% scale.")

if __name__ == "__main__":
    generate_charuco_board()
