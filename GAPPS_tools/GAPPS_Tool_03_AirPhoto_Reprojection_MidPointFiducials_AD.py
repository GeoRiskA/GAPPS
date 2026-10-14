import os
import cv2
import numpy as np
import pandas as pd
from PIL import Image


def crop_and_resample_images(input_image_folder, output_image_folder, fiducialmarks_file, target_width, target_height,
                             target_dpi):
    """
    For each image in the input folder that has an entry in the CSV,
    use its fiducial coordinates (X1, Y1, ..., X4, Y4) to compute a perspective
    transform that crops/resamples the image to the target_width x target_height.
    The output image is then saved with the desired DPI.

    Parameters:
      input_image_folder: path to folder with input images.
      output_image_folder: path to folder where processed images will be saved.
      fiducialmarks_file: CSV file with columns: name, X1, Y1, X2, Y2, X3, Y3, X4, Y4.
      target_width: desired output width in pixels.
      target_height: desired output height in pixels.
      target_dpi: desired DPI (saved as metadata).
    """

    # Read the CSV containing fiducial coordinates
    FM = pd.read_csv(fiducialmarks_file)

    # Create output folder if it doesn't exist
    os.makedirs(output_image_folder, exist_ok=True)

    # List images (e.g., TIFF images)
    images_list = [f for f in os.listdir(input_image_folder) if f.lower().endswith(('.tif', '.tiff'))]

    for image_name in images_list:
        # base_name = os.path.splitext(image_name)[0]
        # Look up the row in CSV that corresponds to the image (assumes CSV column 'name' matches the file's base name)
        row = FM[FM['name'] == image_name]
        if row.empty:
            print(f"Image {image_name} not found in CSV, skipping.")
            continue
        row = row.iloc[0]

        # Get fiducial coordinates from the CSV
        pts1 = np.float32([
            [row['X1'], row['Y1']],
            [row['X2'], row['Y2']],
            [row['X3'], row['Y3']],
            [row['X4'], row['Y4']]
        ])

        # Define the destination points: corners of a rectangle with the target dimensions
        pts2 = np.float32([
            [0, 0],
            [target_width - 1, 0],
            [target_width - 1, target_height - 1],
            [0, target_height - 1]
        ])

        # Compute the perspective transformation matrix
        M = cv2.getPerspectiveTransform(pts1, pts2)

        # Read the image (keeping its original bit depth)
        image_path = os.path.join(input_image_folder, image_name)
        img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            print(f"Could not read image {image_name}, skipping.")
            continue

        # Apply the perspective warp (this both crops and resamples to the target size)
        warped = cv2.warpPerspective(img, M, (target_width, target_height))

        # Convert the image to a PIL image so we can set DPI metadata
        if len(warped.shape) == 2:
            # Grayscale image
            pil_img = Image.fromarray(warped)
        else:
            # Color image: convert from BGR (OpenCV default) to RGB
            pil_img = Image.fromarray(cv2.cvtColor(warped, cv2.COLOR_BGR2RGB))

        # Save the image with the desired DPI metadata
        out_path = os.path.join(output_image_folder, f"{image_name}_cropped.tif")
        pil_img.save(out_path, dpi=(target_dpi, target_dpi))
        print(f"Processed and saved: {out_path}")


# Example usage:
if __name__ == '__main__':
    input_image_folder = r'G:\PROCESSING\SCANS\Haute_Ruzizi_1955\_PROCESSING\A_CanvasSized_Cropped'
    output_image_folder = r'G:\PROCESSING\SCANS\Haute_Ruzizi_1955\_PROCESSING\B_Reprojected'
    fiducialmarks_file = f'{input_image_folder}/Out_fiducialmarks.csv'

    # For example, if you want an output size that corresponds to A4 at 300 DPI,
    # you might use around 2480 x 3508 pixels (you can adjust as needed).
    target_width = 10630
    target_height = 10630
    target_dpi = 900

    crop_and_resample_images(input_image_folder, output_image_folder, fiducialmarks_file, target_width, target_height,
                             target_dpi)
