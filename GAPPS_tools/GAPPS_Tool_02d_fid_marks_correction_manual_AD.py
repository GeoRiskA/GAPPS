
############################################################
import os
import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import csv
import re

#############################################
# OPTIONS
#############################################
# Set FIDUCIAL_MODE to either "CORNERS" or "MIDPOINTS"
FIDUCIAL_MODE = "CORNERS"  # "CORNERS" or "MIDPOINTS"

# Set to True to process all images in the original folder
# and process the chosen fiducial mode for each image via the interactive interface.
PROCESS_ALL_IMAGES = True

# Paths to images
original_images_folder = r"G:\PROCESSING\SCANS\Haute_Ruzizi_1955\_PROCESSING\A_CanvasSized_Cropped/extra"
original_images_folder = r'G:\PROCESSING\SCANS\Bukavu-Bloc_1960\X0012B01\PROCESSING\A_CanvasSized_Cropped'
original_images_folder = r'D:\PROCESSING\SCANS\Manono_1952\PROCESSING\A_CanvasSized_Cropped\corners\_To_Be_Checked'

# Used only when PROCESS_ALL_IMAGES is False:
corners_folder = r"D:\PROCESSING\SCANS\Manono_1952\PROCESSING\A_CanvasSized_Cropped\corners\_To_Be_Checked"

scale_factor = 0.3  # [0.1 - 0.3] Adjusted scale factor to balance visibility and performance

############################################################
# Check outliers
OUTLIER_CHECK = False
if OUTLIER_CHECK:
    import shutil
    os.makedirs(f'{corners_folder}/good/', exist_ok=True)
    outlier_folder = f'{original_images_folder}/corners/_outliers'

    outliers = [i for i in os.listdir(outlier_folder) if i.endswith('.png')]
    outliers_image_names = ['_'.join(i.split('_')[2:])[:-4] for i in outliers]
    corners_to_check = [i for i in os.listdir(corners_folder) if i.endswith('.png')]
    corners_to_keep = []
    corners_image = []
    for i in outliers_image_names:
        for f in corners_to_check:
            if i in f:
                corners_to_keep.append(f)
                corners_image.append(i)
    corners_image = list(set(corners_image))
    if len(corners_image) == len(outliers_image_names):
        print('seems good, at least one corner per outlier image')
        # moving non necessary corners
        for c in corners_to_check:
            if c not in corners_to_keep:
                shutil.move(f'{corners_folder}/{c}',f'{corners_folder}/good/{c}' )

#############################################
# Global variables
#############################################

# Define fiducials based on selected mode
if FIDUCIAL_MODE == "CORNERS":
    fiducials = ["top_left", "top_right", "bot_left", "bot_right"]
    mapping = {"top_left": 0, "top_right": 2, "bot_right": 4, "bot_left": 6}
    fiducials_coo = {"top_left": 0, "top_right": 1, "bot_right": 3, "bot_left": 2}

elif FIDUCIAL_MODE == "MIDPOINTS":
    fiducials = ["top_center", "right_center", "bot_center", "left_center"]
    mapping = {"top_center": 0, "right_center": 2, "bot_center": 4, "left_center": 6}
current_fiducial_index = 0

if PROCESS_ALL_IMAGES:
    # List of original images (e.g., TIFF files)
    image_list = sorted([f for f in os.listdir(original_images_folder) if f.lower().endswith(".tif") or f.lower().endswith(".png") ])
    im_extension = [f for f in os.listdir(original_images_folder)][0][-3:]  # Get the first image to determine dimensions from the extension
    if im_extension.lower() == 'png':
        print('Probably using some _FiducialDetection_ images, will find their tif counterpart')
        base_path = original_images_folder
        while os.path.basename(base_path) != "A_CanvasSized_Cropped" and os.path.dirname(base_path) != base_path:
            base_path = os.path.dirname(base_path)
        CanvasSized_Cropped_folder = base_path
        image_list_tif = [ f.replace('.png','')
                      .replace('_FiducialsDetection_','')  for f in image_list]
        original_images_folder = CanvasSized_Cropped_folder
        image_list = image_list_tif
    current_image_index = 0

    # CSV file will always have 1 + 8 columns: name, then X and Y for each fiducial
    csv_file = os.path.join(original_images_folder, "fiducial_centers_corrected.csv")
else:
    # When processing specific fiducial images.
    corner_images = [f for f in os.listdir(corners_folder) if f.endswith(".png")]
    current_index = 0
    csv_file = os.path.join(corners_folder, "fiducial_centers_corrected.csv")

# Load existing CSV or create a new one
if os.path.exists(csv_file):
    with open(csv_file, newline='') as f:
        reader = csv.reader(f)
        existing_data = {row[0]: row[1:] for row in reader}
else:
    existing_data = {}

#############################################
# Functions
#############################################
# Only used in the corners_folder mode:
def parse_filename(filename):
    # This regex now includes both corners and midpoints.
    match = re.match(r'_ToCheck_(.*?)_(top_left|top_right|bot_left|bot_right|top_center|right_center|bot_center|left_center)\.png', filename)
    return match.groups() if match else (None, None)

def get_crop_region_corner(image, current_fiducial_index):
    """Return crop region for a corner fiducial."""
    h, w = image.shape[:2]
    crop_w, crop_h = w // 3, h // 3
    fid = fiducials[current_fiducial_index]  # Should be one of the corners
    if fid == "top_left":
        return (0, crop_w, 0, crop_h)
    elif fid == "top_right":
        return (w - crop_w, w, 0, crop_h)
    elif fid == "bot_left":
        return (0, crop_w, h - crop_h, h)
    elif fid == "bot_right":
        return (w - crop_w, w, h - crop_h, h)
    else:
        return (0, w, 0, h)

def get_crop_region_midpoint(image, current_fiducial_index):
    """Return crop region for a midpoint fiducial."""
    h, w = image.shape[:2]
    crop_w, crop_h = w // 3, h // 3
    fid = fiducials[current_fiducial_index]  # Should be one of the midpoints
    if fid == "top_center":
        return (w//2 - crop_w//2, w//2 + crop_w//2, 0, crop_h)
    elif fid == "right_center":
        return (w - crop_w, w, h//2 - crop_h//2, h//2 + crop_h//2)
    elif fid == "bot_center":
        return (w//2 - crop_w//2, w//2 + crop_w//2, h - crop_h, h)
    elif fid == "left_center":
        return (0, crop_w, h//2 - crop_h//2, h//2 + crop_h//2)
    else:
        return (0, w, 0, h)

def get_original_coordinates(filename, fiducial_name):
    """
    Get original coordinates for the specified fiducial from Out_fiducialmarks.csv
    Returns (x, y) if found, or (None, None) if not found
    """
    try:
        # Get the base path by going up to A_CanvasSized_Cropped
        base_path = original_images_folder
        while os.path.basename(base_path) != "A_CanvasSized_Cropped" and os.path.dirname(base_path) != base_path:
            base_path = os.path.dirname(base_path)

        original_csv = os.path.join(base_path, "Out_fiducialmarks.csv")

        if os.path.exists(original_csv):
            with open(original_csv, 'r') as f:
                reader = csv.reader(f)
                header = next(reader)
                original_coords = {}
                for row in reader:
                    if len(row[0]) < 4:  # If there's an extra column (likely an index column)
                        img_name = row[1]
                        original_coords[img_name] = row[2:]  # X1, Y1, X2, Y2, X3, Y3, X4, Y4
                    else:
                        img_name = row[0]
                        original_coords[img_name] = row[1:]  # X1, Y1, X2, Y2, X3, Y3, X4, Y4

                # Get base name without extension
                base_name = os.path.splitext(filename)[0].replace('.tif', '').replace('.png', '').replace('_FiducialsDetection_', '')

                if base_name in original_coords:
                    ci = mapping[fiducial_name]
                    x_original = float(original_coords[base_name][ci])
                    y_original = float(original_coords[base_name][ci + 1])
                    return x_original, y_original

        return None, None  # Not found
    except Exception as e:
        print(f"Error reading original coordinates: {e}")
        return None, None  # Error occurred

def load_next_image():
    global current_image_index, current_fiducial_index, current_index
    global original_image, displayed_image, original_filename, fiducial_name

    if PROCESS_ALL_IMAGES:
        if current_image_index >= len(image_list):
            print("All images processed.")
            root.quit()
            return

        original_filename = image_list[current_image_index]
        fiducial_name = fiducials[current_fiducial_index]

        # Calculate progress information
        total_images = len(image_list)
        total_fiducials = len(fiducials)
        total_tasks = total_images * total_fiducials
        current_task = (current_image_index * total_fiducials) + current_fiducial_index + 1
        progress_text = f"Progress: {current_task}/{total_tasks} (Image {current_image_index+1}/{total_images}, Fiducial {current_fiducial_index+1}/{total_fiducials})"

        # Check if coordinates for this image and fiducial are already saved.
        if original_filename in existing_data:
            ci = mapping[fiducial_name]
            if existing_data[original_filename][ci] != "" and existing_data[original_filename][ci+1] != "":
                print(f"Coordinates for {original_filename} at {fiducial_name} already saved. Skipping fiducial.")
                current_fiducial_index += 1
                if current_fiducial_index >= len(fiducials):
                    current_fiducial_index = 0
                    current_image_index += 1
                load_next_image()
                return

        print(f'> Processing: {original_filename} - {fiducial_name}')
        original_path = os.path.join(original_images_folder, original_filename)
        if not os.path.exists(original_path):
            print(f"Original image not found: {original_path}")
            current_fiducial_index += 1
            if current_fiducial_index >= len(fiducials):
                current_fiducial_index = 0
                current_image_index += 1
            load_next_image()
            return

        # Check file extension
        is_tiff = original_path.lower().endswith('.tif') or original_path.lower().endswith('.tiff')

        # Load image with appropriate flags
        if is_tiff:
            original_image = cv2.imread(original_path, cv2.IMREAD_UNCHANGED)
        else:
            original_image = cv2.imread(original_path, cv2.IMREAD_UNCHANGED)

        if original_image is None:
            print(f"Error loading image: {original_path}")
            current_fiducial_index += 1
            if current_fiducial_index >= len(fiducials):
                current_fiducial_index = 0
                current_image_index += 1
            load_next_image()
            return

        # Normalize based on image type
        if len(original_image.shape) == 2 or original_image.shape[2] == 1:  # Grayscale
            original_image = cv2.normalize(original_image, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
        else:  # Color
            original_image = cv2.normalize(original_image, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
            if original_image.shape[2] > 3:  # If more than 3 channels, take only RGB
                original_image = original_image[:, :, :3]

        # Choose cropping function based on mode.
        if FIDUCIAL_MODE == "CORNERS":
            x1, x2, y1, y2 = get_crop_region_corner(original_image, current_fiducial_index)
        else:
            x1, x2, y1, y2 = get_crop_region_midpoint(original_image, current_fiducial_index)
        cropped_image = original_image[y1:y2, x1:x2]

        # Ensure image is in correct format for PIL
        if len(cropped_image.shape) == 2:  # If grayscale, convert to RGB
            cropped_image = cv2.cvtColor(cropped_image, cv2.COLOR_GRAY2RGB)

        # Get original coordinates for the current fiducial from Out_fiducialmarks.csv
        original_x, original_y = get_original_coordinates(original_filename, fiducial_name)

        # Draw a red cross at the original fiducial position if coordinates were found
        if original_x is not None and original_y is not None:
            # Convert to crop coordinates
            cross_x = original_x - x1
            cross_y = original_y - y1

            # Draw red cross in the cropped image (if the point is within the crop)
            if 0 <= cross_x < (x2-x1) and 0 <= cross_y < (y2-y1):
                cross_size = 100
                cv2.line(cropped_image,
                        (int(cross_x - cross_size), int(cross_y)),
                        (int(cross_x + cross_size), int(cross_y)),
                        (0, 0, 255), 8)
                cv2.line(cropped_image,
                        (int(cross_x), int(cross_y - cross_size)),
                        (int(cross_x), int(cross_y + cross_size)),
                        (0, 0, 255), 8)
        else:
            print(f"No original coordinates found for {original_filename} - {fiducial_name}. Using center of fiducial region.")
        resized_image = cv2.resize(cropped_image, (0, 0), fx=scale_factor, fy=scale_factor)
        pil_image = Image.fromarray(resized_image)
        displayed_image = ImageTk.PhotoImage(pil_image)

        canvas.delete("all")
        canvas.create_image(0, 0, anchor=tk.NW, image=displayed_image)

        # Add all text information with consistent colors and positioning
        canvas_width = pil_image.width
        text_x = canvas_width // 2  # Center text horizontally

        canvas.create_text(text_x, 10, text=f"{original_filename} - {fiducial_name}",
                         font=("Arial", 12), fill="black")
        canvas.create_text(text_x, 30, text=progress_text,
                         font=("Arial", 10), fill="blue")
        canvas.create_text(text_x, 50, text="Click to save coordinates | Press Enter to use original coordinates",
                         font=("Arial", 10), fill="red")

    else:
        # Processing in corners_folder mode - similar changes
        if current_index >= len(corner_images):
            print("All images processed.")
            root.quit()
            return

        # Calculate progress information for corners mode
        total_corners = len(corner_images)
        progress_text = f"Progress: {current_index+1}/{total_corners}"

        filename = corner_images[current_index]
        original_filename, fiducial_name = parse_filename(filename)
        current_fiducial_index = fiducials_coo[fiducial_name]
        if not original_filename:
            print(f"Skipping invalid filename: {filename}")
            current_index += 1
            load_next_image()
            return

        if original_filename in existing_data:
            ci = mapping[fiducial_name]
            if existing_data[original_filename][ci] != "" and existing_data[original_filename][ci+1] != "":
                print(f"Coordinates for {original_filename} at {fiducial_name} already saved. Skipping image.")
                current_index += 1
                load_next_image()
                return

        print(f'> image : {filename}')
        original_path = os.path.join(original_images_folder, original_filename)
        if not os.path.exists(original_path):
            print(f"Original image not found: {original_path}")
            current_index += 1
            load_next_image()
            return

        # Check file extension
        is_tiff = original_path.lower().endswith('.tif') or original_path.lower().endswith('.tiff')

        # Load image with appropriate flags
        if is_tiff:
            original_image = cv2.imread(original_path, cv2.IMREAD_UNCHANGED)
        else:
            original_image = cv2.imread(original_path, cv2.IMREAD_UNCHANGED)

        if original_image is None:
            print(f"Error loading image: {original_path}")
            current_index += 1
            load_next_image()
            return

        # Normalize based on image type
        if len(original_image.shape) == 2 or original_image.shape[2] == 1:  # Grayscale
            original_image = cv2.normalize(original_image, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
        else:  # Color
            original_image = cv2.normalize(original_image, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
            if original_image.shape[2] > 3:  # If more than 3 channels, take only RGB
                original_image = original_image[:, :, :3]

        if FIDUCIAL_MODE == "CORNERS":
            x1, x2, y1, y2 = get_crop_region_corner(original_image,current_fiducial_index)
        else:
            x1, x2, y1, y2 = get_crop_region_midpoint(original_image,current_fiducial_index)

        cropped_image = original_image[y1:y2, x1:x2]

        # Ensure image is in correct format for PIL
        if len(cropped_image.shape) == 2:  # If grayscale, convert to RGB
            cropped_image = cv2.cvtColor(cropped_image, cv2.COLOR_GRAY2RGB)


        resized_image = cv2.resize(cropped_image, (0, 0), fx=scale_factor, fy=scale_factor)
        pil_image = Image.fromarray(resized_image)
        displayed_image = ImageTk.PhotoImage(pil_image)

        canvas.delete("all")
        canvas.create_image(0, 0, anchor=tk.NW, image=displayed_image)

        # Get original coordinates for the current fiducial from Out_fiducialmarks.csv
        original_x, original_y = get_original_coordinates(os.path.basename(original_filename), fiducial_name)

        # Draw a red cross at the original fiducial position if coordinates were found
        if original_x is not None and original_y is not None:
            # Convert to crop coordinates
            cross_x = original_x - x1
            cross_y = original_y - y1

            # Convert to canvas coordinates (applying scale factor)
            canvas_x = cross_x * scale_factor
            canvas_y = cross_y * scale_factor

            # Check if point is within the visible area
            if 0 <= canvas_x < pil_image.width and 0 <= canvas_y < pil_image.height:
                cross_size = 15  # Size in canvas coordinates
                canvas.create_line(
                    canvas_x - cross_size, canvas_y,
                    canvas_x + cross_size, canvas_y,
                    fill="red", width=3
                )
                canvas.create_line(
                    canvas_x, canvas_y - cross_size,
                    canvas_x, canvas_y + cross_size,
                    fill="red", width=3
                )
                print(f"Drew cross at canvas coordinates ({canvas_x}, {canvas_y})")
            else:
                print(f"Original point is outside visible area: ({canvas_x}, {canvas_y})")

        else:
            print(
                f"No original coordinates found for {original_filename} - {fiducial_name}. Using center of fiducial region.")

        # Add all text information with consistent colors and positioning
        canvas_width = pil_image.width
        text_x = canvas_width // 2  # Center text horizontally

        canvas.create_text(text_x, 10, text=f"{original_filename} - {fiducial_name}",
                         font=("Arial", 12), fill="black")
        canvas.create_text(text_x, 30, text=progress_text,
                         font=("Arial", 10), fill="blue")
        canvas.create_text(text_x, 50, text="Click to save coordinates | Press Enter to use original coordinates",
                         font=("Arial", 10), fill="red")

        current_index += 1

def save_original_coordinates(event):
    global current_image_index, current_fiducial_index, current_index

    # Find the original coordinates from Out_fiducialmarks.csv
    try:
        # Get the base path by going up to A_CanvasSized_Cropped
        base_path = original_images_folder
        while os.path.basename(base_path) != "A_CanvasSized_Cropped" and os.path.dirname(base_path) != base_path:
            base_path = os.path.dirname(base_path)

        original_csv = os.path.join(base_path, "Out_fiducialmarks.csv")

        if os.path.exists(original_csv):
            with (open(original_csv, 'r') as f):
                reader = csv.reader(f)
                header = next(reader)
                original_coords = {}
                for row in reader:
                    if len(row) > 0:
                        img_name = row[0]
                        original_coords[img_name] = row[1:9]  # X1, Y1, X2, Y2, X3, Y3, X4, Y4

                # Get base name without extension
                base_name = os.path.splitext(original_filename)[0].replace('.tif', ''
                                                                           ).replace('.png', '').replace('_FiducialsDetection_', '')

                if base_name in original_coords:
                    ci = mapping[fiducial_name]
                    x_original = original_coords[base_name][ci]
                    y_original = original_coords[base_name][ci + 1]

                    print(f'   > Using original coordinates from Out_fiducialmarks.csv: ({x_original}, {y_original})')

                    if original_filename not in existing_data:
                        existing_data[original_filename] = [""] * 8

                    existing_data[original_filename][ci] = x_original
                    existing_data[original_filename][ci + 1] = y_original
                else:
                    # Fall back to center of fiducial region if not found in the CSV
                    if FIDUCIAL_MODE == "CORNERS":
                        x1, x2, y1, y2 = get_crop_region_corner(original_image, current_fiducial_index)
                    else:
                        x1, x2, y1, y2 = get_crop_region_midpoint(original_image, current_fiducial_index)

                    x_original = x1 + (x2 - x1) / 2
                    y_original = y1 + (y2 - y1) / 2

                    print(f'   > Image not found in Out_fiducialmarks.csv. Using fiducial center: ({x_original}, {y_original})')

                    if original_filename not in existing_data:
                        existing_data[original_filename] = [""] * 8

                    ci = mapping[fiducial_name]  # Define ci here to ensure it's always available
                    existing_data[original_filename][ci] = str(x_original)
                    existing_data[original_filename][ci + 1] = str(y_original)
        else:
            # Fall back to center if CSV not found
            if FIDUCIAL_MODE == "CORNERS":
                x1, x2, y1, y2 = get_crop_region_corner(original_image, current_fiducial_index)
            else:
                x1, x2, y1, y2 = get_crop_region_midpoint(original_image, current_fiducial_index)

            x_original = x1 + (x2 - x1) / 2
            y_original = y1 + (y2 - y1) / 2

            print(f'   > Out_fiducialmarks.csv not found. Using fiducial center: ({x_original}, {y_original})')

            if original_filename not in existing_data:
                existing_data[original_filename] = [""] * 8

            ci = mapping[fiducial_name]
            existing_data[original_filename][ci] = str(x_original)
            existing_data[original_filename][ci + 1] = str(y_original)

    except Exception as e:
        # If any error occurs, fall back to using center of fiducial region
        print(f"Error reading original coordinates: {e}")
        if FIDUCIAL_MODE == "CORNERS":
            x1, x2, y1, y2 = get_crop_region_corner(original_image, current_fiducial_index)
        else:
            x1, x2, y1, y2 = get_crop_region_midpoint(original_image, current_fiducial_index)

        x_original = x1 + (x2 - x1) / 2
        y_original = y1 + (y2 - y1) / 2

        print(f'   > Using fiducial center as fallback: ({x_original}, {y_original})')

        if original_filename not in existing_data:
            existing_data[original_filename] = [""] * 8

        ci = mapping[fiducial_name]
        existing_data[original_filename][ci] = str(x_original)
        existing_data[original_filename][ci + 1] = str(y_original)

    # Save to CSV file
    with open(csv_file, "w", newline='') as f:
        writer = csv.writer(f)
        # Write header for 4 fiducials (8 coordinates)
        header = ["name", "X1", "Y1", "X2", "Y2", "X3", "Y3", "X4", "Y4"]
        writer.writerow(header)
        for name, coords in existing_data.items():
            writer.writerow([name] + coords)

    # Move to next fiducial or image
    if PROCESS_ALL_IMAGES:
        current_fiducial_index += 1
        if current_fiducial_index >= len(fiducials):
            current_fiducial_index = 0
            current_image_index += 1
    else:
        # Original mode simply moves to next image
        pass

    load_next_image()

def save_coordinates(event):
    global current_image_index, current_fiducial_index, current_index
    x, y = event.x, event.y
    # Retrieve crop region based on current mode.
    if FIDUCIAL_MODE == "CORNERS":
        x1, x2, y1, y2 = get_crop_region_corner(original_image , current_fiducial_index)
    else:
        x1, x2, y1, y2 = get_crop_region_midpoint(original_image, current_fiducial_index)
    x_original = (x / scale_factor) + x1
    y_original = (y / scale_factor) + y1

    print(f'   > Clicked: ({x}, {y}) mapped to ({x_original}, {y_original}) on full image')

    if original_filename not in existing_data:
        # Initialize 8 empty slots for 4 fiducials.
        existing_data[original_filename] = [""] * 8
    ci = mapping[fiducial_name]
    existing_data[original_filename][ci] = str(x_original)
    existing_data[original_filename][ci + 1] = str(y_original)

    with open(csv_file, "w", newline='') as f:
        writer = csv.writer(f)
        # Write header for 4 fiducials (8 coordinates)
        header = ["name", "X1", "Y1", "X2", "Y2", "X3", "Y3", "X4", "Y4"]
        writer.writerow(header)
        for name, coords in existing_data.items():
            writer.writerow([name] + coords)

    if PROCESS_ALL_IMAGES:
        current_fiducial_index += 1
        if current_fiducial_index >= len(fiducials):
            current_fiducial_index = 0
            current_image_index += 1
    else:
        # Original mode simply moves to next image.
        pass

    load_next_image()

#############################################
# Tkinter setup
#############################################
root = tk.Tk()
root.title("Fiducial Marker Picker")
canvas = tk.Canvas(root, width=800, height=800)
canvas.pack()
canvas.bind("<Button-1>", save_coordinates)
# Add binding for Enter key
root.bind("<Return>", save_original_coordinates)

# Start processing
load_next_image()
root.mainloop()



#############################################
MERGE_fidu_files_csv = False
if MERGE_fidu_files_csv:
    # merge with Out_fiducialmarks.csv
    import pandas as pd
    import shutil
    # File paths (adjust if necessary)
    if not PROCESS_ALL_IMAGES:
        fiducials_corrected_file = f"{corners_folder}/fiducial_centers_corrected.csv"
    else:
        fiducials_corrected_file = f"{original_images_folder}/fiducial_centers_corrected.csv"
    # Find the original coordinates from Out_fiducialmarks.csv
    # fiducials_main = f"{original_images_folder}/Out_fiducialmarks.csv"
    base_path = original_images_folder
    while os.path.basename(base_path) != "A_CanvasSized_Cropped" and os.path.dirname(base_path) != base_path:
        base_path = os.path.dirname(base_path)
    fiducials_main = os.path.join(base_path, "Out_fiducialmarks.csv")

    # create a copy of original file
    shutil.copy(fiducials_main, fiducials_main[:-4] + '_original.csv')


    # Read both CSV files into dataframes.
    # Assume the CSV files have columns: name, X1, Y1, X2, Y2, X3, Y3, X4, Y4
    df_fid = pd.read_csv(fiducials_corrected_file)
    df_out = pd.read_csv(fiducials_main)

    # Optional: Replace "nan" strings and actual NaN values with empty strings in both dataframes.
    df_fid.fillna("", inplace=True)
    df_out.fillna("", inplace=True)
    # round the coordinates to 2 decimal places
    df_fid[["X1", "Y1", "X2", "Y2", "X3", "Y3", "X4", "Y4"]] = df_fid[["X1", "Y1", "X2", "Y2", "X3", "Y3", "X4", "Y4"]].round(1)

    # Strip any leading or trailing spaces in column names
    try:
        df_fid.index = [name.replace('.tif', '').replace('.png', '').replace('_FiducialsDetection_', '') for name in
                        df_fid.index]
    except:
        df_fid['name'] = [name.replace('.tif', '').replace('.png', '').replace('_FiducialsDetection_', '') for name in
                        df_fid['name']]
    df_fid.columns = df_fid.columns.str.strip()
    df_out.columns = df_out.columns.str.strip()
    # if FIDUCIAL_MODE == 'CORNERS':
    #     df_fid[["X3", "X4"]] = df_fid[["X4", "X3"]].values
    #     df_fid[["X3", "X4"]] = df_fid[["X3", "X4"]].values

    # If the fiducial file doesn't have a "name" column, assume its index holds filenames.
    # For example, if the index is "5943_065_CanvasSized.tif", then remove the extension.
    if "name" not in df_fid.columns:
        df_fid.index = [name.split('.')[0] for name in df_fid.index]
    else:
        # Otherwise, set the index using the "name" column after stripping the extension.
        df_fid.set_index("name", inplace=True)
        df_fid.index = [name.split('.')[0] for name in df_fid.index]

    # Ensure df_out uses "name" as its index.
    if "name" in df_out.columns:
        df_out.set_index("name", inplace=True)
        df_out.index = [name.split('.')[0] for name in df_out.index]


    modifications = 0
    new_lines = 0
    # Loop over each image in the fiducial data.
    for image in df_fid.index:
        if image not in df_out.index:
            # Get the row from df_fid
            row_to_add = df_fid.loc[image].copy()
            row_to_add['top_left_accuracy'] = 0.9
            row_to_add['top_right_accuracy'] = 0.9
            row_to_add['bot_right_accuracy'] = 0.9
            row_to_add['bot_left_accuracy'] = 0.9

            # Ensure there's a 'name' entry; if not, add it.
            if "name" not in row_to_add.index:
                row_to_add["name"] = image

            # Add the row into df_out
            df_out.loc[image] = row_to_add
            modifications += 1
            new_lines += 1

        else:
            # If image exists, update each coordinate if the fiducial file has a non-empty value
            for col in ["X1", "Y1", "X2", "Y2", "X3", "Y3", "X4", "Y4"]:
                fid_val = df_fid.loc[image, col]
                out_val = df_out.loc[image, col]
                if str(fid_val).strip() != "" and str(fid_val) != str(out_val):
                    df_out.loc[image, col] = fid_val
                    modifications += 1

    print(f' >> {str((modifications))} modifications applied, {str(new_lines)} new images added')

    # Ensure columns are in the right order and there are no duplicate columns
     # Reset the index to turn "name" back into a column.
    df_out = df_out.sort_index()
    df_out = df_out.reset_index()
    df_out.rename(columns={'index': 'name'}, inplace=True)
    if 'name' in df_out.index:
        df_out = df_out.drop('name')
    # Write the merged dataframe to the output CSV.
    df_out.to_csv(fiducials_main, index=False)
    print(f"Merging complete. Total modifications: {modifications}")
