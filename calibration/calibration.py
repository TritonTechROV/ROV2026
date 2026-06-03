"""
ChArUco Board Camera Calibration Script
========================================
Board:         8x10 squares
Square length: 0.02286 m
Marker length: 0.01778 m
Resolution:    1920 x 1080
"""

import cv2
import numpy as np
import glob
import os
import json
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BOARD_COLS        = 8          # number of squares horizontally
BOARD_ROWS        = 10         # number of squares vertically
SQUARE_LENGTH     = 0.02286      # metres
MARKER_LENGTH     = 0.01778     # metres
IMAGE_WIDTH       = 1920
IMAGE_HEIGHT      = 1080
IMAGE_SIZE        = (IMAGE_WIDTH, IMAGE_HEIGHT)

ARUCO_DICT_ID     = cv2.aruco.DICT_4X4_50

# Folder containing calibration images (change as needed)
IMAGES_GLOB       = "calib_images/*.jpg"   # supports *.png, *.bmp, etc.

# Output file for calibration results
OUTPUT_JSON       = "calibration_result.json"
OUTPUT_NPZ        = "calibration_result.npz"


# ---------------------------------------------------------------------------
# Helper – build board and detector
# ---------------------------------------------------------------------------
def create_board_and_detector():
    aruco_dict   = cv2.aruco.getPredefinedDictionary(ARUCO_DICT_ID)
    board        = cv2.aruco.CharucoBoard(
        (BOARD_COLS, BOARD_ROWS),
        SQUARE_LENGTH,
        MARKER_LENGTH,
        aruco_dict,
    )

    aruco_params = cv2.aruco.DetectorParameters()
    # Slightly relaxed thresholds help with varied lighting
    aruco_params.adaptiveThreshWinSizeMin  = 3
    aruco_params.adaptiveThreshWinSizeMax  = 53
    aruco_params.adaptiveThreshWinSizeStep = 4
    aruco_params.minMarkerPerimeterRate    = 0.02
    aruco_params.maxMarkerPerimeterRate    = 4.0

    charuco_params           = cv2.aruco.CharucoParameters()
    charuco_params.minMarkers = 2          # require at least 2 markers per corner

    detector = cv2.aruco.CharucoDetector(board, charuco_params, aruco_params)
    return aruco_dict, board, detector


# ---------------------------------------------------------------------------
# Step 1 – collect corners from all images
# ---------------------------------------------------------------------------
def collect_corners(image_paths, board, detector, visualise=False):
    all_charuco_corners = []
    all_charuco_ids     = []
    used_images         = []

    print(f"\nProcessing {len(image_paths)} image(s)...")

    for img_path in sorted(image_paths):
        img  = cv2.imread(img_path)
        if img is None:
            print(f"  [WARN] Could not read: {img_path}")
            continue

        # Resize if the image does not match the expected resolution
        h, w = img.shape[:2]
        if (w, h) != IMAGE_SIZE:
            img = cv2.resize(img, IMAGE_SIZE, interpolation=cv2.INTER_AREA)
            print(f"  [INFO] Resized {os.path.basename(img_path)} from {w}x{h} to {IMAGE_SIZE[0]}x{IMAGE_SIZE[1]}")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        charuco_corners, charuco_ids, marker_corners, marker_ids = detector.detectBoard(gray)

        if (
            charuco_ids is not None
            and charuco_corners is not None
            and len(charuco_ids) >= 4          # need enough corners for calibration
        ):
            all_charuco_corners.append(charuco_corners)
            all_charuco_ids.append(charuco_ids)
            used_images.append(img_path)
            print(f"  [OK ] {os.path.basename(img_path):40s}  corners detected: {len(charuco_ids)}")

            if visualise:
                vis = img.copy()
                cv2.aruco.drawDetectedCornersCharuco(vis, charuco_corners, charuco_ids)
                cv2.imshow("ChArUco detection – press any key", vis)
                cv2.waitKey(0)
        else:
            n = len(charuco_ids) if charuco_ids is not None else 0
            print(f"  [SKIP] {os.path.basename(img_path):40s}  corners detected: {n} (need ≥ 4)")

    if visualise:
        cv2.destroyAllWindows()

    return all_charuco_corners, all_charuco_ids, used_images


# ---------------------------------------------------------------------------
# Step 2 – calibrate
# ---------------------------------------------------------------------------
def calibrate(board, all_corners, all_ids, image_size):
    print("\nRunning calibration…")

    # Initial guess: principal point at image centre, focal length ~ image width
    fx = fy = float(image_size[0])
    cx, cy  = image_size[0] / 2.0, image_size[1] / 2.0
    camera_matrix_init = np.array(
        [[fx,  0, cx],
         [ 0, fy, cy],
         [ 0,  0,  1]], dtype=np.float64
    )
    dist_coeffs_init = np.zeros((8, 1), dtype=np.float64)

    flags = (
        cv2.CALIB_USE_INTRINSIC_GUESS | cv2.CALIB_RATIONAL_MODEL
        # Uncomment lines below to fix specific parameters during optimisation:
        # | cv2.CALIB_FIX_PRINCIPAL_POINT
        # | cv2.CALIB_FIX_ASPECT_RATIO
        # | cv2.CALIB_ZERO_TANGENT_DIST
    )

    rms, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.aruco.calibrateCameraCharuco(
        charucoCorners  = all_corners,
        charucoIds      = all_ids,
        board           = board,
        imageSize       = image_size,
        cameraMatrix    = camera_matrix_init,
        distCoeffs      = dist_coeffs_init,
        flags           = flags,
    )

    return rms, camera_matrix, dist_coeffs, rvecs, tvecs


# ---------------------------------------------------------------------------
# Step 3 – per-image reprojection error
# ---------------------------------------------------------------------------
def reprojection_errors(board, all_corners, all_ids, rvecs, tvecs,
                        camera_matrix, dist_coeffs, used_images):
    errors = []
    obj_points = board.getChessboardCorners()

    for i, (corners, ids) in enumerate(zip(all_corners, all_ids)):
        obj_pts = obj_points[ids.flatten()]
        projected, _ = cv2.projectPoints(
            obj_pts, rvecs[i], tvecs[i], camera_matrix, dist_coeffs
        )
        err = cv2.norm(corners, projected, cv2.NORM_L2) / np.sqrt(len(corners))
        errors.append(err)
        print(f"  {os.path.basename(used_images[i]):40s}  reprojection error: {err:.4f} px")

    return errors


# ---------------------------------------------------------------------------
# Step 4 – save results
# ---------------------------------------------------------------------------
def save_results(camera_matrix, dist_coeffs, rms, per_image_errors,
                 used_images, image_size):
    # --- JSON (human-readable) ---
    result = {
        "image_size":          list(image_size),
        "rms_reprojection_error": rms,
        "mean_reprojection_error": float(np.mean(per_image_errors)),
        "camera_matrix": camera_matrix.tolist(),
        "dist_coeffs":   dist_coeffs.flatten().tolist(),
        "used_images":   [str(p) for p in used_images],
        "per_image_errors": {
            os.path.basename(p): round(e, 6)
            for p, e in zip(used_images, per_image_errors)
        },
    }
    with open(OUTPUT_JSON, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nCalibration saved → {OUTPUT_JSON}")

    # --- NumPy archive ---
    np.savez(
        OUTPUT_NPZ,
        camera_matrix = camera_matrix,
        dist_coeffs   = dist_coeffs,
        image_size    = np.array(image_size),
        rms           = rms,
    )
    print(f"Calibration saved → {OUTPUT_NPZ}")


# ---------------------------------------------------------------------------
# Step 5 – optional undistortion preview
# ---------------------------------------------------------------------------
def undistort_preview(camera_matrix, dist_coeffs, image_path, image_size):
    img = cv2.imread(image_path)
    if img is None:
        return
    if tuple(img.shape[1::-1]) != image_size:
        img = cv2.resize(img, image_size)

    h, w = img.shape[:2]
    new_mtx, roi = cv2.getOptimalNewCameraMatrix(
        camera_matrix, dist_coeffs, (w, h), alpha=0
    )
    undistorted = cv2.undistort(img, camera_matrix, dist_coeffs, None, new_mtx)

    x, y, rw, rh = roi
    undistorted = undistorted[y:y+rh, x:x+rw]

    combined = np.hstack([
        cv2.resize(img,         (640, 360)),
        cv2.resize(undistorted, (640, 360)),
    ])
    cv2.putText(combined, "Original", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.putText(combined, "Undistorted", (650, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.imshow("Undistortion preview – press any key", combined)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    aruco_dict, board, detector = create_board_and_detector()

    image_paths = glob.glob(IMAGES_GLOB)
    if not image_paths:
        print(f"\n[ERROR] No images found matching '{IMAGES_GLOB}'.")
        print("        Place your calibration images in the expected folder and re-run.")
        return

    all_corners, all_ids, used_images = collect_corners(
        image_paths, board, detector, visualise=False
    )

    if len(used_images) < 5:
        print(f"\n[ERROR] Only {len(used_images)} usable image(s). Need at least 5.")
        return

    rms, camera_matrix, dist_coeffs, rvecs, tvecs = calibrate(
        board, all_corners, all_ids, IMAGE_SIZE
    )

    print(f"\n{'='*60}")
    print(f"RMS reprojection error : {rms:.4f} px  (good < 1.0 px)")
    print(f"\nCamera matrix:\n{camera_matrix}")
    print(f"\nDistortion coefficients:\n{dist_coeffs.flatten()}")
    print(f"{'='*60}")

    print("\nPer-image reprojection errors:")
    per_image_errors = reprojection_errors(
        board, all_corners, all_ids, rvecs, tvecs,
        camera_matrix, dist_coeffs, used_images
    )
    print(f"\nMean per-image error: {np.mean(per_image_errors):.4f} px")

    save_results(camera_matrix, dist_coeffs, rms, per_image_errors,
                 used_images, IMAGE_SIZE)

    # Uncomment to preview undistortion on the first used image:
    # undistort_preview(camera_matrix, dist_coeffs, used_images[0], IMAGE_SIZE)


if __name__ == "__main__":
    main()
