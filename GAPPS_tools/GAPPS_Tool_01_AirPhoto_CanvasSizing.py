"""
------------------------------------------------------------------------------
PYTHON SCRIPT FOR THE STANDARDIZING OF AERIAL PHOTO ARCHIVE CANVAS SIZE
------------------------------------------------------------------------------

Version: 2.1.0 (19/07/2024)
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

© Royal Museum for Central Africa / Vrije Universiteit Brussel, 2020-2024
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

import matplotlib.pyplot as plt
import matplotlib

matplotlib.use('Qt5Agg')

from skimage import io, color
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

################################ END OF SETUP ################################

def detect_black_frame(image_path, clip_dir,error_images, save_fig=False):
    start_time = time.time()

    # Load image as grayscale
    image = io.imread(image_path, as_gray=True)

    # Binarize the image based on a threshold (Otsu's method)
    thresh = threshold_otsu(image)
    binary = image < thresh  # True for black pixels, False for white

    # Label connected regions in the binary image
    labeled_image = label(binary)
    # plt.figure()
    # plt.imshow(image, cmap='nipy_spectral')

    # Find the largest square-like region that could be the black frame
    max_area = 0
    frame_bbox = None
    for region in regionprops(labeled_image):
        minr, minc, maxr, maxc = region.bbox
        width, height = maxc - minc, maxr - minr

        # Check if region is square-like and takes up at least 2/3 of the image area
        if 0.85 < width / height < 1.15 and width * height > (2 / 3) * image.size:
            if region.area > max_area:
                max_area = region.area
                frame_bbox = (minr, minc, maxr, maxc)

    # save cropped image
    if frame_bbox:
        minr, minc, maxr, maxc = frame_bbox
        cropped_image = image[minr:maxr, minc:maxc]
        # Add XX white pixel rows/columns on each side of the cropped image
        white_buffer = 40  # white pixel size buffer around detected frame
        cropped_image_with_border = cv2.copyMakeBorder(
            cropped_image, white_buffer, white_buffer, white_buffer, white_buffer, cv2.BORDER_CONSTANT,
            value=65535)  # 65535 = white for uint16
        io.imsave(f'{clip_dir}/{os.path.basename(image_path)[:-4]}_Cropped.tif', cropped_image_with_border)
        print(
            f' > clipped to {clip_dir}/{os.path.basename(image_path)[:-4]}_Cropped.tif [in {time.time() - start_time:.2f} seconds]')

        # Plot the original image with the detected frame
        fig, ax = plt.subplots()
        ax.imshow(image, cmap='gray')
        rect = plt.Rectangle((minc, minr), maxc - minc, maxr - minr,
                             edgecolor='red', linewidth=2, fill=False)
        ax.add_patch(rect)

        # plt.show()
        if save_fig:
            os.makedirs(f'{clip_dir}/frame_check', exist_ok=True)
            plt.savefig(f'{clip_dir}/frame_check/{os.path.basename(image_path)[:-4]}_frame.png', dpi=150,
                        bbox_inches='tight')
            plt.close()
    else:
        print('\033[91m !! No black frame detected in image {}\033[0m'.format(os.path.basename(image_path)))
        print(f'\033[91m --> error image skipped, and path saved to {clip_dir}/__error_images.txt\033[0m'.format(clip_dir))
        error_images.append(image_path)
        with open(os.path.join(clip_dir, '__error_images.txt'), 'a') as f:
            f.write("%s\n" % image_path)

def script_01_csize(input_image_folder, output_image_folder, subfolders=False, crop_to_frame = True):

    print(' ')
    print('=====================================================================')
    print('=           PYTHON SCRIPT FOR IMAGE CANVAS STANDARDIZING            =')
    print('=  Version 2.0.2 (July 2024)  |  B. Smets/A. Dille (RMCA/VUB)   =')
    print('=====================================================================')
    print(' ')
    
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

    if subfolders:
        for root, _, files in os.walk(input_image_folder):
            for file in files:
                if file.lower().endswith((".tif", ".tiff")) and not file.startswith('preview'):
                    allfiles.append(file)
                    allfiles_path.append(os.path.join(root, file))
    else:
        allfiles = [file for file in os.listdir(input_image_folder) if file.lower().endswith((".tif", ".tiff")) and not file.startswith('preview')]
        allfiles_path = [os.path.join(input_image_folder, file) for file in allfiles]

    images_list = allfiles
    images_list_path = allfiles_path

    # ### Define the list of images and count the number of files to process ###
    # Only main dir
    # allfiles = os.listdir(input_image_folder)
    # images_list = [filename for filename in allfiles if filename[-4:] in [".tif", ".TIF"]]  # ,".jpg",".JPG"
    # images_list = images_list + [filename for filename in allfiles if filename[-5:] in [".tiff", ".TIFF"]]

    print('Number of images to process: ' + str(len(images_list)))
    print(images_list)
    print(' ')

    # add a check if the image where not already processed
    canvas_sized_images_list = [image for image in os.listdir(output_image_folder) if image.endswith( '_CanvasSized.tif')]
    if len(canvas_sized_images_list) > 0:
        print('\033[92mSome images were already processed, they will be skipped...\033[0m\n')
        images_list_path = [image_path for image_path in images_list_path if os.path.basename(image_path)[:-4] +  '_CanvasSized.tif' not in canvas_sized_images_list]
        if len(images_list_path) == 0:
            print('All images were already processed to canvas size\n')
            if crop_to_frame:
                print('Now checking clip to frame...')
            else:
                return

    SKIP = False

    if SKIP == False and len(images_list_path) > 0:
        print(f'\033[93mNumber of images left to process: {str(len(images_list_path))}\033[0m')
        print('\n')
        ### Detect the max width and height in the dataset ###
        sizes = [Image.open(f, 'r').size for f in images_list_path]
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
            # file = os.path.join(input_image_folder, os.path.splitext(os.path.basename(image))[0] + '.tif')
            img = cv2.imread(image_path, -1)

            # print(n,img.shape[:2],image_path,len(img.shape))
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
        # n=1
        # for image_path in images_list_path:
        #     standardize_canvas(image_path,n)
        #     n+=1

    if crop_to_frame:


        print(' ')
        print('Clipping to frame...')

        clip_dir = output_image_folder + '_Cropped'
        os.makedirs(clip_dir, exist_ok=True)

        canvas_sized_images_list = [image for image in os.listdir(output_image_folder) if
                                    image.endswith('_CanvasSized.tif')]
        cropped_images_list = [image for image in os.listdir(clip_dir) if
                                    image.endswith('_Cropped.tif')]
        canvas_sized_images_list_path = [os.path.join(output_image_folder, image) for image in canvas_sized_images_list if image[:-4] +  '_Cropped.tif' not in cropped_images_list]

        if len(canvas_sized_images_list) == 0:
            print('All images were already clipped to frame\n')
            return
        else:
            print(f'Number of images left to process: {str(len(canvas_sized_images_list_path))}\n')

            total_start_time = time.time()
            for i, image_path in enumerate(canvas_sized_images_list_path):
                print(f' >> Image {i + 1}: {os.path.basename(image_path)}')

                try:
                    detect_black_frame(image_path, clip_dir, error_images, save_fig=True)
                except Exception as e:
                    print(f'Error: {e}')
                    print(f'Error in image {os.path.basename(image_path)}')
                    print(f' --> error image skipped, and path saved to {output_image_folder}/__error_images.txt')
                    error_images.append(image_path)

            total_end_time = time.time()
            print(f'Total time taken: {total_end_time - total_start_time:.2f} seconds')

            if len(error_images) > 0:
                print(f'\n {len(error_images)} error images found')
                for item in error_images:
                    print(f'Error  image {os.path.basename(item)}')
                print('  > error image paths can be found in __error_images.txt\n ')

        sleep(3)


    print(' ')
    print('======================')
    print(' PROCESSING COMPLETED ')
    print('======================')

    ##### END PROCESSING #####

if __name__ == "__main__":
    script_01_csize(input_image_folder, output_image_folder, subfolders, crop_to_frame)


