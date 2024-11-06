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

import os
from PIL import Image
Image.MAX_IMAGE_PIXELS = 30000000000
import numpy as np
import cv2
from joblib import Parallel, delayed
import multiprocessing
from time import sleep
from pathlib import Path

################################    SETUP     ################################

##### DIRECTORY PATHS #####
#input_image_folder = r"D:\path\input"
#output_image_folder = r"D:\path\output"

#### PARALLEL PROCESSING #####
# (Choose the number of CPU cores you want to use)
# (minimum = 1; suggested value = (number of cores) - 1)
# (if you don't know how many cores you have, write: 'multiprocessing.cpu_count()')
num_cores = multiprocessing.cpu_count() - 1

################################ END OF SETUP ################################

def script_01_csize(input_image_folder, output_image_folder, subfolder=False):

    print(' ')
    print('=====================================================================')
    print('=           PYTHON SCRIPT FOR IMAGE CANVAS STANDARDIZING            =')
    print('=  Version 2.0.2 (July 2024)  |  B. Smets/A. Dille (RMCA/VUB)   =')
    print('=====================================================================')
    print(' ')
    

    os.chdir(input_image_folder)
    ### Define the list of images and count the number of files to process ###
    # also look into sub directory
    allfiles=[]
    allfiles_path=[]
    images_list=[]
    if subfolder:
        for root, dirs, files in os.walk(input_image_folder):
            for file in files:
                allfiles.append(file)
                images_list = [image for image in allfiles if image[-4:] in [".tif", ".TIF"]]  # ,".jpg",".JPG"
                images_list = images_list + [image for image in allfiles if image[-5:] in [".tiff", ".TIFF"]]
                allfiles_path.append(os.path.join(root, file))
                images_list_path = [image for image in allfiles_path if image[-4:] in [".tif", ".TIF"]]  # ,".jpg",".JPG"
                images_list_path = images_list_path + [image for image in allfiles_path if image[-5:] in [".tiff", ".TIFF"]]
    else:
        allfiles = os.listdir(input_image_folder)
        images_list = [filename for filename in allfiles if filename.endswith((".tif", ".TIF", ".tiff", ".TIFF"))]
        images_list_path = [os.path.join(input_image_folder, image) for image in images_list]

    # ### Define the list of images and count the number of files to process ###
    # Only main dir
    # allfiles = os.listdir(input_image_folder)
    # images_list = [filename for filename in allfiles if filename[-4:] in [".tif", ".TIF"]]  # ,".jpg",".JPG"
    # images_list = images_list + [filename for filename in allfiles if filename[-5:] in [".tiff", ".TIFF"]]

    print('Number of images to process: ' + str(len(images_list)))
    print(images_list)
    print(' ')

    # add a check if the image where not already processed
    canvas_sized_images_list = [image for image in os.listdir(output_image_folder) if image.endswith("_CanvasSized.tif")]
    if len(canvas_sized_images_list) > 0:
        print('Some images were already processed, they will be skipped...\n')
        images_list = [image for image in images_list if image[:-4] + '_CanvasSized.tif' not in canvas_sized_images_list]
        images_list_path = [os.path.join(input_image_folder, image) for image in images_list]
        if len(images_list_path) == 0:
            print('All images were already processed, nothing to do...')
            return


    if len(images_list_path) > 0:
        print('Number of images left to process: ' + str(len(images_list)))
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

        # Use parallel processing
        Parallel(n_jobs=num_cores, verbose=30)(delayed(standardize_canvas)(image_path) for image_path in images_list_path)
        # n=1
        # for image_path in images_list_path:
        #     standardize_canvas(image_path,n)
        #     n+=1

        sleep(3)

        print(' ')
        print('======================')
        print(' PROCESSING COMPLETED ')
        print('======================')

        ##### END PROCESSING #####

if __name__ == "__main__":
    script_01_csize(input_image_folder, output_image_folder,subfolder)



