"""
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
------------------------------------------------------------------------------
PYTHON SCRIPT FOR AERIAL PHOTO ARCHIVE RESIZING TO LOWER DPI
BEFORE PHOTOGRAMMETRIC PROCESSING USING AGISOFT METASHAPE PRO
------------------------------------------------------------------------------

# In order to smooth the potential noise introduced by the reprojection of each image, **I strongly suggest to
downsample the images to a lower resolution**. At the RMCA, we scan the photos at a resolution of 1600 dpi
(except for specific collections), which is, in general, too much considering the quality of the collections. So,
we use to resample the reprojected photos to 900 dpi (+ or - 300 dpi, depending on the quality of the dataset). The
script will resize all the images in a folder to a user defined resolution value using bicubic interpolation. An
unsharp mask can be applied after the interpolation, as well as a adaptative histogram calibration (CLAHE). Applying
an unsharp mask is an image sharpening technique commonly used in digital image processing software after downscaling
to maintain details in the image despite size changes (e.g. used by default in photoshop when downscaling an image).
The technique uses a blurred, or "unsharp", negative image to create a mask of the original image. The unsharp mask is
then combined with the original positive image, creating an image that is less blurry than the original.

Version: 2.0.1 (24/12/2021)
Authors: Antoine DILLE for version 1.0.1, v2
        (Royal Museum for Central Africa)

Citation:
    Smets, B., 2021
    Historical Aerial Photo Pre-Processing
    [Script_2_AirPhoto_Reprojection_v101.py].
    Version 1.0
    https://github.com/GeoRiskA/historical_airphoto_preprocessing
    DOI: N/A

Associated article (to be cited too):
    Smets, B., Dewitte, O., Michellier, C., Muganga, G., Dille, A., Kervyn, F.,
    SUBMITTED
    Insights into the SfM photogrammetric processing of historical
    panchromatic aerial photographs without camera calibration
    information.
    ISPRS International Journal of Geo-Information.
    DOI: N/A

Notes:

    - For the required Python libraries, we recommend the use of Anaconda
      or Miniconda.

    - To use this script, simply adapt the directory paths and required values
      in the setup section of the script.

Log:
        - v1.0.1 (AD)
        - v2.0.1 (AD)
                - adapted for GAPP (graphic interface)
Todo:
    - could be parallelized, but not sure it would be really faster (main limitation being probably the disk writing capacity)

Different options
    - OpenCV
    - Pillow
    - scikit image

see for unsharp mask in python
- https://www.idtools.com.au/unsharp-masking-with-python-and-opencv/
- https://stackoverflow.com/questions/32454613/python-unsharp-mask/32455269


"""

import os
import time
from pathlib import Path
import pandas as pd

import cv2
import numpy as np

# ----------------------------------------------------------------------------
################################    SETUP     ################################
# ----------------------------------------------------------------------------
#
# input_image_folder = r"E:\Adille-Data\RESIST\GIS\Optical_Imagery\Aerial_Photographs_Bukavu_1958-59\Aerial_Pictures\Bukavu_1959_CC\CanvasSized_02\Reprojected"
# output_image_folder = input_image_folder + '/Downscaled_60_2_hist'

extension = '.tif'  # '.png'. output file extension
tool = 'opencv'  # opencv works best, and is the only one thoroughly tested. also 'pillow' and 'scikit'
# apply Contrast Limited adaptive histogram equalization to image (CLAHE)
HistoCal = True
scale_percent = 60  # percent of original size. e.g., with 60% -->  1500dpi*0.6=900 dpi
# [0, 1 or 2]; 0 for no sharpening, 1 for low intensity, 2 for medium intensity sharpening.
SharpeningIntensity = 2
# can be further tuned in the function unsharp_mask_OpenCV

# ----------------------------------------------------------------------------
################################ END OF SETUP ###############################
# ----------------------------------------------------------------------------


def image_resampling_sharpening(input_image_folder, output_image_folder, HistoCal, SharpeningIntensity, scan_resolution,output_res):

    print(' ')
    print('=====================================================================')
    print('=         PYTHON SCRIPT FOR AIR PHOTO ARCHIVE DOWNSAMPLING         =')
    print('=         Version 2.0.1 (December 2021)  |  A. Dille (RMCA/VUB)     =')
    print('=====================================================================')
    print(' ')
    scale_percent = np.round(100 / float(scan_resolution) * float(output_res),2)

    print('\n Input parameters: ')
    print(f' Input image folder : {input_image_folder}')
    print(f' Output image folder : {output_image_folder}')
    print(f' scan_resolution : {scan_resolution}')
    print(f' output resolution  : {output_res}')
    print(f' Rescale percentage : {scale_percent}')
    print(f' Histo Cal : {HistoCal}\n')


    # --------------------------------------------------
    # listing files to process
    # --------------------------------------------------

    allfiles = os.listdir(input_image_folder)

    images_list = [filename for filename in allfiles if filename.lower().endswith(('.tif', '.tiff'))]
    resized_images_list = [image for image in os.listdir(output_image_folder) if
                       image.endswith('_standardized.tif')]
    images_list = [image for image in images_list if
                   image[:-4] + '_DownSharp.tif' not in resized_images_list]

    print('\n-------------------------------'
          '\n-------------------------------\n'
          ' > found ' + str(len(images_list)) + ' images to process'
          '\n-------------------------------'
          '\n-------------------------------\n')
    if len(resized_images_list) > 0:
        print('\033[92mSome images were already processed, they will be skipped...\033[0m\n')
        print(f'\033[93mNumber of images left to process: {str(len(images_list))}\033[0m\n\n')

    if tool == 'opencv':
        print('\n --------------------------------------'
              '\n Using OpenCV to resize the images \n '
              '-----------------------------------------\n')
        start_time = time.time()

        OpenCVDownscaler(images_list, scale_percent,resized_images_list,input_image_folder,output_image_folder,scan_resolution,output_res)  # main

        print("\n--- data processing time was %.2f s seconds ---\n" %
              (time.time() - start_time))

        # check number of file processed compared to input files
        outfiles = os.listdir(output_image_folder)
        outimlist = [filename for filename in outfiles if filename[-4:]
                     in [".tif", ".TIF", ".png", ".jpg", ".JPG"]]
        
        outimlist = outfiles + [filename for filename in outimlist if filename[-5:] in [".tiff", ".TIFF"]]
        if len(images_list) != len(outimlist):
            print('*** WARNING ***')
            print('! it seems that some image(s) have not been processed!')
            print('--> # of input images= ' + str(len(images_list)) +
                  ' while # of processed images= ' + str(len(outimlist)) + ' <--')
            print('*** WARNING ***')
    # --------------------------------------------------
    # Functions
    # --------------------------------------------------

def unsharp_mask_OpenCV(image, kernel_size=(3, 3), sigma=1.0):
    # First we blur the image. By smoothing an image we suppress
    im_blurred = cv2.GaussianBlur(image, kernel_size, sigma)
    # most of the high-frequency components.

    # Second we subtract this smoothed image from the original image(the resulting difference is known as a mask).
    # Thus, the output image will have most of the high-frequency components that are blocked by the smoothing filter.
    # Adding this mask back to the original will enhance the high-frequency components.
    if SharpeningIntensity == 1:  # low intensity
        sharpened = cv2.addWeighted(image, 2, im_blurred, -1.0, 0)
    elif SharpeningIntensity == 2:  # medium intensity
        sharpened = cv2.addWeighted(image, 1.0 + 3.0, im_blurred, -3.0, 0)

    return sharpened

# functions
def get_resizing_settings(resolution_file,output_res):
    res_file = pd.read_csv(resolution_file, sep=',', header=[0])
    res_col = res_file['Resolution']
    i = res_file.loc[res_col==output_res].index[0]
    settings = (res_file['X dimension (pixel)'][i],res_file['Y dimension (pixel)'][i])
    
    print(settings)
    
    return settings

def unsharp_mask_Pillow(image, Inradius=3):
    from PIL import ImageFilter
    sharpened = image.filter(ImageFilter.UnsharpMask(radius=Inradius, percent=150))
    return sharpened

def OpenCVDownscaler(images_list, scale_percent,resized_images_list,input_image_folder,output_image_folder,resolution_file,output_res):
    # A. Downscaling with OpenCV
    for i, image in enumerate(images_list):
        print('\n >>> Image [' + str(i+1) + '/' +
              str(len(images_list)) + ']: ' + image)
        
        img = cv2.imread(input_image_folder + '/' + image, cv2.IMREAD_UNCHANGED)
        print('     Original Dimensions : ', img.shape)

        width = int(img.shape[1] * scale_percent / 100)
        height = int(img.shape[0] * scale_percent / 100)
        dim = (width, height)
        
        # ##### Amelie worked here
        # !! if used need to import the resolution_file file in the function...
        # dim = get_resizing_settings(resolution_file, output_res)
        
        ############################
        
        # resize image
        # INTER_CUBIC is a bicubic interpolation
        resized = cv2.resize(img, dim, interpolation=cv2.INTER_CUBIC)

        """[optional] flag that takes one of the following methods. INTER_NEAREST – a nearest-neighbor interpolation INTER_LINEAR
        – a bilinear interpolation (used by default) INTER_AREA – resampling using pixel area relation. It may be a
        preferred method for image decimation, as it gives moire’-free results. But when the image is zoomed, it is
        similar to the INTER_NEAREST method. INTER_CUBIC – a bicubic interpolation over 4×4 pixel neighborhood INTER_LANCZOS4 – a
        Lanczosinterpolation over 8×8 pixel neighborhood
        """

        print('     Resized Dimensions : ', resized.shape)

        # B. apply unsharp mask to resized image
        if SharpeningIntensity > 0:
            resized = unsharp_mask_OpenCV(
                resized, kernel_size=(3, 3), sigma=1.0)

        # C. apply Contrast Limited adaptive histogram equalization to image (CLAHE)
        if HistoCal is True:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(40, 40))
            resized = clahe.apply(resized)

        # D. Save the image
        Path(output_image_folder).mkdir(parents=True, exist_ok=True)
        resized_name = image[:-4] + "_DownSharp" + extension
        downSname = output_image_folder + '/' + resized_name   # output filename

        # Saving the image using cv2.imwrite() method
        cv2.imwrite(downSname, resized)
        print('    -> saved to: ' + downSname)
        resized_images_list.append(resized_name)
    


if __name__ == "__main__":
    input_image_folder = r"D:/PROCESSING/SCANS/SCANS_Kwamouth_Kutu_1955_1956/output_01/B_Reprojected"
    output_image_folder = r"D:/PROCESSING/SCANS/SCANS_Kwamouth_Kutu_1955_1956/output_01/C_Resampled"
    scan_resolution = 1600
    output_res = 600
    HistoCal = True
    image_resampling_sharpening(input_image_folder, output_image_folder, HistoCal, SharpeningIntensity, scan_resolution, output_res)

