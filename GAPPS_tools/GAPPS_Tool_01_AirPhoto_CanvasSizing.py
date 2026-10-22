"""
------------------------------------------------------------------------------
PYTHON SCRIPT FOR THE STANDARDIZING OF AERIAL PHOTO ARCHIVE CANVAS SIZE
------------------------------------------------------------------------------

Version: 2.2.0 (20/10/2026)
Authorz: Benoît SMETS
          (Royal Museum for Central Africa  /  Vrije Universiteit Brussel)
         Antoine DILLE
          (Royal Museum for Central Africa)

Notes:


    - Specific Python modules needed for this script:
        > Joblib
        > OpenCV
        > Pillow
        > scikit-image
        > matplotlib
        > numpy

    - To use this script in standalone, simply adapt the directory paths and
      required values in the setup section of the script.

Log:
        - v1.1. (AD)
                - changed the way the image files are selected for better
                  handling of different formats
                - check if output folder exists and create if needed
                - increased max image size handled in PIL to avoid warnings
        - v2.0 (AD) December 2021
                - adapted for GAPP (graphic interface)
        - v2.1 (BS) July 2024
                - Adapted to the new GAPPS interface
        - v2.2.1 (AD) October 2026
                - cropped images written to a temporary folder then moved (no empty
                  file left by an interrupted run); empty files are processed again
        - v2.2 (AD) October 2026
                - crop to frame: the canvas sizing is skipped (its output is
                  not used when the images are cropped to their frame)
                - crop to frame: the black frame is detected on a downsampled
                  copy of the image (much faster), images processed in parallel
                - fixed the detection of already processed images (.tiff) and
                  the scanning of the output folders as input folders

© Royal Museum for Central Africa / Vrije Universiteit Brussel, 2020-2026
"""

import os, time
from PIL import Image
Image.MAX_IMAGE_PIXELS = 30000000000
import numpy as np
import cv2
from joblib import Parallel, delayed
import multiprocessing
from time import sleep
from pathlib import Path

import matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.patches import Rectangle

from skimage import io
from skimage.measure import label, regionprops
from skimage.filters import threshold_otsu
################################    SETUP     ################################

##### DIRECTORY PATHS #####
#input_image_folder = r"D:\path\input"
#output_image_folder = r"D:\path\output"

#### PARALLEL PROCESSING #####
# (Choose the number of CPU cores you want to use)
# (minimum = 1; suggested value = (number of cores) - 1)
# (if you don't know how many cores you have, write: 'multiprocessing.cpu_count()')
# num_cores = multiprocessing.cpu_count() - 1
num_cores = 5

# Number of images cropped to frame in parallel. Each worker holds a full resolution
# image in memory (~0.5-1.5 GB for a 1600 dpi scan): reduce if the RAM is limited.
num_cores_crop = max(1, min(4, multiprocessing.cpu_count() - 1))

# Downsampling factor used to detect the black frame (detection on a 1/N copy of the
# image). The detected frame is enlarged by N pixels on each side to never cut the frame.
FRAME_DETECTION_FACTOR = 4

################################ END OF SETUP ################################

def detect_black_frame(image_path, clip_dir, save_fig=False):
    """Detect the black frame of an air photo scan and save the image cropped to it.

    The frame is detected on a downsampled copy of the image; the crop is done on the
    full resolution image.

    :return: (image_path, True) if the image was cropped, (image_path, False) otherwise
    """
    start_time = time.time()
    f = FRAME_DETECTION_FACTOR
    name = os.path.splitext(os.path.basename(image_path))[0]

    # Load image as grayscale
    image = io.imread(image_path, as_gray=True)
    H, W = image.shape[:2]

    # Downsampled copy for the frame detection
    small = cv2.resize(image, (max(1, W // f), max(1, H // f)), interpolation=cv2.INTER_AREA)
    fy, fx = H / small.shape[0], W / small.shape[1]  # exact scale factors

    # Binarize the image based on a threshold (Otsu's method)
    thresh = threshold_otsu(small)
    thresh0 = thresh

    # Find the largest square-like region that could be the black frame
    max_area = 0
    frame_bbox = None
    while frame_bbox is None and thresh > thresh0 * 0.1:
        thresh *= 0.9  # Decrease the threshold
        binary = small < thresh
        labeled_image = label(binary)
        for region in regionprops(labeled_image):
            minr, minc, maxr, maxc = region.bbox
            width, height = maxc - minc, maxr - minr
            if 0.9 < width / height < 1.1 and width * height > (2 / 3) * small.size:
                if region.area > max_area:
                    max_area = region.area
                    frame_bbox = (minr, minc, maxr, maxc)

    # save cropped image
    if frame_bbox:
        # Frame in full resolution coordinates, enlarged by f pixels (never cut the frame)
        minr, minc, maxr, maxc = frame_bbox
        minr = max(0, int(np.floor(minr * fy)) - f)
        minc = max(0, int(np.floor(minc * fx)) - f)
        maxr = min(H, int(np.ceil(maxr * fy)) + f)
        maxc = min(W, int(np.ceil(maxc * fx)) + f)

        cropped_image = image[minr:maxr, minc:maxc]
        # Add XX white pixel rows/columns on each side of the cropped image
        white_buffer = 40  # white pixel size buffer around detected frame
        cropped_image_with_border = cv2.copyMakeBorder(
            cropped_image, white_buffer, white_buffer, white_buffer, white_buffer, cv2.BORDER_CONSTANT,
            value=65535)  # 65535 = white for uint16
        # Written in a temporary folder, then moved: an interrupted run never leaves an empty or
        # truncated image that would look already processed
        tmp_dir = os.path.join(clip_dir, '_tmp')
        os.makedirs(tmp_dir, exist_ok=True)
        tmp_path = os.path.join(tmp_dir, f'{name}_Cropped.tif')
        io.imsave(tmp_path, cropped_image_with_border, check_contrast=False)
        os.replace(tmp_path, os.path.join(clip_dir, f'{name}_Cropped.tif'))
        print(f'   > clipped to {clip_dir}/{name}_Cropped.tif [in {time.time() - start_time:.2f} seconds]')

        # Plot the (downsampled) original image with the detected frame
        if save_fig:
            fig = Figure()
            FigureCanvasAgg(fig)
            ax = fig.add_subplot(1, 1, 1)
            ax.imshow(small, cmap='gray', extent=(0, W, H, 0))
            ax.add_patch(Rectangle((minc, minr), maxc - minc, maxr - minr,
                                   edgecolor='red', linewidth=2, fill=False))
            os.makedirs(f'{clip_dir}/frame_check', exist_ok=True)
            fig.savefig(f'{clip_dir}/frame_check/{name}_frame.png', dpi=150, bbox_inches='tight')
        return image_path, True
    else:
        print(' !! No black frame detected in image {}'.format(os.path.basename(image_path)))
        return image_path, False


def _safe_detect_black_frame(image_path, clip_dir, save_fig=True):
    """Wrapper for the parallel processing: an error on one image does not stop the others."""
    try:
        return detect_black_frame(image_path, clip_dir, save_fig=save_fig)
    except Exception as e:
        print(f'Error in image {os.path.basename(image_path)}: {e}')
        return image_path, False


def script_01_csize(input_image_folder, output_image_folder, subfolders=False, crop_to_frame = True):

    print(' ')
    print('=====================================================================')
    print('=           PYTHON SCRIPT FOR IMAGE CANVAS STANDARDIZING            =')
    print('=  Version 2.2.0 (October 2026)  |  B. Smets/A. Dille (RMCA/VUB)    =')
    print('=====================================================================')
    print(' ')

    print(f' Launch time: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f' Input image folder : {input_image_folder}')
    print(f' Output image folder : {output_image_folder}\n')
    print(f' Checking for subfolders : {subfolders}\n')
    print(f' Crop to frame : {crop_to_frame}\n')

    os.chdir(input_image_folder)



    ### Define the list of images and count the number of files to process ###
    # also look into sub directory
    allfiles = []
    error_images = []
    allfiles_path = []

    # Folders never scanned for input images: GAPPS outputs (e.g. output_results inside the
    # input folder, with A_CanvasSized, _FM_templates, ...) and folders starting with '_'
    excluded_folders = {os.path.normcase(os.path.abspath(f)) for f in
                        (output_image_folder, output_image_folder + '_Cropped', os.path.dirname(output_image_folder))}

    if subfolders:
        for root, dirs, files in os.walk(input_image_folder):
            dirs[:] = sorted(d for d in dirs if not d.startswith('_')
                             and os.path.normcase(os.path.abspath(os.path.join(root, d))) not in excluded_folders)
            for file in sorted(files):
                if (file.lower().endswith((".tif", ".tiff")) and not file.startswith('preview')
                        and not 'Canvas' in file and not 'Cropped' in file and not 'fidu' in file):
                    allfiles.append(file)
                    allfiles_path.append(os.path.join(root, file))
    else:
        allfiles = [file for file in os.listdir(input_image_folder) if file.lower().endswith((".tif", ".tiff"))
                    and not file.startswith('preview') and not 'Canvas' in file and not 'Cropped' in file]
        allfiles_path = [os.path.join(input_image_folder, file) for file in allfiles]

    images_list = allfiles
    images_list_path = allfiles_path

    print('Number of images to process: ' + str(len(images_list)))
    print(images_list)
    print(' ')

    # When cropping to the frame, the original images are cropped directly: the canvas sizing
    # output is not used, so this (long) step is skipped.
    SKIP_CANVAS_SIZED = crop_to_frame
    if SKIP_CANVAS_SIZED:
        print(' > Crop to frame selected: canvas sizing skipped (the original images are cropped directly)\n')

    if SKIP_CANVAS_SIZED == False:
        Path(output_image_folder).mkdir(parents=True, exist_ok=True)
        # add a check if the image where not already processed
        canvas_sized_images_list = [image for image in os.listdir(output_image_folder) if image.endswith( '_CanvasSized.tif')]
        if len(canvas_sized_images_list) > 0:
            print('\033[92mSome images were already processed, they will be skipped...\033[0m\n')
            images_list_path = [image_path for image_path in images_list_path
                                if Path(image_path).stem + '_CanvasSized.tif' not in canvas_sized_images_list]
            if len(images_list_path) == 0:
                print('All images were already processed to canvas size\n')

    if SKIP_CANVAS_SIZED == False and len(images_list_path) > 0:
        print(f'\033[93mNumber of images left to process: {str(len(images_list_path))}\033[0m')
        print('\n')
        ### Detect the max width and height in the dataset ###
        # (computed on all images, so that resumed runs produce the same canvas size)
        sizes = [Image.open(f, 'r').size for f in allfiles_path]
        sizes_array = np.asarray(sizes)
        widths = sizes_array[:, 0]
        heights = sizes_array[:, 1]
        width_max = max(widths)
        height_max = max(heights)

        print('maximum width found = ' + str(width_max) + ' pixels')
        print('maximum height found = ' + str(height_max) + ' pixels')
        print(' ')

        ### Standardize the the canvas size of each image ###
        def standardize_canvas(image_path):
            # Read the images, keep the original pixel depth (-1) and read its dimensions
            img = cv2.imread(image_path, -1)

            rows, cols = img.shape[:2]
            # Add columns and rows to change the canvas size to maximum width and height
            rows_added = height_max - rows
            cols_added = width_max - cols
            imready = cv2.copyMakeBorder(img, top=0, bottom=rows_added, left=0, right=cols_added,
                                         borderType=cv2.BORDER_CONSTANT, value=0)
            # Save the new image with the standardized size of canvas
            img_name = os.path.splitext(os.path.basename(image_path))[
                0]  # Find the name of the input image, without its file extension, in order to use it into the output image name
            Path(output_image_folder).mkdir(parents=True, exist_ok=True)  # create folder if does no exist
            cv2.imwrite(os.path.join(output_image_folder, img_name + '_CanvasSized.tif'), imready)

        total_start_time = time.time()

        # Use parallel processing
        Parallel(n_jobs=num_cores, verbose=30)(delayed(standardize_canvas)(image_path) for image_path in images_list_path)

        print(f'Total time taken: {time.time() - total_start_time:.2f} seconds')

    if crop_to_frame:

        print(' ')
        print('Clipping to frame...')

        clip_dir = output_image_folder + '_Cropped'
        os.makedirs(clip_dir, exist_ok=True)

        # (empty files, left by an interrupted run of a former version, are processed again)
        cropped_images_list = [image for image in os.listdir(clip_dir) if image.endswith('_Cropped.tif')
                               and os.path.getsize(os.path.join(clip_dir, image)) > 0]

        images_to_crop = [
                image_path for image_path in allfiles_path
                if Path(image_path).stem + '_CanvasSized_Cropped.tif' not in cropped_images_list
                   and Path(image_path).stem + '_Cropped.tif' not in cropped_images_list]

        if len(images_to_crop) == 0:
            print('All images were already clipped to frame\n')
        else:
            if len(cropped_images_list) > 0:
                print(f'\033[92m{len(allfiles_path) - len(images_to_crop)} images were already clipped to frame, '
                      f'they will be skipped...\033[0m')
            print(f'Number of images left to process: {str(len(images_to_crop))} '
                  f'(in parallel on {num_cores_crop} cores)\n')

            total_start_time = time.time()
            results = Parallel(n_jobs=num_cores_crop, verbose=30)(
                delayed(_safe_detect_black_frame)(image_path, clip_dir, True) for image_path in images_to_crop)

            error_images = [image_path for image_path, ok in results if not ok]
            if len(error_images) > 0:
                os.makedirs(clip_dir, exist_ok=True)
                with open(os.path.join(clip_dir, '__error_images.txt'), 'a') as f:
                    for item in error_images:
                        f.write("%s\n" % item)

            total_end_time = time.time()
            print(f'Total time taken: {total_end_time - total_start_time:.2f} seconds')

            if len(error_images) > 0:
                print(f'\n {len(error_images)} error images found (no black frame detected or reading error)')
                for item in error_images:
                    print(f'Error  image {os.path.basename(item)}')
                print(f'  > error image paths can be found in {clip_dir}/__error_images.txt\n ')

        sleep(3)


    print(' ')
    print('======================')
    print(' PROCESSING COMPLETED ')
    print('======================')

    ##### END PROCESSING #####

if __name__ == "__main__":
    script_01_csize(input_image_folder, output_image_folder, subfolders, crop_to_frame)


