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
        - v2.1.0 (AD) October 2026
                - parallel processing enabled
                - optional direct reprojection at the output resolution (replaces Tool 3 +
                  Tool 4, without saving the full resolution reprojected images)
                - fixed the detection of already processed images (.tiff)
                - images whose fiducial marks were corrected after their reprojection are
                  reprojected again (FM coordinates used recorded in _fiducialmarks_used.csv)
"""

import numpy as np
import os, time
import pandas as pd
import cv2
from joblib import Parallel, delayed
import multiprocessing
from time import sleep
from pathlib import Path

import shutil

try:  # GAPPS package import (GUI)
    from GAPPS_tools.GAPPS_Tool_04_AirPhotos_Resize import sharpen_and_calibrate, to_bool
    from GAPPS_tools.GAPPS_Tool_02e_FM_Review import mark_array, reference_shape, reliable_marks, ACC_COLUMNS
except ImportError:  # standalone use from the GAPPS_tools folder
    from GAPPS_Tool_04_AirPhotos_Resize import sharpen_and_calibrate, to_bool
    from GAPPS_Tool_02e_FM_Review import mark_array, reference_shape, reliable_marks, ACC_COLUMNS


def reference_from_marks(FM, margin=0.02):
    """Target positions and output size for mid-side notches (no camera model needed).

    The shape of the four notches (top, right, bottom, left) is learnt from the confident detections of
    the dataset (accuracy >= 0.88, or reviewed), with its usual size (median left-right distance), rotated
    so that the left-right notches are horizontal. The output image covers the four notches plus a margin
    (fraction of the left-right distance), so that the whole image area is kept.
    :return: pts2 (4 x 2 float32, order top, right, bottom, left), width, height
    """
    P, S = mark_array(FM)
    ref = reference_shape(P, S)  # (top/bottom never detected with confidence: symmetric of the other one)
    if np.isnan(ref).any():
        raise ValueError('the shape of the notches could not be learnt (not enough confident detections): '
                         'review the fiducial marks first')
    ok = (S[:, 1] >= 0.88) & (S[:, 3] >= 0.88)
    scale = float(np.median(np.abs(P[ok, 1] - P[ok, 3])))
    z = ref * scale
    m = margin * scale
    x0, y0 = z.real.min() - m, z.imag.min() - m
    z = z - (x0 + 1j * y0)
    width, height = int(np.ceil(z.real.max() + m)), int(np.ceil(z.imag.max() + m))
    return np.float32([[v.real, v.imag] for v in z]), width, height


def fit_transform(pts1, pts2, mode, use=None):
    """Corners: perspective transform (4 points); mid-side notches: affine transform (least squares)
    on the reliable notches (`use`: indices, at least 3)."""
    if mode == 'midpoints':
        if use is not None and len(use) >= 3:
            pts1, pts2 = pts1[use], pts2[use]
        A = np.hstack([pts1, np.ones((len(pts1), 1), np.float32)])
        M, *_ = np.linalg.lstsq(A, pts2, rcond=None)
        return M.T.astype(np.float64)  # 2 x 3
    return cv2.getPerspectiveTransform(pts1, pts2)


def warp(img, M, size, flags=cv2.INTER_LINEAR):
    if M.shape == (2, 3):
        return cv2.warpAffine(img, M, size, flags=flags)
    return cv2.warpPerspective(img, M, size, flags=flags)

#### PARALLEL PROCESSING #####
# (Choose the number of CPU cores you want to use)
# (minimum = 1; suggested value = (number of cores) - 1)
# (if you don't know how many cores you have, write: 'multiprocessing.cpu_count()')
# Each worker holds a full resolution image and its reprojection in memory (~1 GB for a
# 1600 dpi scan): reduce the number of cores if the RAM is limited.

num_cores = max(1, min(4, multiprocessing.cpu_count() - 1))


def output_name(image_name, direct=False):
    """Name of the reprojected image (same names as Tool 3 + Tool 4 for the direct mode)."""
    stem = str(image_name.split('.')[0])
    return stem + ('_standardized_DownSharp.tif' if direct else '_standardized.tif')


FM_USED_CSV = '_fiducialmarks_used.csv'  # FM coordinates used for each reprojected image (output folder)
FM_KEYS = ['X1', 'Y1', 'X2', 'Y2', 'X3', 'Y3', 'X4', 'Y4']


def fm_signature(row):
    """FM coordinates (and accuracies, which select the notches used) of one row of Out_fiducialmarks.csv."""
    sig = [int(round(float(row[k]))) for k in FM_KEYS]
    sig += [round(float(row[c]), 2) if c in row and pd.notna(row[c]) else 0.0 for c in ACC_COLUMNS]
    return tuple(sig)


def read_fm_used(output_image_folder):
    """FM coordinates used for the images already reprojected: {image name (no extension): signature}."""
    path = os.path.join(output_image_folder, FM_USED_CSV)
    if not os.path.isfile(path):
        return {}
    try:
        df = pd.read_csv(path)
        return {str(r['name']): fm_signature(r) for _, r in df.iterrows()}
    except Exception:
        return {}


def write_fm_used(output_image_folder, used):
    """Write the FM coordinates used for each reprojected image (atomic write)."""
    rows = [dict(zip(['name'] + FM_KEYS + ACC_COLUMNS, (name,) + tuple(sig))) for name, sig in sorted(used.items())]
    path = os.path.join(output_image_folder, FM_USED_CSV)
    pd.DataFrame(rows, columns=['name'] + FM_KEYS + ACC_COLUMNS).to_csv(path + '.tmp', index=False)
    os.replace(path + '.tmp', path)


def last_reviews(input_image_folder):
    """Time of the last manual review of each image (Out_fiducialmarks_review_log.csv), as timestamps."""
    path = os.path.join(input_image_folder, 'Out_fiducialmarks_review_log.csv')
    if not os.path.isfile(path):
        return {}
    try:
        log = pd.read_csv(path)
        t = pd.to_datetime(log['time'], errors='coerce')
        log = log.assign(ts=[x.to_pydatetime().timestamp() if pd.notna(x) else np.nan for x in t])  # local time
        return log.groupby(log['name'].astype(str))['ts'].max().to_dict()
    except Exception:
        return {}


def images_to_process(input_image_folder, output_image_folder, images_list, FM, direct):
    """Images to (re)project: not done yet, or whose fiducial marks changed since their reprojection.

    The FM coordinates used are recorded in _fiducialmarks_used.csv; for images reprojected before this
    record existed, an image is redone if it was reviewed (review log) after its reprojection.
    :return: list of image files, dict {image file: reason} for the images redone, records of the others
    """
    FM = FM.assign(_stem=FM['name'].astype(str).map(lambda n: n.split('.')[0]))
    current = {s: fm_signature(r) for s, r in FM.drop_duplicates('_stem', keep='last').set_index('_stem').iterrows()}
    used = read_fm_used(output_image_folder)
    reviews = last_reviews(input_image_folder)
    todo, redo, keep = [], {}, {}
    for image in images_list:
        stem = image.split('.')[0]
        out = os.path.join(output_image_folder, output_name(image, direct is not None))
        if not os.path.isfile(out):
            todo.append(image)
            continue
        if stem not in current:  # no FM coordinates: nothing to compare (kept as it is)
            continue
        if stem in used:
            if used[stem] != current[stem]:
                todo.append(image)
                redo[image] = 'fiducial marks changed'
            else:
                keep[stem] = used[stem]
        else:
            t = reviews.get(stem)
            if t is not None and t == t and t > os.path.getmtime(out):
                todo.append(image)
                redo[image] = 'fiducial marks reviewed after the reprojection'
            else:
                keep[stem] = current[stem]  # assumed reprojected with the current coordinates
    return todo, redo, keep


def reproject_and_crop(input_image_folder, output_image_folder, image_name, FM, pts2, dimensionX, dimensionY,
                       mode='corners', direct=None):
    """Reproject one image based on its fiducial marks.

    :param direct: None to reproject at the scan resolution, or a dict with keys 'scale' (output dpi /
        input dpi), 'histo_cal' and 'sharpening_intensity' to reproject directly at the output resolution
        (the image is first downsampled with a bicubic interpolation as in Tool 4, then warped with a
        bicubic interpolation, sharpened and calibrated).
    """
    start_time = time.time()
    # Read the images, keep the original pixel depth (-1) and read its dimensions
    image_path = os.path.join(input_image_folder, image_name)
    img = cv2.imread(image_path, -1)
    if img is None:
        print(f'\033[91mImage {image_name} could not be read.\033[0m')
        return

    RVB = len(img.shape) != 2  # if True img not in grayscale. The program can not work

    if RVB:
        # save gray scale images
        # TODO : transform RVB images to grayscale image
        RVB_path = '{}/RVB_images'.format(output_image_folder)
        Path(RVB_path).mkdir(parents=True, exist_ok=True)
        ImageName = '{}.tif'.format(image_name)
        path = os.path.join(RVB_path, ImageName)
        cv2.imwrite(path, img)
        print('ignored' + image_name + 'because it isnt grayscale')
        return

    # Extract the image name and find the corresponding row with fiducial marks coordinates, in the CSV file
    try:
        idx = FM[FM['name'] == image_name.split('.')[0]].index[0]
    except IndexError:  # try with an extension to the name items
        try:
            idx = FM[FM['name'] == image_name].index[0]
        except IndexError:
            print(f'\033[91mImage {image_name} not found in the Out_fiducial.csv file.\033[0m')
            print(' Added to __error_images.txt')
            with open(os.path.join(output_image_folder, '__error_images.txt'), 'a') as f:
                f.write("%s\n" % image_path)
            return

    df = FM.loc[idx]

    # FM 1-4: corners (top-left, top-right, bottom-right, bottom-left) or mid-side notches (top, right,
    # bottom, left); for the notches, pts2 comes from reference_from_marks()
    pts1 = np.float32([[df['X1'], df['Y1']], [df['X2'], df['Y2']],
                       [df['X3'], df['Y3']], [df['X4'], df['Y4']]])
    use = None
    if mode == 'midpoints':  # only the reliable notches (score >= 0.88 or reviewed), if at least 3
        acc = [float(df[c]) if c in df and pd.notna(df[c]) else 0.0 for c in ACC_COLUMNS]
        use = reliable_marks(acc)
        if len(use) < 3:
            print(f'\033[93m   {image_name}: only {len(use)} reliable notch(es), the 4 notches are used '
                  f'(review this image with "Review / correct FM detection")\033[0m')
            use = None

    if direct is None:
        # Reprojection at the scan resolution
        M = fit_transform(pts1, pts2, mode, use)
        imready = warp(img, M, (dimensionX, dimensionY))
    else:
        # Direct reprojection at the output resolution. Output size and fiducial mark positions are those
        # of a reprojection at the scan resolution followed by a resize (Tool 4), for identical geometry.
        s = direct['scale']
        out_w, out_h = int(dimensionX * s), int(dimensionY * s)
        sx, sy = out_w / dimensionX, out_h / dimensionY
        pts2_out = np.float32([[(x + 0.5) * sx - 0.5, (y + 0.5) * sy - 0.5] for x, y in pts2])
        # Downsample the scan (bicubic, as Tool 4), and scale its fiducial marks accordingly. The downsampling
        # factor is measured on the fiducial marks (distances between them in the scan and in the output), so
        # that it is also right for scans made at another resolution than the nominal one (mixed folders)
        h, w = img.shape[:2]
        pairs = [(i, j) for i in range(4) for j in range(i + 1, 4)]
        spread_in = np.mean([np.linalg.norm(pts1[i] - pts1[j]) for i, j in pairs])
        spread_out = np.mean([np.linalg.norm(pts2_out[i] - pts2_out[j]) for i, j in pairs])
        s_img = spread_out / spread_in if spread_in > 0 else s
        small = cv2.resize(img, (max(1, int(round(w * s_img))), max(1, int(round(h * s_img)))),
                           interpolation=cv2.INTER_CUBIC)
        ax, ay = small.shape[1] / w, small.shape[0] / h
        pts1_small = np.float32([[(x + 0.5) * ax - 0.5, (y + 0.5) * ay - 0.5] for x, y in pts1])
        M = fit_transform(pts1_small, pts2_out, mode, use)
        # (bicubic warp: a bilinear one at this resolution visibly softens the image)
        imready = warp(small, M, (out_w, out_h), flags=cv2.INTER_CUBIC)
        # Unsharp mask and histogram calibration (as in Tool 4)
        imready = sharpen_and_calibrate(imready, direct['sharpening_intensity'], direct['histo_cal'])

    # Save the reprojected image
    Path(output_image_folder).mkdir(parents=True, exist_ok=True)  # Check if output folder exists
    cv2.imwrite(os.path.join(output_image_folder, output_name(image_name, direct is not None)), imready)
    print(f' > reprojected image saved: {image_name} [in time: {round((time.time() - start_time), 2)}s]')

    # Export a preview of the reprojected and cropped image --------------------------------
    preview_folder = os.path.join(output_image_folder, '_preview')
    Path(preview_folder).mkdir(parents=True, exist_ok=True)
    preview_image = cv2.resize(imready, (dimensionX // 12, dimensionY // 12), interpolation=cv2.INTER_AREA)
    cv2.imwrite(os.path.join(preview_folder, str(image_name.split('.')[0]) + '_preview.tif'), preview_image)
    return image_name.split('.')[0], fm_signature(df)  # FM coordinates used (recorded by the main process)


def image_reprojection(input_image_folder, output_image_folder, fiducialmarks_file,
                       camera, resolution_file, input_resolution, mode='corners',
                       output_resolution=None, histo_cal=True, sharpening_intensity=2):
    """Reproject the images based on the pixel coordinates of their fiducial marks.

    If output_resolution is given (dpi), the images are reprojected directly at this resolution, then
    sharpened and calibrated (replaces Tool 3 + Tool 4: no full resolution reprojected image is saved).
    """
    direct = None
    if output_resolution is not None:
        direct = {'scale': float(output_resolution) / float(input_resolution),
                  'histo_cal': to_bool(histo_cal),
                  'sharpening_intensity': int(sharpening_intensity)}

    print(' ')
    print('=====================================================================')
    print('=            PYTHON SCRIPT FOR IMAGE REPROJECTION                   =')
    print('=  Version 2.1.0 (October 2026)  |  B. Smets/A. Dille (RMCA/VUB)    =')
    print('=====================================================================')
    print(' ')

    print('\n Input parameters: ')
    print(f' Input image folder : {input_image_folder}')
    print(f' Output image folder : {output_image_folder}')
    print(f' Camera : {camera}')
    print(f' Fiducialmarks file : {fiducialmarks_file}')
    print(f' Camera Resolution file : {resolution_file}')
    print(f' Input resolution  : {input_resolution}')
    if direct:
        print(f' Direct reprojection to output resolution : {output_resolution} dpi '
              f'(histogram calibration: {direct["histo_cal"]}, sharpening: {direct["sharpening_intensity"]})')
    print(f' Fiducial location  : {mode}\n')

    os.makedirs(output_image_folder, exist_ok=True)

    # Define the list of images and count the number of files to process
    allfiles = os.listdir(input_image_folder)
    images_list = [filename for filename in allfiles if filename.lower().endswith(('.tif', '.tiff'))]

    # Import the CSV file with the fiducial marks coordinates of the images
    FM = pd.read_csv(fiducialmarks_file, sep=',', header=[0])
    FM.columns = FM.columns.str.strip()

    # Skip the images already processed, unless their fiducial marks changed since (e.g. corrected with
    # "Review / correct FM detection")
    n_all = len(images_list)
    images_list, redo, used = images_to_process(input_image_folder, output_image_folder, images_list, FM, direct)
    if len(images_list) < n_all:
        print('\033[92mSome images were already processed, they will be skipped...\033[0m\n')
        print(f'\033[93mNumber of images left to process: {str(len(images_list))}\033[0m\n\n')
    if redo:
        print(f'\033[93m{len(redo)} image(s) reprojected again (their output is replaced):\033[0m')
        for image, reason in redo.items():
            print(f'   {image}: {reason}')
        print('')

    print('Number of tasks (images to process): ' + str(len(images_list)))
    print(' ')

    if mode == 'midpoints':
        # Mid-side notches: target positions learnt from the dataset (the camera model is not used)
        pts2, dimensionX, dimensionY = reference_from_marks(FM)
        print(f' > Mid-side notches: output size {dimensionX} x {dimensionY} pix (at the scan resolution), '
              f'notch positions (top, right, bottom, left): {np.round(pts2).astype(int).tolist()}\n')
    else:
        # Import the projected coordinates of the fiducial marks, for the selected scan resolution
        res_file = pd.read_csv(resolution_file, sep=',', header=[0])
        res_col = res_file['Resolution']
        i = res_file.loc[res_col == int(input_resolution)].index[0]
        FM_proj = [[res_file['Xp1'][i], res_file['Yp1'][i]],
                   [res_file['Xp2'][i], res_file['Yp2'][i]],
                   [res_file['Xp3'][i], res_file['Yp3'][i]],
                   [res_file['Xp4'][i], res_file['Yp4'][i]]]
        pts2 = np.float32(FM_proj)
        dimensionX = int(res_file['X dimension (pixel)'][i])
        dimensionY = int(res_file['Y dimension (pixel)'][i])

    ##### PARALLEL PROCESSING #####
    if len(images_list) > 0:
        start_time = time.time()
        print(f' > reprojecting {len(images_list)} images in parallel on {num_cores} cores\n')
        results = Parallel(n_jobs=num_cores, verbose=30)(
            delayed(reproject_and_crop)(input_image_folder, output_image_folder, image_name, FM, pts2, dimensionX,
                                        dimensionY, mode, direct) for image_name in images_list)
        print(f'Total time taken: {time.time() - start_time:.2f} seconds')
        for r in results:
            if r is not None:
                used[r[0]] = r[1]
    # Record the FM coordinates used for each reprojected image (to detect later corrections)
    write_fm_used(output_image_folder, used)

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

    input_image_folder = r'E:\PROCESSING\SCANS\Dossier_Mohamed\_extra\_PROCESSING\A_CanvasSized_Cropped'
    input_image_folder = r'G:\PROCESSING\SCANS\Haute_Ruzizi_1955\_PROCESSING\A_CanvasSized_Cropped'
    input_image_folder = r'G:\PROCESSING\SCANS\Rwanda_1974_bukavu\Bande_12_13\PROCESSING\A_CanvasSized_Cropped'

    output_image_folder = rf'{os.path.dirname(input_image_folder)}/B_Reprojected'
    camera = 'Wild_RC5a'
    fiducialmarks_file = rf'{input_image_folder}\Out_fiducialmarks.csv'
    resolution_file = r"C:\Users\adille\Desktop\Softwares\GAPPS\camera_models\Wild_RC5a_Airphoto_dimensions_vs_dpi.csv"
    input_resolution = 1600
    mode = 'corners'  # fiducials location 'corners', 'midpoints'

    # ----------------------------------------------------------------------------
    ################################ END OF SETUP ###############################
    # ----------------------------------------------------------------------------

    image_reprojection(input_image_folder, output_image_folder,
                       fiducialmarks_file, camera, resolution_file, input_resolution, mode)
