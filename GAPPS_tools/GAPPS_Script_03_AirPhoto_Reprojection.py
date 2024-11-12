#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
------------------------------------------------------------------------------
PYTHON SCRIPT FOR AERIAL PHOTO ARCHIVE REPROJECTION INTO A STANDARD FORMAT
BEFORE PHOTOGRAMMETRIC PROCESSING USING AGISOFT METASHAPE PRO
------------------------------------------------------------------------------
This script aims to reproject the aerial photographs based on the pixel coordinates of the fiducial marks, in order
to obtain a homogeneous dataset with the center of perspective located in the middle of the images. To run this script,
you first need to create a table, in csv format, containing the XY coordinates (in pixel) of four fiducial marks used to
locate the center of perspective (see SCRIPT 02). A template of such a table is provided
(*"fiducial_marks_coordinates_TEMPLATE.csv"*). Please, keep the name of each columns similar to those in the
template, as these names are used in the script to find the corresponding information. Image's names, in the
CSV file, must also be similar to the files that will be processed. By default, the fiducial marks 1, 2, 3 and
4 correspond to the top-left, top-right, bottom-right and bottom-left corners, respectively. If the fiducial marks
are located at mid-distance from the corners, the fiducial marks 1, 2, 3 and 4 correspond to the top, right, bottom
and left positions, respectively.

Version: 2.0.1 (24/12/2021)
Authors: Benoît SMETS
        (Royal Museum for Central Africa  /  Vrije Universiteit Brussel)
        &
        Antoine DILLE for version 1.0.2, v2
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
      
    - Specific Python modules needed for this script:
        > Joblib
        > Numpy
        > OpenCV
        > Pandas
    
    - To use this script, simply adapt the directory paths and required values
      in the setup section of the script.

Log:
        - v1.0.2 (AD)
                - changed the way the image files are selected for better handling of different format
                - modified output size so that no 'image data' is lost in the process
                - adapted the naming convention of fiducial mark template
                - check if output folder exists and create if needed
                - improved image save name (only one '.tif')
                - handle two cases if image name column in csv has/has no extension
        - v2.0.1 (AD)
                - adapted for GAPP (graphic interface)
"""

import numpy as np
import os
import pandas as pd
import cv2
from joblib import Parallel, delayed
import multiprocessing
from time import sleep
from pathlib import Path


import shutil


#### PARALLEL PROCESSING #####
# (Choose the number of CPU cores you want to use)
# (minimum = 1; suggested value = (number of cores) - 1)
# (if you don't know how many cores you have, write: 'multiprocessing.cpu_count()')

num_cores =   multiprocessing.cpu_count() - 1




def image_reprojection(input_image_folder, output_image_folder, fiducialmarks_file,
                   camera,resolution_file,input_resolution):

    print(' ')
    print('=====================================================================')
    print('=            PYTHON SCRIPT FOR IMAGE REPROJECTION                   =')
    print('=  Version 2.0.1 (December 2021)  |  B. Smets/A. Dille (RMCA/VUB)   =')
    print('=====================================================================')
    print(' ')

    print('\n Input parameters: ')
    print(f' Input image folder : {input_image_folder}')
    print(f' Output image folder : {output_image_folder}')
    print(f' Camera : {camera}')
    print(f' Fiducialmarks file : {fiducialmarks_file}')
    print(f' Camera Resolution file : {resolution_file}')
    print(f' Input resolution  : {input_resolution}\n')

    ##### DEFINE ADDITIONAL USEFUL VARIABLES #####

    allfiles = os.listdir(input_image_folder)

    images_list = [filename for filename in allfiles if filename.lower().endswith(('.tif', '.tiff'))]
    
    FM = pd.read_csv(fiducialmarks_file, sep=',', header=[0]) 

    ##### DISPLAY THE NUMBER OF IMAGES TO PROCESS #####

    number_images = str(len(images_list))
    number_fidu_marks = str(len(FM))
    if number_fidu_marks >= number_images :
        print('Number of tasks (images to process): ' + number_images)
        print(' ')
   
    ### Coordinate of fiducial Marks depending on the resolution
    
    res_file = pd.read_csv(resolution_file, sep=',', header=[0])
    res_col = res_file['Resolution']   
    i = res_file.loc[res_col==int(input_resolution)].index[0]
    FM_proj = [[res_file['Xp1'][i],res_file['Yp1'][i]],
               [res_file['Xp2'][i],res_file['Yp2'][i]],
               [res_file['Xp3'][i],res_file['Yp3'][i]],
               [res_file['Xp4'][i],res_file['Yp4'][i]]]
    
    pts2 = np.float32(FM_proj)
    
        
    ##### DIMENSIONS OF THE OUTPUT IMAGE #####

    dimensionX = res_file['X dimension (pixel)'][i]
    dimensionY = res_file['Y dimension (pixel)'][i]
    
    ##### PROCESSING WORKFLOW #####
    
    def reproject_and_crop(image):
        # Read the images, keep the original pixel depth (-1) and read its dimensions
        # os.path.splitext(os.path.basename(image))[0] + '.tif')
        dst_filename = os.path.join(input_image_folder, image)
        img = cv2.imread(dst_filename, -1)
        
        RVB = len(img.shape)!=2 # if True img not in grayscale. The program can not work
        
         
        
        if RVB:
            # save gray scale images
            # TODO : transform RVB images to grayscale image
            RVB_path = '{}/RVB_images'.format(output_image_folder)
            Path(RVB_path).mkdir(parents=True, exist_ok=True)
            ImageName = '{}.tif'.format(image)
            path = os.path.join(RVB_path,ImageName)
            cv2.imwrite(path,img)
            print('ignored' + image +'because it isnt grayscale')
            
        else : 
            # Extract the image name and find the corresponding row with fiducial marks coordinates, in the CSV file
            try:
                idx = FM[FM['name'] == image.split('.')[0]].index[0]
            except:  # try with an extension to the name items"
                idx = FM[FM['name'] == image].index[0]

            df = FM.loc[idx]

            # pts1 = np.float32([[df['X1'][idx], df['Y1'][idx]], [df['X2'][idx], df['Y2'][idx]],
            #                    [df['X3'][idx], df['Y3'][idx]], [df['X4'][idx], df['Y4'][idx]]])
            pts1 = np.float32([[df['X1'], df['Y1']], [df['X2'], df['Y2']],
                               [df['X3'], df['Y3']], [df['X4'], df['Y4']]])
            # Reproject the image by applying the new coordinates of the fiducial marks and crop it at the provided dimensions
            M = cv2.getPerspectiveTransform(pts1, pts2)
            imready = cv2.warpPerspective(img, M, (dimensionX, dimensionY))
        
            # Export the reprojected and cropped images
            Path(output_image_folder).mkdir(parents=True,
                                            exist_ok=True)  # Check if output folder exists
            cv2.imwrite(os.path.join(output_image_folder, str(
                image.split('.')[0]) + '_standardized.tif'), imready)
            
            
    ##### PARALLEL PROCESSING #####
    multiprocess = False
    if multiprocess:
        Parallel(n_jobs=num_cores, verbose=30)(
        delayed(reproject_and_crop)(image) for image in images_list)
        
    else:    
        for i, image in enumerate(images_list):
            print(f'Processing image {image} [{i + 1}/{len(images_list)}]')
            reproject_and_crop(image)
    
    ##### END PROCESSING #####
    sleep(3)

    print(' ')
    print('======================')
    print(' PROCESSING COMPLETED ')
    print('======================')
    

    


if __name__ == "__main__":
    
    # ----------------------------------------------------------------------------
    ################################    SETUP     ################################
    # ----------------------------------------------------------------------------

    # DIRECTORY PATHS ##### (for Windows paths, please use "//" between directories ; for Mac, simply use "/" between directories)

    # path = r'F:\2_SfM_READY_photo_collection\Usumbura_1957-58-59\GAPP\test13\traitement'
    # input_image_folder = path+r'\01_CanvasSized'
    #
    # fiducialmarks_file = path+r'\01_CanvasSized/new_fiducial_marks_coordinates_Usumbura_1957-58-59.csv'
    #
    # output_image_folder =path+r'\02_Reprojected'
    #
    # if '02_Reprojected' in os.listdir(input_image_folder) :
    #     shutil.rmtree('{}/Reprojected'.format(input_image_folder))
    #     print('_________cleared___________')
    #
    # '''
    # fiducialmarks_file.csv example:
    #
    # name	X1	Y1	X2	Y2	X3	Y3	X4	Y4
    # 5942_005_CC_CanvasSized.tif	636	916	10383	766	10469	10424	730	10580
    # 5968_Bande-19-072_CanvasSized.tiff	727	750	11218	699	11175	11003	722	11061
    #
    # '''
    # camera = 'Wild RC510'  # !! Points location calculated for 'Wild RC5a' camera only for now... Could add others e.g., 'Fairchild K17B'
    #
    #
    # resolution_file = r'D:\ENSG_internship_2022\git\historical_airphoto_preprocessing\scriptsAndInterfaces\camera\Wild_RC10_Airphoto_Photo_dimensions_vs_dpi.csv'
    # input_resolution = 1500

    # input_image_folder = r'D:\PROCESSING\SCANS\SCANS_Kwamouth_Kutu_1955_1956\output_01\A_CanvasSized_Cropped'
    # output_image_folder = r'D:\PROCESSING\SCANS\SCANS_Kwamouth_Kutu_1955_1956\output_01\B_Reprojected'
    # camera = 'Wild_RC5a'
    # fiducialmarks_file = r'D:\PROCESSING\SCANS\SCANS_Kwamouth_Kutu_1955_1956\output_01\A_CanvasSized_Cropped\Out_fiducialmarks.csv'
    # resolution_file = r'C:\Users\adille\OneDrive - Africamuseum\_python\camera_models\Wild_RC5a_Airphoto_dimensions_vs_dpi.txt'
    # input_resolution = 1600
    # ----------------------------------------------------------------------------
    ################################ END OF SETUP ###############################
    # ----------------------------------------------------------------------------
    
    image_reprojection(input_image_folder, output_image_folder,
                   fiducialmarks_file, camera,resolution_file,input_resolution)
