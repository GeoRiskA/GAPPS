import cv2
import numpy as np
import csv
import os


def compute_dynamic_rois(image, center_ratio=0.5):
    """
    Compute four dynamic ROIs for the image based on a centre region.
    center_ratio defines the portion of the image considered as the centre.
    The centre region is split into four quadrants.
    Returns a list of ROIs as (x, y, w, h).
    """
    height, width = image.shape
    cx, cy = width // 2, height // 2
    center_w = int(width * center_ratio)
    center_h = int(height * center_ratio)
    top_left_x = cx - center_w // 2
    top_left_y = cy - center_h // 2

    # Split the centre region into four quadrants.
    roi_w = center_w // 2
    roi_h = center_h // 2
    rois = [
        (top_left_x, top_left_y, roi_w, roi_h),  # top-left quadrant
        (top_left_x + roi_w, top_left_y, roi_w, roi_h),  # top-right quadrant
        (top_left_x, top_left_y + roi_h, roi_w, roi_h),  # bottom-left quadrant
        (top_left_x + roi_w, top_left_y + roi_h, roi_w, roi_h)  # bottom-right quadrant
    ]
    return rois


def detect_mark_in_roi_SIFT(image, template, roi, ratio_thresh=0.75, min_matches=10):
    """
    Use SIFT to detect a fiducial mark in the ROI.
    - image: the full grayscale image.
    - template: the grayscale template of the fiducial mark.
    - roi: a tuple (x, y, w, h) defining the ROI in the image.
    Returns the centre coordinate (in image coordinates) and the number of good matches.
    If detection is not reliable, returns (None, number_of_good_matches).
    """
    x, y, w, h = roi
    roi_img = image[y:y + h, x:x + w]

    # Create SIFT detector.
    sift = cv2.SIFT_create()

    # Compute keypoints and descriptors for both ROI and template.
    kp_roi, des_roi = sift.detectAndCompute(roi_img, None)
    kp_temp, des_temp = sift.detectAndCompute(template, None)

    if des_roi is None or des_temp is None:
        return None, 0

    # BFMatcher using L2 norm (suitable for SIFT).
    bf = cv2.BFMatcher()
    matches = bf.knnMatch(des_temp, des_roi, k=2)

    # Apply Lowe's ratio test.
    good = []
    for m, n in matches:
        if m.distance < ratio_thresh * n.distance:
            good.append(m)

    if len(good) < min_matches:
        return None, len(good)

    # Use good matches to compute homography.
    src_pts = np.float32([kp_temp[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp_roi[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    if M is None:
        return None, len(good)

    # Map template corners to ROI coordinates.
    h_temp, w_temp = template.shape
    pts = np.float32([[0, 0], [w_temp, 0], [w_temp, h_temp], [0, h_temp]]).reshape(-1, 1, 2)
    dst = cv2.perspectiveTransform(pts, M)
    # Compute the centre of the transformed region.
    center_roi = np.mean(dst, axis=0)[0]
    # Convert to full image coordinates.
    center_image = (int(center_roi[0] + x), int(center_roi[1] + y))
    return center_image, len(good)


def process_image(image_path, template, ratio_thresh=0.75, min_matches=10):
    """
    Process one image: compute dynamic ROIs and run SIFT detection in each ROI.
    Returns a list of detection results and the loaded image.
    """
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        print(f"Could not load image: {image_path}")
        return [], None

    rois = compute_dynamic_rois(image, center_ratio=0.5)
    results = []
    for idx, roi in enumerate(rois):
        center, good_matches = detect_mark_in_roi_SIFT(image, template, roi, ratio_thresh, min_matches)
        results.append({
            'roi_index': idx,
            'center': center,
            'good_matches': good_matches,
            'roi': roi
        })
    return results, image


def save_unsure_crop(image, roi, output_path):
    """
    Save the cropped ROI as a PNG image for manual inspection.
    """
    x, y, w, h = roi
    crop = image[y:y + h, x:x + w]
    cv2.imwrite(output_path, crop)


def main():
    # Define paths.
    template_path = 'template.png'
    images_folder = 'images'
    output_csv = 'fiducial_marks.csv'
    unsure_folder = 'unsure_marks'
    os.makedirs(unsure_folder, exist_ok=True)

    # Load the fiducial mark template.
    template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
    if template is None:
        print("Template image not found.")
        return

    csv_rows = []
    for filename in os.listdir(images_folder):
        if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff')):
            continue
        image_path = os.path.join(images_folder, filename)
        detections, image = process_image(image_path, template, ratio_thresh=0.75, min_matches=10)
        if image is None:
            continue
        for detection in detections:
            roi_idx = detection['roi_index']
            center = detection['center']
            good_matches = detection['good_matches']
            # If detection is not reliable (i.e. insufficient matches), save the ROI crop.
            if center is None:
                unsure_filename = f"{os.path.splitext(filename)[0]}_roi{roi_idx}.png"
                unsure_path = os.path.join(unsure_folder, unsure_filename)
                save_unsure_crop(image, detection['roi'], unsure_path)
            else:
                csv_rows.append([filename, roi_idx, center[0], center[1], good_matches])

    # Write the results to a CSV file.
    with open(output_csv, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Image', 'ROI_Index', 'Center_X', 'Center_Y', 'Good_Matches'])
        writer.writerows(csv_rows)


if __name__ == "__main__":
    main()
