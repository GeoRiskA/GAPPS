"""
========================================================================================
                     GAPPS – GeoRiskA Airphoto Pre-Processing Suite
========================================================================================
                             = AUTOMATIC FM DETECTION =

Description: This script aims to detect the (pixel coordinates) centre of the four
    fiducial marks of an aerial image. This information will be used to reproject the
    aerial photographs in order to obtain a homogeneous dataset with the center of
    perspective located in the middle of the images. It requires one (or more) template
    for each fiducial of a typical aerial image of the dataset. One can precise the
    presence of stripes with no data around some side of the image. It is worth noting
    that a) it is OpenCV tool matchTemplate that is used, the latter is not able to
    account for change in size nor orientation (e.g., rotation) between the template
    and the image (--> so consider using the tool to have templates at the correct size
    for your dataset); b) for now it only handles fiducials located in the corner of the
    image; c) there are some checks to monitor the accuracy of the matching and provide
    warnings, but sometimes it is not sufficient --> do not hesitate to do a visual
    check of the coordinates found. To help with that one figure with the location of the
    four fiducials is created for each images (in folder >/_temp_corners/_all_fiducials).

Copyright:
    RMCA — Royal Museum for Central Africa (Tervuren, BELGIUM)
        Natural Hazards and Cartography (GeoRiskA), Dpt. of Earth Sciences
    VUB — Vrije Universiteit Brussel (Brussels, BELGIUM)
        Cartography and GIS research group (CGIS), Dpt. of Geography
    © 2021 – 2024

Software management and coordination:
    - Benoît SMETS (RMCA / VUB)

Software authorship:
    - Paul BARRIERE (ENSG)
    - Antoine Dille (RMCA)
    - Benoît SMETS (RMCA / VUB)

The script was developed on Windows 10 and MacOS ≥ 14.6. This script remains unclean,
in development, and is subject to change.

Changes (October 2026): all the templates of the template folder are used (the best match is kept);
    templates are rescaled for images scanned at another resolution (size of the source image recorded
    in Center_Fiducials.txt, or else the typical image size of the folder); coarse-to-fine matching.
    Cross-shaped marks: the centre is then refined at the intersection of the two lines of the cross, because
    the bright disc and the frame around the mark do not always have the same position relative to the cross.

Last update: 2026-10-29
========================================================================================
"""

import os, time, shutil
import sys
import copy
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib
from time import sleep
import multiprocessing
from joblib import Parallel, delayed
import cv2

# Suppress FutureWarning messages (humhumhum)
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

from GAPPS_tools.GAPP_ORIGINAL_AutomaticFiducialDetection import MatchingValueThreshold

# so that no figures are showing up (note that it may pose problems when using Spyder (?))
matplotlib.use('Agg')

# Developer's setup (Do not modify)
# -----------------
DebugMode = False
OneTemplateMax = False  # (not used anymore: all the templates are tried, the best match is kept)



def toCSV(image, Coo, fidu_coordinates):
    """
    Fonction detecting the manual marking of fiducial marks and returning a csv line corresponding.

    :param image: path of the image file
    :type image: string

    :return: line to fill the csv file (corresponding to the image)
    :rtype : DataFrame
    """    
    name = os.path.splitext(os.path.basename(image))[0]
    X1,Y1 =Coo['top_left' ][0],Coo['top_left' ][1]    
    X2,Y2 =Coo['top_right'][0],Coo['top_right'][1]
    X3,Y3 =Coo['bot_right'][0],Coo['bot_right'][1]
    X4,Y4 =Coo['bot_left' ][0],Coo['bot_left' ][1]
    top_left_accuracy = round(fidu_coordinates[fidu_coordinates['corner'] == 'top_left']['maxVal'].values[0],2)
    top_right_accuracy = round(fidu_coordinates[fidu_coordinates['corner'] == 'top_right']['maxVal'].values[0],2)
    bot_right_accuracy = round(fidu_coordinates[fidu_coordinates['corner'] == 'bot_right']['maxVal'].values[0],2)
    bot_left_accuracy = round(fidu_coordinates[fidu_coordinates['corner'] == 'bot_left']['maxVal'].values[0],2)

    line = pd.DataFrame({'name':name,
      'X1':[X1],'Y1':[Y1],
      'X2':[X2],'Y2':[Y2],
      'X3':[X3],'Y3':[Y3],
      'X4':[X4],'Y4':[Y4],
      'top_left_accuracy':[top_left_accuracy],
      'top_right_accuracy':[top_right_accuracy],
      'bot_right_accuracy':[bot_right_accuracy],
      'bot_left_accuracy':[bot_left_accuracy]                   }      )
    
    return (line)


def addLine(image_name, Coord, fidu_coordinates, Out_fiducialmarks_CSV):
    """
    Fonction adding a line to the csv we are creating

    :param image: path of the image file
    :type image: string

    :return: None
    """
    line = toCSV(image_name, Coord, fidu_coordinates)
    columns = ['name', 'X1', 'Y1', 'X2', 'Y2', 'X3', 'Y3', 'X4', 'Y4', 'top_left_accuracy', 'top_right_accuracy', 'bot_right_accuracy', 'bot_left_accuracy']
    if os.path.exists(Out_fiducialmarks_CSV):
        f = pd.read_csv(Out_fiducialmarks_CSV)
        if not f[f['name'] == image_name].empty:
            return
        line.columns = f.columns # to have the same order
        f = pd.concat([f, line], ignore_index=True)
        f.to_csv(Out_fiducialmarks_CSV, mode='w', sep=",", index=False)

    else:
        with open(Out_fiducialmarks_CSV, 'w') as f:
            f.write(
                'name, X1, Y1, X2, Y2, X3, Y3, X4, Y4, top_left_accuracy, top_right_accuracy, bot_right_accuracy, bot_left_accuracy\n')
        f = line
        f.to_csv(Out_fiducialmarks_CSV, mode='w', sep=",", index=False, header=columns)


def distance(matrice, xc, yc):
    """
    Calculate distance between 2 points

    :param matrice: matrice of points'coordinates
    :type matrice: numpy [int,int]
    :param xc: pixel's column of the center in template image
    :type xc: int
    :param yc: pixel's line of the center in template image
    :type yc: int

    :return: distance between 2 points 
    :rtype: float

    """
    dx = matrice[:, :, 0]-xc
    dy = matrice[:, :, 1]-yc
    return np.sqrt(dx**2 + dy**2)


def CenterFiducial_LUCASKANADE(img2, Fidu_type, orientation, template, xc, yc, image_name, corner, type_fidu, corner_folder):
    """
   allow to detect and give the coordinates of a fiducial mark using the Lucas Kanade filter

   :param img2: image cropped where the fiducial should be 
   :type img2: .tif
   :param Fidu_type: type of fiducial : 'rectangular'; 'target'
   :type Fidu_Type: str
   :param template:image of the template of the fiduciale
   :type template: .tif
   :param orientation: orientation of rectangular fidicial 'h' : horizontal or 'v' : vertical
   :type orientation: str
   :param xc: pixel's column of the center in template image
   :type xc: int
   :param yc: pixel's line of the center in template image
   :type yc: int

   :return: u,v Coordinates of the fiducial
   :rtype: int,int
   """
    text = image_name + '_' + corner

    # First try template matching (existing approach)
    res = cv2.matchTemplate(img2, template, cv2.TM_CCOEFF_NORMED)
    (_, maxVal, _, maxLoc) = cv2.minMaxLoc(res)

    if DebugMode is True:
        print('     template matching statistics for ' + corner +
              ' > Max value: ' + str(maxVal) + ' | ' + str(maxLoc))


    # If template matching confidence is low, try feature-based approach
    # MatchingValueThreshold = 0.9
    # if maxVal < MatchingValueThreshold:
    #     # Try ML-based detection
    #     ml_x, ml_y, ml_conf = integrate_ml_fiducial_detection(img2, corner_folder, corner, image_name)
    #
    #     if ml_x is not None and ml_conf > 0.5:
    #         return ml_x, ml_y, ml_conf
    #     print(f"     Template matching for {corner} below threshold ({maxVal:.2f} < {MatchingValueThreshold})")
    #     # print(f"     Trying feature-based detection for {corner}...")
    #     #
    #     # # Try multiple feature types and take the best one
    #     # feature_results = []
    #     # for feat_type in ['AKAZE', 'SIFT', 'ORB']:
    #     #     feature_x, feature_y, feature_conf = feature_based_detection(corner_image=img2,
    #     #                                                                  template_image=template,
    #     #                                                                  corner_folder=corner_folder,
    #     #                                                                  feature_type=feat_type)
    #     #     if feature_x is not None:
    #     #         feature_results.append((feature_x, feature_y, feature_conf, feat_type))
    #     #
    #     # # If we have any valid results, pick the one with highest confidence
    #     # if feature_results:
    #     #     feature_results.sort(key=lambda x: x[2], reverse=True)
    #     #     feature_x, feature_y, feature_conf, feat_type = feature_results[0]
    #     #
    #     #     # Be more permissive - accept reasonable confidence matches
    #     #     if feature_conf > 0.35:  # Lower threshold to accept more results
    #     #         print(f"     {feat_type} feature matching successful for {corner}")
    #     #         print(f"     Confidence: {feature_conf:.2f} | Position: ({feature_x:.1f}, {feature_y:.1f})")
    #     #
    #     #         return feature_x, feature_y, feature_conf
    #     # else:
    #     #     print(f"     All feature-based methods failed for {corner}. Falling back to original approach.")
    #
    #     print(f"     Trying enhanced Hough Transform for {corner}...")
    #     hough_x, hough_y, hough_conf = enhanced_hough_detection(
    #         corner_image=img2,
    #         template_image=template
    #     )
    #
    #     if hough_x is not None and hough_conf > 0.3:
    #         print(f"     Hough Transform successful for {corner}")
    #         print(f"     Confidence: {hough_conf:.2f} | Position: ({hough_x}, {hough_y})")
    #         return hough_x, hough_y, hough_conf
    #
    #     print(f"     Hough Transform failed for {corner}. Falling back to original approach.")

    # Continue with original approach if template matching was good or feature-based failed
    Sfid = 0
    Img = img2[maxLoc[1] - Sfid:maxLoc[1] + template.shape[0] + Sfid,
          maxLoc[0] - Sfid:maxLoc[0] + template.shape[1] + Sfid]
    im_gray = cv2.cvtColor(Img, cv2.COLOR_BGR2GRAY)

    # Original approach with ShiTomasi corner detection
    if type_fidu == "barycentre":
        feature_params = dict(maxCorners=25,
                              qualityLevel=0.01,
                              minDistance=3,
                              blockSize=3)

        p0 = cv2.goodFeaturesToTrack(im_gray, **feature_params)
        d = distance(p0, xc, yc)
        err = np.argsort(d, axis=0)
        if (d[err[0][0]][0] >= 15):
            x = xc
            y = yc
        else:
            i = 0
            x = 0
            y = 0
            while (i < 4 and d[err[i][0]][0] < 15):
                x += p0[err[i][0]][0][0]
                y += p0[err[i][0]][0][1]
                i += 1
            x = x / i
            y = y / i

        # Visualization
        final_mask = copy.deepcopy(im_gray)
        final_mask = cv2.circle(
            final_mask, (int(round(x)), int(round(y))), 1, 255, -1)
        save_folder_path = corner_folder + '/' + corner + "/barycentre/"

        if DebugMode:  # debug images (one per corner and image)
            Path(save_folder_path).mkdir(parents=True, exist_ok=True)
            plt.imsave(save_folder_path + "/file_%s.png" % (text), final_mask)

    elif type_fidu == "fixed":
        x = xc
        y = yc
        final_mask = copy.deepcopy(im_gray)
        final_mask = cv2.circle(
            final_mask, (int(round(x)), int(round(y))), 1, 255, -1)
        save_folder_path = corner_folder + '/' + corner + "/fixedCopie/"

        if DebugMode:  # debug images (one per corner and image)
            Path(save_folder_path).mkdir(parents=True, exist_ok=True)
            plt.imsave(save_folder_path + "/file_%s.png" % (text), final_mask)

    return x+maxLoc[0], y+maxLoc[1], maxVal


def FindCircles(corner_image, DP=0.05, MinDist=20, MinRadius=170, MaxRadius=250, parameter2=100):
    """
    OpenCV HoughCircles is used when template matching isn't working. It only works if the fiducial is a circle...

    :param corner_image_path:
    :param DP:This parameter is the inverse ratio of the accumulator resolution to the image resolution
    (see Yuen et al. for more details). Essentially, the larger the dp gets, the smaller the accumulator array gets.
    :param MinDist: Minimum distance between the center (x, y) coordinates of detected circles. If the minDist is too
    small, multiple circles in the same neighborhood as the original may be (falsely) detected. If the minDist is too
    large, then some circles may not be detected at all.
    :param MinRadius: Minimum size of the radius (in pixels).
    :param MaxRadius: Maximum size of the radius (in pixels).
    :param parameter2: Accumulator threshold value for the cv2.HOUGH_GRADIENT method. The smaller the threshold is,
    the more circles will be detected (including false circles). The larger the threshold is less circles will
    potentially be returned.
    :return:
    """

    # corner_image = cv2.imread(corner_image_path, cv2.CV_8UC1)
    corner_imageBlr = cv2.GaussianBlur(
        corner_image, (11, 11), cv2.BORDER_DEFAULT)

    im = corner_imageBlr

    detected_circles = None
    # or len(detected_circles[0])<2: # will decrease the parameter2 until it founds a circle
    while detected_circles is None:
        detected_circles = cv2.HoughCircles(im,
                                            cv2.HOUGH_GRADIENT, dp=DP, minDist=MinDist, param1=50,
                                            param2=parameter2, minRadius=MinRadius, maxRadius=MaxRadius)
        if DebugMode is True:
            print('   ' + os.path.basename(corner_image) + '> ' +str(MinDist) + ' ' + str(parameter2))  # for debugging

        parameter2 = parameter2 - 2

        if parameter2 < 14:
            break
        
    if DebugMode is True:
        fig, axs = plt.subplots(1, 2, figsize=(6, 6))
        fig.suptitle(os.path.basename(corner_image[:-4]), fontweight="bold")
        axs[0].imshow(corner_image, cmap=plt.cm.gray)
        axs[0].set_title('corner')
        axs[1].imshow(im)
        axs[1].set_title('thresholded')
        
        if detected_circles is not None:
            for i in range(len(detected_circles[0])):
                circle1 = plt.Circle((detected_circles[0][i][0], detected_circles[0][i][1]),
                                     (detected_circles[0][i][2]), fill=False, color='r')
                axs[1].add_patch(circle1)
                axs[1].plot(detected_circles[0][i][0],
                            detected_circles[0][i][1],
                            'r', marker=".", markersize=10)

    return detected_circles

def integrate_ml_fiducial_detection(img2, corner_folder, corner, image_name):
    """
    Integrate machine learning-based fiducial detection

    :param img2: Corner image
    :param corner_folder: Folder for corner images
    :param corner: Corner identifier
    :param image_name: Image name
    :return: x, y coordinates and confidence
    """
    try:
        # Import the detection function
        from fiducial_detection_dl import detect_fiducial_rf

        # Path to trained model
        model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 'trained_models', 'fiducial_rf_model.joblib')

        if os.path.exists(model_path):
            print(f"     Using ML-based detection for {corner}...")
            x, y, conf = detect_fiducial_rf(img2, model_path, corner, image_name)

            if conf > 0.5:
                print(f"     ML detection successful for {corner}: ({x}, {y}), confidence: {conf:.2f}")
                return x, y, conf
            else:
                print(f"     ML detection confidence too low: {conf:.2f}")
        else:
            print(f"     ML model not found at {model_path}")
    except Exception as e:
        print(f"     Error in ML detection: {str(e)}")

    return None, None, 0.0

def enhanced_hough_detection(corner_image, template_image=None, min_radius=20, max_radius=250):
    """
    Enhanced Hough Transform detection for fiducial marks with optimized performance

    :param corner_image: Cropped corner image containing fiducial mark
    :param template_image: Optional template image (used for sizing hints)
    :param min_radius: Minimum radius to detect
    :param max_radius: Maximum radius to detect
    :return: (x, y) coordinates of fiducial center, confidence score
    """
    # Convert to grayscale if needed
    if len(corner_image.shape) == 3:
        gray = cv2.cvtColor(corner_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = corner_image.copy()

    # Get template size for auto-radius calculation if template is provided
    if template_image is not None:
        if len(template_image.shape) == 3:
            template_gray = cv2.cvtColor(template_image, cv2.COLOR_BGR2GRAY)
        else:
            template_gray = template_image.copy()

        # Estimate radius range based on template size
        template_size = min(template_gray.shape)
        min_radius = max(10, int(template_size * 0.2))
        max_radius = int(template_size * 0.8)

    # Apply preprocessing to enhance circle detection - more efficient pipeline
    # 1. Blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # 2. CLAHE for contrast enhancement (only if needed)
    if np.std(blurred) < 30:  # Only apply CLAHE if contrast is low
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        blurred = clahe.apply(blurred)

    # 3. Edge detection - useful for confidence calculation later
    edges = cv2.Canny(blurred, 50, 150)

    # Optimize parameter combinations - fewer combinations
    dp_values = [1.5]  # Most reliable value
    param1_values = [100]
    param2_values = [70, 50, 30]  # Try high values first, then lower

    circles_found = []
    confidence_scores = []

    # Try parameter combinations
    for dp in dp_values:
        for param1 in param1_values:
            for param2 in param2_values:
                try:
                    # Apply HoughCircles
                    circles = cv2.HoughCircles(
                        blurred,
                        cv2.HOUGH_GRADIENT,
                        dp=dp,
                        minDist=30,
                        param1=param1,
                        param2=param2,
                        minRadius=min_radius,
                        maxRadius=max_radius
                    )

                    if circles is not None:
                        # Convert to integers
                        circles = np.uint16(np.around(circles))

                        # Only keep circles within image bounds with margin
                        for circle in circles[0, :]:
                            x, y, r = circle
                            margin = 10
                            if (x >= margin and y >= margin and
                                x < gray.shape[1] - margin and
                                y < gray.shape[0] - margin):

                                # Calculate confidence - check edge alignment
                                mask = np.zeros_like(edges)
                                cv2.circle(mask, (x, y), r, 255, 2)

                                # Calculate edge alignment score
                                edge_pixels = np.sum(edges[mask == 255]) / np.sum(mask == 255)
                                confidence = min(1.0, edge_pixels / 100)  # Normalize

                                circles_found.append((x, y, r))
                                confidence_scores.append(confidence)

                        # If we found good circles, stop searching
                        if len(circles_found) > 0 and confidence_scores[-1] > 0.4:
                            break

                except Exception as e:
                    continue

            # Early termination if good circles found
            if len(circles_found) > 0 and max(confidence_scores) > 0.4:
                break

        # Early termination if good circles found
        if len(circles_found) > 0 and max(confidence_scores) > 0.4:
            break

    # If no circles found, return None
    if not circles_found:
        print("      No circles found with Hough Transform")
        return None, None, 0.0

    # Sort by confidence and take the best one
    best_idx = np.argmax(confidence_scores)
    x, y, r = circles_found[best_idx]
    confidence = confidence_scores[best_idx]

    print(f"      Hough Transform found circle at ({x}, {y}) with radius {r}, confidence: {confidence:.2f}")

    # Add debugging visualization if needed
    if DebugMode:
        result = corner_image.copy()
        cv2.circle(result, (x, y), r, (0, 255, 0), 2)  # Draw circle
        cv2.circle(result, (x, y), 2, (0, 0, 255), 3)  # Draw center

        # Create debug folder
        debug_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'debug_hough')
        os.makedirs(debug_folder, exist_ok=True)

        # Save debug image
        debug_path = os.path.join(debug_folder, f"hough_circle_{confidence:.2f}.jpg")
        cv2.imwrite(debug_path, result)

    return int(x), int(y), confidence


def feature_based_detection(corner_image, template_image,corner_folder, feature_type='AKAZE'):
    """
    Enhanced feature-based detection for fiducial marks with better preprocessing
    and more relaxed matching criteria for historical imagery

    :param corner_image: Cropped corner image containing fiducial mark
    :param template_image: Template image of the fiducial mark
    :param feature_type: Type of feature detector to use ('SIFT', 'ORB', or 'AKAZE')
    :return: (x, y) coordinates of fiducial center, confidence score
    """
    # Convert images to grayscale if they're not already
    if len(corner_image.shape) == 3:
        corner_gray = cv2.cvtColor(corner_image, cv2.COLOR_BGR2GRAY)
    else:
        corner_gray = corner_image.copy()

    if len(template_image.shape) == 3:
        template_gray = cv2.cvtColor(template_image, cv2.COLOR_BGR2GRAY)
    else:
        template_gray = template_image.copy()

    # Get dimensions
    h_template, w_template = template_gray.shape
    h_corner, w_corner = corner_gray.shape

    # Enhanced preprocessing to improve feature detection
    # Apply CLAHE to improve contrast
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    corner_gray = clahe.apply(corner_gray)
    template_gray = clahe.apply(template_gray)

    # Blur to reduce noise
    corner_gray = cv2.GaussianBlur(corner_gray, (3, 3), 0)
    template_gray = cv2.GaussianBlur(template_gray, (3, 3), 0)

    # Initialize feature detector with optimized parameters for fiducial marks
    if feature_type == 'SIFT':
        detector = cv2.SIFT_create(nfeatures=1000, contrastThreshold=0.02, edgeThreshold=20, sigma=1.6)
        norm_type = cv2.NORM_L2
    elif feature_type == 'ORB':
        detector = cv2.ORB_create(nfeatures=3000, scaleFactor=1.1, WTA_K=3, edgeThreshold=10, patchSize=31)
        norm_type = cv2.NORM_HAMMING
    else:  # AKAZE
        detector = cv2.AKAZE_create(threshold=0.0003, diffusivity=cv2.KAZE_DIFF_PM_G2)
        norm_type = cv2.NORM_HAMMING

    # Find keypoints and descriptors
    kp1, des1 = detector.detectAndCompute(template_gray, None)
    kp2, des2 = detector.detectAndCompute(corner_gray, None)

    # Debug keypoints
    print(f"      {feature_type}: Found {len(kp1)} keypoints in template, {len(kp2)} in corner image")

    # If not enough keypoints, return failure
    if len(kp1) < 4 or len(kp2) < 4 or des1 is None or des2 is None:
        print(f"      {feature_type}: Not enough keypoints found")
        return None, None, 0.0

    # Match features with more relaxed criteria for historical imagery
    good_matches = []
    try:
        matcher = cv2.BFMatcher(norm_type)
        matches = matcher.knnMatch(des1, des2, k=2)

        # Apply less strict ratio test for historical imagery
        for m, n in matches:
            if m.distance < 0.85 * n.distance:  # More permissive ratio for historical images
                good_matches.append(m)
    except Exception as e:
        print(f"      {feature_type}: Matching failed: {str(e)}")
        # Fallback to basic matching
        matcher = cv2.BFMatcher(norm_type, crossCheck=True)
        matches = matcher.match(des1, des2)
        # Take top 20 matches
        good_matches = sorted(matches, key=lambda x: x.distance)[:20]

    print(f"      {feature_type}: Found {len(good_matches)} good matches")

    # For fiducial marks, we can work with fewer matches
    if len(good_matches) < 4:
        print(f"      {feature_type}: Not enough good matches")
        return None, None, 0.0

    # Extract location of good matches
    src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

    # First try with more relaxed RANSAC parameters for historical imagery
    try:
        M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 10.0)  # Higher ransac threshold

        if M is None:
            print(f"      {feature_type}: Homography failed")
            return None, None, 0.0

        # Calculate inlier ratio
        inliers = np.sum(mask)
        inlier_ratio = inliers / len(good_matches)
        print(f"      {feature_type}: Inlier ratio: {inlier_ratio:.2f} ({inliers}/{len(good_matches)})")

        # For fiducial marks in historical imagery, accept lower inlier ratio
        if inlier_ratio < 0.3:  # Lower threshold for historical imagery
            print(f"      {feature_type}: Inlier ratio too low")
            return None, None, 0.0

        # Get center of template
        center_template = np.float32([[w_template/2, h_template/2]]).reshape(-1, 1, 2)

        # Transform center to find location in corner image
        center_corner = cv2.perspectiveTransform(center_template, M)
        x, y = center_corner[0][0][0], center_corner[0][0][1]

        # Basic validation - must be within image bounds with margin
        margin = 10
        if (x < margin or y < margin or
            x > w_corner - margin or y > h_corner - margin):
            print(f"      {feature_type}: Center point outside valid area")
            return None, None, 0.0

        # Calculate confidence based on inlier ratio
        confidence = inlier_ratio
        print(f"      {feature_type}: Success! Center at ({x:.1f}, {y:.1f}), confidence: {confidence:.2f}")

        # Create debug visualization if in debug mode
        if DebugMode:
            # Create a debug folder
            debug_folder = os.path.join(corner_folder, '_debug')
            os.makedirs(debug_folder, exist_ok=True)

            # Create visualization of matches
            matches_mask = mask.ravel().tolist()
            match_img = cv2.drawMatches(template_gray, kp1, corner_gray, kp2, good_matches, None,
                                       matchesMask=matches_mask, flags=2)

            # Draw center point on result image
            result = corner_image.copy()
            cv2.circle(result, (int(x), int(y)), 5, (0, 0, 255), -1)

            # Save debug images
            debug_name = f"{corner}_{feature_type}_{confidence:.2f}"
            cv2.imwrite(os.path.join(debug_folder, f"{debug_name}_matches.jpg"), match_img)
            cv2.imwrite(os.path.join(debug_folder, f"{debug_name}_result.jpg"), result)

        return x, y, confidence

    except Exception as e:
        print(f"      {feature_type}: Error during homography: {str(e)}")
        return None, None, 0.0

def visualize_feature_matching(corner_image, template_image, x, y, confidence, good_matches, kp1, kp2, save_path):
    """
    Create visualization of feature matching results for debugging
    """
    # Create matching visualization
    match_img = cv2.drawMatches(template_image, kp1, corner_image, kp2, good_matches, None,
                               flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)

    # Draw detected center
    result_img = corner_image.copy()
    cv2.circle(result_img, (int(x), int(y)), 5, (0, 0, 255), -1)

    # Create figure with subplots
    fig, axs = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle(f"Feature Matching (Confidence: {confidence:.2f})", fontweight="bold")

    axs[0].imshow(cv2.cvtColor(template_image, cv2.COLOR_BGR2RGB))
    axs[0].set_title('Template')

    axs[1].imshow(cv2.cvtColor(match_img, cv2.COLOR_BGR2RGB))
    axs[1].set_title('Matches')

    axs[2].imshow(cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB))
    axs[2].set_title('Detected Center')
    axs[2].plot(x, y, 'r+', markersize=15)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()

def systeme(a1, b1, c1, a2, b2, c2):
    """ 
    find the coordinate of the intersection point of 2 lines
    inputs:  parameters of equation
        a1*x + b1*y =c1
        a2*x + b2*y =c2'

    :param a1: parameter of the equation (line 1)
    :type a1: float
    :param b1: parameter of the equation (line 1)
    :type b1: float
    :param c1: result of the equation (line 1)
    :type c1: float
    :param a2: parameter of the equation (line 2)
    :type a2: float
    :param b2: parameter of the equation (line 2)
    :type b2: float
    :param c2: result of the equation (line 2)
    :type c2: float

    :results: result approximation
    :rtype: float

     """
    x = float()
    y = float()

    if a1*b2-a2*b1 == 0:
        print('Pas de solution')
        
    else:
        y = (c2*a1-c1*a2)/(a1*b2-a2*b1)
        x = (c1-b1*y)/a1
        # print('x =', round(x, 0), "", 'y =', round(y, 0))
    return x, y


def select_fiducial_corners(img, S, p, Fidu_type, black_stripe_location):
    """ 
    Crop image to select area where are the fiducials

    :param img: aerial photo
    :type img: cv2 img
    :param S: max size of the black border of the picture
    :type S: int
    :param p: percentage of bandwidth width compare to the half size of the photo
    :type p: float
    :param Fidu_type: fiducial type (ex target)
    :type Fidu_type: str
    :param black_stripe_location: (top, left, right, bot)
    :type black_stripe_location: [str]

    :returns:
        - F :if Fidu-type == target or cross: atrributes top_left, top_right, bot_left, bot_right
                    if Fidu-type == rectangle : atrributes top, bot, right, left
            ex : 
                F['top']=  [img, coord_u0, coord_v0 int  ]
    :rtype: dic                           
    """
    F = {}
    U = img.shape[1]  # hori
    V = img.shape[0]  # verti

    def crop(v0, u0):
        corner = img[v0:v0 + S, u0:u0 + S]
        if corner.ndim == 2:  # grayscale image: 3 channels expected by the detection (as cv2.imread default)
            corner = cv2.cvtColor(corner, cv2.COLOR_GRAY2BGR)
        return corner

    if Fidu_type == "target" or Fidu_type == "cross":
        
        # by default corner size
        u_left = 0
        u_right = U - S
        v_top = 0
        v_bot = V - S
        
        # Update for black strip:
        if 'top' in black_stripe_location:
            v_top = v_top + int(p*V)
            
        if 'bottom' in black_stripe_location:
            v_bot = v_bot - int(p*V)
            
        if 'left' in black_stripe_location:
            u_left = u_left + int(p*U)
            
        if 'right' in black_stripe_location:
            u_right = u_right - int(p*U)

        F['top_left'] = [crop(v_top, u_left), v_top, u_left]
        F['top_right'] = [crop(v_top, u_right), v_top, u_right]
        F['bot_right'] = [crop(v_bot, u_right), v_bot, u_right]
        F['bot_left'] = [crop(v_bot, u_left), v_bot, u_left]
        
    else:
        print("type of fiducial not defined: please complete the code")
        
    return F


def FiducialFig(F, fidu_coordinates, corner_folder):
    """
    Create a figure with the 4 corners per image, with a red rectangle showing the outline of the template position
    and a point at the fiducial coordinates

    :param F:
    :param fidu_coordinates:
    :return:
    """
    DPI = 200

    fidu_coordinates2 = fidu_coordinates.set_index('corner')

    # Create a figure
    fig, axs = plt.subplots(2, 2, figsize=(12, 12))
    fig.suptitle(fidu_coordinates['image'][0] + "\n", fontweight="bold")
    x = 0
    y = 0
    
    # for corner in fidu_coordinates['corner']:
    for corner in ['top_left', 'top_right',  'bot_left', 'bot_right']:

        axs[y, x].imshow(F[corner][0], cmap=plt.cm.gray)
        axs[y, x].set_title(corner)

        # Add a rectangle with location of template
        template_rectangle = patches.Rectangle((fidu_coordinates2.loc[corner]['u1'] - int(F[corner][2] + fidu_coordinates2.loc[corner]['xc']),
                                                fidu_coordinates2.loc[corner]['v1'] - int(F[corner][1]) - fidu_coordinates2.loc[corner]['yc']),
                                               fidu_coordinates2.loc[corner]['xc'] *2, fidu_coordinates2.loc[corner]['yc']*2,
                                               linewidth=2, edgecolor='r', facecolor='none')
        axs[y, x].add_patch(template_rectangle)  # Add the patch to the Axes

        # Add a circle at the found fiducial coordinates
        axs[y, x].plot(fidu_coordinates2.loc[corner]['u1'] - int(F[corner][2]),
                       fidu_coordinates2.loc[corner]['v1'] - int(F[corner][1]),
                       color='r', marker="+", markersize=12, markeredgewidth=0.8)

        x = x + 1
        if x == 2:
            x = 0
            y = 1

    fig.tight_layout()
    
    # save figure
    save_folder_path = corner_folder + '/_all_fiducials'
    Path(save_folder_path).mkdir(parents=True,exist_ok=True)  # create folder if does no exist
    plt.savefig(f"{save_folder_path}/_FiducialsDetection_{fidu_coordinates['image'][0]}.png",
                dpi=DPI)
    plt.close()

CORNER_NAMES = ['top_left', 'top_right', 'bot_right', 'bot_left']
_template_cache = {}


def load_corner_templates(fiducial_template_folder, center_fidu_tempate_CSV):
    """All the corner templates of a folder: {corner: [dict(name, img, xc, yc, src_w), ...]}.

    Center_Fiducials.txt: one line per template, 'name xc yc [source_width source_height]' (the size of the
    image the template was cut from is recorded by the template creator since October 2026; None if unknown).
    The templates are kept in memory (per process) as long as the file is not modified.
    """
    try:
        from GAPPS_tools.GAPPS_Tool_02e_FM_Review import template_key
    except ImportError:
        from GAPPS_Tool_02e_FM_Review import template_key
    key = (fiducial_template_folder, os.path.getmtime(center_fidu_tempate_CSV)
           if os.path.isfile(center_fidu_tempate_CSV) else 0)
    if key in _template_cache:
        return _template_cache[key]
    centres = {}
    if os.path.isfile(center_fidu_tempate_CSV):
        for line in open(center_fidu_tempate_CSV):
            parts = line.split()
            if len(parts) >= 3:
                src_w = int(float(parts[3])) if len(parts) >= 5 else None
                centres[parts[0]] = (int(parts[1]), int(parts[2]), src_w)
    templates = {c: [] for c in CORNER_NAMES}
    for f in sorted(os.listdir(fiducial_template_folder)):
        name, ext = os.path.splitext(f)
        corner = template_key(f)
        if ext.lower() not in ('.tif', '.tiff') or corner not in templates:
            continue
        if name not in centres:
            print(f"! No centre for template {f} in Center_Fiducials.txt: template not used")
            continue
        t = cv2.imdecode(np.fromfile(os.path.join(fiducial_template_folder, f), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if t is None:
            continue
        xc, yc, src_w = centres[name]
        templates[corner].append({'name': name, 'img': t, 'xc': xc, 'yc': yc, 'src_w': src_w,
                                  'cross': template_cross(t, xc, yc)})
    # Cross not found in a template (faint lines): directions of the crosses of the other templates
    found = [t['cross'] for ts in templates.values() for t in ts if t['cross'] is not None]
    if found:
        for ts in templates.values():
            for t in ts:
                if t['cross'] is None:
                    t['cross'] = found[0]
    _template_cache.clear()
    _template_cache[key] = templates
    return templates


def template_scale(src_w, image_width, ref_width):
    """Scale factor to apply to a template for an image: ratio of the image width to the width of the image the
    template was cut from (recorded, or else assumed to be the typical width of the folder). 1 if within 6 %
    (same scan resolution)."""
    w0 = src_w or ref_width
    if not w0:
        return 1.0
    s = image_width / float(w0)
    return 1.0 if abs(s - 1) < 0.06 else s


def match_one(window, template, xc, yc, scale=1.0):
    """Match one template in a corner window (both 8-bit grayscale), coarse to fine.

    The match is first searched at half resolution, then refined at full resolution around the best position.
    :return: (u, v) FM centre in the window, matching score (normalized cross-correlation), template centre (scaled)
    """
    if scale != 1.0:
        template = cv2.resize(template, None, fx=scale, fy=scale,
                              interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    th, tw = template.shape[:2]
    H, W = window.shape[:2]
    if th > H or tw > W:
        return (0, 0), -1.0, (xc * scale, yc * scale)
    f = 0.5 if min(th, tw) >= 160 else 1.0
    if f < 1:
        wc = cv2.resize(window, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        tc = cv2.resize(template, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        _, _, _, (xq, yq) = cv2.minMaxLoc(cv2.matchTemplate(wc, tc, cv2.TM_CCOEFF_NORMED))
        m = 6
        x0, y0 = max(int(xq / f) - m, 0), max(int(yq / f) - m, 0)
        x1, y1 = min(int(xq / f) + m + tw, W), min(int(yq / f) + m + th, H)
        _, score, _, (xr, yr) = cv2.minMaxLoc(cv2.matchTemplate(window[y0:y1, x0:x1], template, cv2.TM_CCOEFF_NORMED))
        x, y = x0 + xr, y0 + yr
    else:
        _, score, _, (x, y) = cv2.minMaxLoc(cv2.matchTemplate(window, template, cv2.TM_CCOEFF_NORMED))
    return (x + xc * scale, y + yc * scale), float(score), (xc * scale, yc * scale)


def _dark_lines(a, k):
    """Thin dark lines of an 8-bit image (black top-hat: broad shapes, edges and illumination are removed)."""
    se = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    return cv2.morphologyEx(a, cv2.MORPH_BLACKHAT, se)


def _hough_lines(a, k, min_votes):
    """Straight thin dark lines (rho, theta) of an image, strongest first."""
    L = _dark_lines(a, k).astype(np.float32)
    thr = max(L.mean() + 3 * L.std(), np.percentile(L, 97))
    B = cv2.morphologyEx((L > thr).astype(np.uint8) * 255, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    lines = cv2.HoughLines(B, 1, np.pi / 360, max(10, int(min_votes)))
    return [] if lines is None else [(float(r), float(t)) for r, t in lines[:, 0]]


def _angle_diff(t1, t2):
    """Difference between two line directions (rad, 0 - pi/2)."""
    return abs(((t1 - t2 + np.pi / 2) % np.pi) - np.pi / 2)


def _cross_point(lines, min_angle=np.deg2rad(30)):
    """Intersection of the strongest line and the strongest line crossing it, or None."""
    if not lines:
        return None
    r1, t1 = lines[0]
    for r2, t2 in lines[1:]:
        if _angle_diff(t1, t2) > min_angle:
            A = np.array([[np.cos(t1), np.sin(t1)], [np.cos(t2), np.sin(t2)]])
            x, y = np.linalg.solve(A, np.array([r1, r2]))
            return x, y, (t1, t2)
    return None


def template_cross(template, xc, yc):
    """Directions of the two lines of a cross-shaped FM (e.g. the X of Wild cameras) in a template, or None
    (no clear cross: other kind of mark). Only lines passing through the template centre are considered."""
    hw = min(xc, yc, template.shape[1] - xc, template.shape[0] - yc)
    r, k = int(0.6 * hw), max(7, int(0.06 * hw)) | 1
    sub = template[int(yc) - r:int(yc) + r, int(xc) - r:int(xc) + r]
    if sub.size == 0:
        return None
    lines = [(rho, t) for rho, t in _hough_lines(sub, k, 0.35 * r)
             if abs(r * np.cos(t) + r * np.sin(t) - rho) < 0.06 * hw]
    p = _cross_point(lines)
    return None if p is None else p[2]


def refine_on_cross(window, u, v, angles, hw, tol=np.deg2rad(8)):
    """FM centre at the intersection of the two lines of a cross, searched around (u, v).

    The bright disc and the dark frame around the cross do not always have the same position relative to the
    cross (different cameras, uneven illumination), so the template match can be off by tens of pixels: the
    centre of the mark is the intersection of its two lines (directions of the template +/- 8 deg).
    :return: (u, v) in the window, or None if the two lines are not found
    """
    r, k = int(0.75 * hw), max(7, int(0.06 * hw)) | 1
    x0, y0 = max(int(u) - r, 0), max(int(v) - r, 0)
    sub = window[y0:int(v) + r, x0:int(u) + r]
    if sub.size == 0:
        return None
    lines = [(rho, t) for rho, t in _hough_lines(sub, k, 0.4 * r)
             if min(_angle_diff(t, a) for a in angles) < tol]
    p = _cross_point(lines)
    if p is None:
        return None
    x, y = x0 + p[0], y0 + p[1]
    if np.hypot(x - u, y - v) > 0.6 * hw:
        return None
    return x, y


def match_corner(F_corner, templates, image_width, ref_width):
    """Best match of all the templates of one corner. F_corner: [window, v0, u0] (select_fiducial_corners).
    :return: dict(u1, v1 (image coordinates), maxVal, template, xc, yc)"""
    window, v0, u0 = F_corner
    if window.ndim == 3:
        window = cv2.cvtColor(window, cv2.COLOR_BGR2GRAY)
    best, best_t = {'maxVal': -1.0}, None
    for t in templates:
        scale = template_scale(t['src_w'], image_width, ref_width)
        (u, v), score, (xc, yc) = match_one(window, t['img'], t['xc'], t['yc'], scale)
        if score > best['maxVal']:
            best, best_t = {'u': u, 'v': v, 'maxVal': round(score, 4), 'scale': scale,
                            'template': t['name'] + ('' if scale == 1.0 else f' (x{scale:.2f})'), 'xc': xc, 'yc': yc}, t
    if best_t is not None:
        u, v = best['u'], best['v']
        # Cross-shaped marks: centre refined at the intersection of the two lines of the cross (the matching
        # score stays the one of the whole template)
        if best_t.get('cross') is not None:
            hw = min(best_t['xc'], best_t['yc']) * best['scale']
            c = refine_on_cross(window, u, v, best_t['cross'], hw)
            if c is not None:
                best['refined_by'] = float(np.hypot(c[0] - u, c[1] - v))
                best['template'] += ' +cross'
                u, v = c
        best['u1'], best['v1'] = int(round(u0 + u)), int(round(v0 + v))
    return best



# ------------------------------------------------------------------------------------------------------------
# Choice of the four FMs as a consistent frame (November 2026)
# ------------------------------------------------------------------------------------------------------------
# The best match of each corner taken alone can be a wrong mark when the templates do not fit the marks of a
# camera well (other camera in the same folder): image texture, or the extra discs of some cameras (counter,
# ringed disc), can then score higher than the true mark. Several candidates are therefore kept per corner,
# and the four FMs are chosen together: good matching scores AND a consistent frame (parallelogram with equal
# diagonals, of the same size as the other images of the roll), preferably all from the same template set.
N_CANDIDATES = 5      # candidates kept per corner
PEAKS_PER_TEMPLATE = 3
GEOM_WEIGHT = 0.10    # matching score lost per 1 % of the image width of frame error
SET_PENALTY = 0.02    # matching score lost per additional template set used for the four FMs of an image
FRAME_TOL = 60.0      # closure error (pix) above which the four FMs of an image are listed for the review
FRAME_TOL_REL = 0.005 # ... or this fraction of the image width, if larger


def template_set(name, corner):
    """Template set of a template: 'Template_B1600_top_left_1' -> 'Template_B1600'."""
    i = name.rfind('_' + corner)
    return name[:i] if i > 0 else name


def match_peaks(window, template, xc, yc, scale=1.0, k=PEAKS_PER_TEMPLATE):
    """As match_one, but the k best separated positions of the template in the window.
    :return: [((u, v) FM centre in the window, score), ...] best first, template centre (scaled)"""
    if scale != 1.0:
        template = cv2.resize(template, None, fx=scale, fy=scale,
                              interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    th, tw = template.shape[:2]
    H, W = window.shape[:2]
    c = (xc * scale, yc * scale)
    if th > H or tw > W:
        return [], c
    f = 0.5 if min(th, tw) >= 160 else 1.0
    if f < 1:
        wc = cv2.resize(window, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        tc = cv2.resize(template, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    else:
        wc, tc = window, template
    R = cv2.matchTemplate(wc, tc, cv2.TM_CCOEFF_NORMED)
    R = np.nan_to_num(R, nan=-1.0)
    r = max(3, int(0.5 * min(tc.shape[:2])))  # peaks closer than half a template: same mark
    out = []
    for _ in range(k):
        _, s, _, (xq, yq) = cv2.minMaxLoc(R)
        if s <= -0.99:
            break
        R[max(yq - r, 0):yq + r + 1, max(xq - r, 0):xq + r + 1] = -1.0
        if f < 1:  # refined at full resolution around the coarse position
            m = 6
            x0, y0 = max(int(xq / f) - m, 0), max(int(yq / f) - m, 0)
            x1, y1 = min(int(xq / f) + m + tw, W), min(int(yq / f) + m + th, H)
            sub = window[y0:y1, x0:x1]
            if sub.shape[0] < th or sub.shape[1] < tw:
                continue
            _, s, _, (xr, yr) = cv2.minMaxLoc(cv2.matchTemplate(sub, template, cv2.TM_CCOEFF_NORMED))
            x, y = x0 + xr, y0 + yr
        else:
            x, y = xq, yq
        out.append(((x + c[0], y + c[1]), float(s)))
    return out, c


def _dedupe(cands, n):
    """Candidates sorted by score, without the ones closer than half a template to a better one."""
    kept = []
    for cd in sorted(cands, key=lambda d: -d['maxVal']):
        if all(np.hypot(cd['u1'] - k['u1'], cd['v1'] - k['v1']) > cd['hw'] for k in kept):
            kept.append(cd)
        if len(kept) >= n:
            break
    return kept


def match_corner_candidates(F_corner, templates, corner, image_width, ref_width, n=N_CANDIDATES):
    """The n best (separated) positions of all the templates of one corner. F_corner: [window, v0, u0].
    :return: [dict(u1, v1 (image coordinates), maxVal, template, set, xc, yc, hw), ...] best first"""
    window, v0, u0 = F_corner
    if window.ndim == 3:
        window = cv2.cvtColor(window, cv2.COLOR_BGR2GRAY)
    cands = []
    for t in templates:
        scale = template_scale(t['src_w'], image_width, ref_width)
        peaks, (xc, yc) = match_peaks(window, t['img'], t['xc'], t['yc'], scale)
        hw = min(t['xc'], t['yc']) * scale
        for (u, v), score in peaks:
            cands.append({'u': u, 'v': v, 'u1': u0 + u, 'v1': v0 + v, 'maxVal': round(score, 4),
                          'template': t['name'] + ('' if scale == 1.0 else f' (x{scale:.2f})'),
                          'set': template_set(t['name'], corner), 'xc': xc, 'yc': yc, 'hw': hw,
                          'cross': t.get('cross')})
    cands = _dedupe(cands, n)
    for cd in cands:
        # Cross-shaped marks: centre refined at the intersection of the two lines of the cross
        if cd['cross'] is not None:
            c = refine_on_cross(window, cd['u'], cd['v'], cd['cross'], cd['hw'])
            if c is not None:
                cd['refined_by'] = float(np.hypot(c[0] - cd['u'], c[1] - cd['v']))
                cd['template'] += ' +cross'
                cd['u1'], cd['v1'] = u0 + c[0], v0 + c[1]
        cd['u1'], cd['v1'] = int(round(cd['u1'])), int(round(cd['v1']))
    return cands


def frame_error(P, prior=None):
    """Frame error (pix) of four FMs P = [top_left, top_right, bot_right, bot_left] (complex x + iy):
    closure of the parallelogram + 0.5 x difference of the diagonals (+ 0.5 x difference with the usual
    width and height of the frame of the roll, if known). :return: (error, closure)"""
    tl, tr, br, bl = P
    closure = abs(tl + br - tr - bl)
    err = closure + 0.5 * abs(abs(br - tl) - abs(bl - tr))
    if prior is not None:
        w = 0.5 * (abs(tr - tl) + abs(br - bl))
        h = 0.5 * (abs(bl - tl) + abs(br - tr))
        err += 0.5 * (abs(w - prior[0]) + abs(h - prior[1]))
    return err, closure


def select_frame(cands, image_width, prior=None):
    """Four FMs (one candidate per corner) with the best matching scores AND a consistent frame.
    :param cands: {corner: [candidates]} for the four CORNER_NAMES
    :return: ({corner: candidate}, frame error (pix), closure (pix))"""
    import itertools
    best, best_obj = None, -np.inf
    for combo in itertools.product(*[cands[c] for c in CORNER_NAMES]):
        P = [cd['u1'] + 1j * cd['v1'] for cd in combo]
        err, closure = frame_error(P, prior)
        obj = (np.mean([cd['maxVal'] for cd in combo]) - GEOM_WEIGHT * 100 * err / image_width
               - SET_PENALTY * (len({cd['set'] for cd in combo}) - 1))
        if obj > best_obj:
            best_obj, best = obj, (dict(zip(CORNER_NAMES, combo)), err, closure)
    return best


def roll_frame_prior(Out_fiducialmarks_CSV, image_name, threshold=0.88, min_images=3, image_width=None):
    """Usual (median) width and height (pix) of the frame of the FMs of the images of the same roll
    (name prefix before the first '_') already in Out_fiducialmarks.csv with four good matching scores,
    or None (fewer than min_images such images, or a frame that does not fit an image of image_width:
    images of the roll scanned at another resolution)."""
    if not os.path.isfile(Out_fiducialmarks_CSV):
        return None
    try:
        df = pd.read_csv(Out_fiducialmarks_CSV)
        df.columns = [c.strip() for c in df.columns]
        name = os.path.splitext(image_name)[0]
        roll = name.split('_')[0]
        df = df[(df['name'].astype(str).str.split('_').str[0] == roll) & (df['name'].astype(str) != name)]
        acc = df[['top_left_accuracy', 'top_right_accuracy', 'bot_right_accuracy', 'bot_left_accuracy']]
        df = df[(acc.astype(float) >= threshold).all(axis=1)]
        if len(df) < min_images:
            return None
        P = [df[f'X{k}'].astype(float).values + 1j * df[f'Y{k}'].astype(float).values for k in range(1, 5)]
        w = 0.5 * (np.abs(P[1] - P[0]) + np.abs(P[2] - P[3]))
        h = 0.5 * (np.abs(P[3] - P[0]) + np.abs(P[2] - P[1]))
        w, h = float(np.median(w)), float(np.median(h))
        if image_width and not 0.6 * image_width < w < image_width:
            return None
        return w, h
    except Exception:
        return None


def typical_image_width(image_folder, imlist):
    """Median width of the images of a folder (read from the file headers)."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    widths = []
    for f in imlist:
        try:
            with Image.open(os.path.join(image_folder, f)) as im:
                widths.append(im.size[0])
        except Exception:
            pass
    return int(np.median(widths)) if widths else None


def Main(image_folder, image_name, S, p, Fiducial_type, black_stripe_location, type_fidu, dataset, fiducial_template_folder, corner_folder, Out_fiducialmarks_CSV, center_fidu_tempate_CSV, overwriting=False, write_outputs=True,
         ref_width=None):
    """Detect the four fiducial marks of one image.

    :param write_outputs: True: the results are written in Out_fiducialmarks.csv (and _TobeChecked.csv);
        False (parallel processing): they are only returned, and written by the main process
        (several processes writing the same CSV file at the same time can lose lines).
    :param ref_width: typical width (pix) of the images of the folder: templates without a recorded source
        image size are assumed to come from an image of this width (and are rescaled for larger or smaller scans)
    :return: dict with keys 'image', 'line' (row for Out_fiducialmarks.csv or None),
        'tobechecked' (DataFrame or None) and 'error' (None or a message)
    """
    result = {'image': image_name, 'line': None, 'tobechecked': None, 'error': None}

    MatchingValueThreshold = 0.88
    DPI = 150
    start = time.time()

    if Fiducial_type != 'rectangle' and Fiducial_type != 'target' and Fiducial_type != 'cross':
        print('Code not yet built for this fiducial type')
        sys.exit()

    already_processed = False

    # checking if not already in the Out_fiducialmarks_CSV
    if not overwriting and os.path.exists(Out_fiducialmarks_CSV):
        fidFile = pd.read_csv(Out_fiducialmarks_CSV)
        if image_name.split('.')[0] in fidFile['name'].values:
            already_processed = True
            print(f'Fiducial detection already done for {image_name}')

    # if not overwriting and os.path.exists(f'{corner_folder}/_all_fiducials//_FiducialsDetection_{image_name}.png'):
    #     print(f'Fiducial detection already done for {image_name}')

    if overwriting or already_processed is False:

        # -------------------------------------------------------------------------------------
        # 1.0. #select the area of the image where the fiducials are located (i.e., the corners)
        # -------------------------------------------------------------------------------------

        image_path = '{}/{}'.format(image_folder, image_name)
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)  # 8-bit, 1 channel (converted to BGR per corner)
        if img is None:
            size = os.path.getsize(image_path) if os.path.exists(image_path) else 0
            result['error'] = (f'unreadable image ({size} bytes): empty, truncated or corrupted file '
                               f'-> delete it and run Tool 1 again for this image')
            print(f'\033[91m !! {image_name}: {result["error"]}\033[0m')
            return result

        F = select_fiducial_corners(img, S, p, Fiducial_type, black_stripe_location)  # cropping image corner
        F_area = F.keys()

        Coord = {}
        ToBeChecked = pd.DataFrame(columns=['image', 'corner', 'x', 'y', 'maxVal','is Check'])
        fidu_coordinates = pd.DataFrame(columns=['image', 'corner', 'template', 'xc', 'yc', 'u1', 'v1', 'maxVal'])


        # Templates of all the template sets (the best match is kept), rescaled to the size of this image
        h_img, w_img = img.shape[:2]
        S_img = max(S, int(round(S * w_img / ref_width))) if ref_width else S  # window ~ proportional to the scan size
        if S_img != S:
            F = select_fiducial_corners(img, S_img, p, Fiducial_type, black_stripe_location)
        templates = load_corner_templates(fiducial_template_folder, center_fidu_tempate_CSV)

        # Candidates per corner (several positions of all the template sets), then the four FMs are chosen
        # together: good matching scores and a consistent frame (see select_frame)
        cands = {}
        for corner in F_area:
            if not templates.get(corner):
                print(f"Can't find any corresponding fiducial template for {corner} in {fiducial_template_folder}")
                continue
            cands[corner] = match_corner_candidates(F[corner], templates[corner], corner, w_img, ref_width)
        cands = {c: v for c, v in cands.items() if v}
        prior = roll_frame_prior(Out_fiducialmarks_CSV, image_name, MatchingValueThreshold, image_width=w_img)
        frame_tol = max(FRAME_TOL, FRAME_TOL_REL * w_img)
        chosen, err, closure = {}, None, None
        if len(cands) == 4:
            chosen, err, closure = select_frame(cands, w_img, prior)
            weak = [c for c, b in chosen.items() if b['maxVal'] < MatchingValueThreshold]
            if weak or closure > frame_tol:
                # Second try with larger search windows: the candidates of both windows are pooled
                print(f" \033[91m  !!   first try: " + ', '.join(f"{c} {np.round(chosen[c]['maxVal'], 2)}" for c in weak)
                      + (f"{', ' if weak else ''}frame closure {closure:.0f} pix" if closure > frame_tol else '')
                      + "\033[0m")
                F2 = select_fiducial_corners(img, S_img + 400, max(p - 0.02, 0), Fiducial_type, black_stripe_location)
                for corner in cands:
                    more = match_corner_candidates(F2[corner], templates[corner], corner, w_img, ref_width)
                    cands[corner] = _dedupe(cands[corner] + more, 2 * N_CANDIDATES)
                chosen, err, closure = select_frame(cands, w_img, prior)
        else:
            chosen = {c: v[0] for c, v in cands.items()}  # some corner without template: no frame check

        frame_bad = closure is not None and closure > frame_tol
        for corner, best in chosen.items():
            if best['maxVal'] < MatchingValueThreshold or frame_bad:
                # Listed for the manual review (Review FM detection tool: GAPPS_interface_FM_review.py)
                ToBeChecked = pd.concat([ToBeChecked, pd.DataFrame(
                    {'image': [image_name], 'corner': [corner], 'x': [best['u1']],
                     'y': [best['v1']], 'maxVal': [best['maxVal']]})], ignore_index=True)
            Coord[corner] = [best['u1'], best['v1']]
            fidu_coordinates = pd.concat([fidu_coordinates, pd.DataFrame(
                [{'image': image_name, 'corner': corner, 'template': best['template'], 'xc': best['xc'],
                  'yc': best['yc'], 'u1': best['u1'], 'v1': best['v1'], 'maxVal': best['maxVal']}])],
                ignore_index=True)
        if closure is not None:
            col = '91' if frame_bad else '92'
            print(f" \033[{col}m           frame closure {closure:.0f} pix (tolerance {frame_tol:.0f})"
                  f"{'' if prior is None else f', roll frame {prior[0]:.0f} x {prior[1]:.0f} pix'}"
                  f"{'  -> listed for the manual review' if frame_bad else ''}\033[0m")

        if len(Coord) == 4:
            print(f"   >> found acceptable solution for {image_name}  [in {round(time.time() - start, 1)} seconds]")
            for corner in Coord.keys():
                val = fidu_coordinates[fidu_coordinates['corner'] == corner]['maxVal'].values[0]
                tname = fidu_coordinates[fidu_coordinates['corner'] == corner]['template'].values[0]
                col = '91' if val < 0.85 else ('93' if val < 0.92 else '92')
                print(f" \033[{col}m           {corner} : {np.round(val, 2)} | {Coord[corner]}  ({tname})\033[0m")
            # Add to CSV file (or return the line, in parallel mode)
            if write_outputs:
                addLine(image_name, Coord, fidu_coordinates, Out_fiducialmarks_CSV)
            else:
                result['line'] = toCSV(image_name, Coord, fidu_coordinates)
            FiducialFig(F, fidu_coordinates, corner_folder)  # save a figure
        else:
            result['error'] = 'fiducial marks not found (no template for some corners?)'

        if not ToBeChecked.empty and not write_outputs:
            result['tobechecked'] = ToBeChecked
        elif not ToBeChecked.empty:
            # write to file
            if not os.path.isfile(Out_fiducialmarks_CSV[:-4] + '_TobeChecked.csv'):
                ToBeChecked.to_csv(Out_fiducialmarks_CSV[:-4] + '_TobeChecked.csv',
                                   mode='w', header=['image', 'corner', 'x', 'y', 'maxVal','is Check'])  # append to file

            else:  # else it exists so append without writing the header
                ToBeChecked.to_csv(Out_fiducialmarks_CSV[:-4] + '_TobeChecked.csv', mode='a', header=False)  # append to file
    return result


def recentre_on_cross(image_folder, fiducial_template_folder, keep_reviewed=True):
    """Re-centre the FMs of Out_fiducialmarks.csv on the intersection of their cross (cross-shaped marks).

    For results obtained before the cross refinement existed (October 2026), without running the detection
    again: each FM is moved to the intersection of the two lines of its cross, searched around its current
    position. The FMs reviewed manually (Out_fiducialmarks_review_log.csv) are kept as they are.
    A backup of Out_fiducialmarks.csv is made first. :return: number of FMs moved
    """
    try:
        from GAPPS_tools import GAPPS_Tool_02e_FM_Review as fmr
    except ImportError:
        import GAPPS_Tool_02e_FM_Review as fmr
    fm_csv = os.path.join(image_folder, fmr.FM_CSV)
    df = fmr.read_fm(fm_csv)
    templates = load_corner_templates(fiducial_template_folder,
                                      os.path.join(fiducial_template_folder, 'Center_Fiducials.txt'))
    angles = next((t['cross'] for ts in templates.values() for t in ts if t.get('cross') is not None), None)
    if angles is None:
        print(' > No cross found in the templates: nothing to do')
        return 0
    images = fmr.list_images(image_folder)
    ref_width = typical_image_width(image_folder, list(images.values()))
    reviewed = set()
    if keep_reviewed:
        log = fmr.read_review_log(image_folder)
        reviewed = set(zip(log['name'].astype(str), log['corner'].astype(str))) if len(log) else set()
    backup = fmr.backup_fm(fm_csv)
    print(f' > Backup: {backup}')
    moved = 0
    for i, (name, row) in enumerate(df.iterrows()):
        if name not in images:
            continue
        img = cv2.imread(os.path.join(image_folder, images[name]), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        # half width of the templates at the scale of this image
        hw = float(np.median([min(t['xc'], t['yc']) * template_scale(t['src_w'], img.shape[1], ref_width)
                              for ts in templates.values() for t in ts]))
        for k, corner in enumerate(CORNER_NAMES, start=1):
            if (name, corner) in reviewed:
                continue
            x, y = float(row[f'X{k}']), float(row[f'Y{k}'])
            c = refine_on_cross(img, x, y, angles, hw)
            if c is not None and np.hypot(c[0] - x, c[1] - y) >= 1:
                df.loc[name, f'X{k}'], df.loc[name, f'Y{k}'] = int(round(c[0])), int(round(c[1]))
                moved += 1
        print(f'   [{i + 1}/{len(df)}] {name}', flush=True)
    fmr.write_fm(fm_csv, df)
    print(f' > {moved} fiducial marks moved to the centre of their cross ({fm_csv})')
    return moved


def _safe_Main(*args, **kwargs):
    """Main, but an error on one image is returned instead of stopping the whole processing."""
    try:
        return Main(*args, **kwargs)
    except Exception as e:
        print(f'\033[91m !! {args[1]}: {type(e).__name__}: {e}\033[0m')
        return {'image': args[1], 'line': None, 'tobechecked': None, 'error': f'{type(e).__name__}: {e}'}


def write_parallel_results(results, Out_fiducialmarks_CSV):
    """Write the results returned by the parallel workers (only the main process writes the CSV files)."""
    lines = [r['line'] for r in results if r and r.get('line') is not None]
    if lines:
        f = pd.read_csv(Out_fiducialmarks_CSV)
        new = pd.concat(lines, ignore_index=True)
        new.columns = f.columns  # same column names and order as the existing file
        new = new[~new[f.columns[0]].isin(f[f.columns[0]])]
        pd.concat([f, new], ignore_index=True).to_csv(Out_fiducialmarks_CSV, mode='w', sep=",", index=False)
    checks = [r['tobechecked'] for r in results if r and r.get('tobechecked') is not None]
    if checks:
        tbc = Out_fiducialmarks_CSV[:-4] + '_TobeChecked.csv'
        pd.concat(checks, ignore_index=True).to_csv(tbc, mode='a', header=not os.path.isfile(tbc))



REDONE_TXT = 'Out_fiducialmarks_redone.txt'  # images re-detected automatically, with the templates used


def images_to_redo(image_folder, fiducial_template_folder):
    """Images already in Out_fiducialmarks.csv to detect again: a corner with a low matching score, or four
    FMs that do not form a consistent frame (geometry check). Images with a corner corrected manually
    (review log) are kept as they are, and so are the images already re-detected with the same templates
    (Out_fiducialmarks_redone.txt), so that a new run does not redo them again and again.
    :return: (list of image names without extension, key of the current templates)"""
    try:
        from GAPPS_tools import GAPPS_Tool_02e_FM_Review as fmr
    except ImportError:
        import GAPPS_Tool_02e_FM_Review as fmr
    centres = os.path.join(fiducial_template_folder, 'Center_Fiducials.txt')
    tkey = (f"{os.path.normcase(os.path.abspath(fiducial_template_folder))}|"
            f"{int(os.path.getmtime(centres)) if os.path.isfile(centres) else 0}")
    queue = fmr.build_review_queue(image_folder, include_missing=False, include_reviewed=True)
    names = sorted({it['name'] for it in queue})
    log = fmr.read_review_log(image_folder)
    reviewed = set(log['name'].astype(str)) if len(log) else set()
    done = set()
    path = os.path.join(image_folder, REDONE_TXT)
    if os.path.isfile(path):
        for line in open(path, encoding='utf-8'):
            parts = line.rstrip('\n').split('\t')
            if len(parts) == 2 and parts[1] == tkey:
                done.add(parts[0])
    return [n for n in names if n not in reviewed and n not in done], tkey


def forget_detections(image_folder, names, tkey):
    """Remove images from Out_fiducialmarks.csv and Out_fiducialmarks_TobeChecked.csv (after a backup), so
    that they are detected again, and record them in Out_fiducialmarks_redone.txt."""
    try:
        from GAPPS_tools import GAPPS_Tool_02e_FM_Review as fmr
    except ImportError:
        import GAPPS_Tool_02e_FM_Review as fmr
    names = set(names)
    fm_csv = os.path.join(image_folder, fmr.FM_CSV)
    backup = fmr.backup_fm(fm_csv)
    df = fmr.read_fm(fm_csv)
    fmr.write_fm(fm_csv, df[~df['name'].isin(names)])
    tbc = os.path.join(image_folder, fmr.TOBECHECKED_CSV)
    if os.path.isfile(tbc):
        t = pd.read_csv(tbc, index_col=0)
        t = t[~t['image'].astype(str).map(fmr.stem).isin(names)]
        t.reset_index(drop=True).to_csv(tbc)
    with open(os.path.join(image_folder, REDONE_TXT), 'a', encoding='utf-8') as f:
        for n in sorted(names):
            f.write(f'{n}\t{tkey}\n')
    return backup



def print_roll_summary(image_folder, good=0.90, flag_share=0.30, flag_median=0.88):
    """Table of the matching scores per roll (name prefix before the first '_') of Out_fiducialmarks.csv, and
    the rolls for which a template set made on one of their images would probably help.
    :return: DataFrame (one row per roll)"""
    try:
        from GAPPS_tools import GAPPS_Tool_02e_FM_Review as fmr
    except ImportError:
        import GAPPS_Tool_02e_FM_Review as fmr
    df = fmr.read_fm(os.path.join(image_folder, fmr.FM_CSV))
    if len(df) == 0:
        return pd.DataFrame()
    acc = df[fmr.ACC_COLUMNS].astype(float)
    geo = fmr.geometry_check(df, layout=fmr.read_layout(image_folder)) if len(df) >= 5 else pd.DataFrame()
    rolls = df['name'].astype(str).str.split('_').str[0]
    rows = []
    for roll in sorted(rolls.unique()):
        sel = (rolls == roll).values
        a = acc[sel].values.ravel()
        a = a[~np.isnan(a)]
        n_geo = int(geo.loc[df['name'][sel], 'suspect'].sum()) if len(geo) else 0
        rows.append({'roll': roll, 'images': int(sel.sum()),
                     'low': float(np.mean(a < good)) if a.size else np.nan,
                     'median': float(np.median(a)) if a.size else np.nan,
                     'p10': float(np.percentile(a, 10)) if a.size else np.nan,
                     'frame': n_geo})
    t = pd.DataFrame(rows)
    print(f'\n > Matching scores per roll:')
    print(f"   {'Roll':<10}{'Images':>7}{'Corners < ' + format(good, '.2f'):>18}{'Median score':>14}"
          f"{'10th pct':>10}{'Bad frames':>12}")
    for r in t.itertuples():
        bad = r.low > flag_share or r.median < flag_median
        col = '91' if bad else ('93' if r.low > 0.05 or r.frame else '92')
        print(f"\033[{col}m   {r.roll:<10}{r.images:>7}{r.low:>17.0%} {r.median:>13.2f}{r.p10:>10.2f}"
              f"{r.frame:>12}\033[0m")
    weak = t[(t['low'] > flag_share) | (t['median'] < flag_median)]
    if len(weak):
        print(f"\033[93m > The templates do not fit the fiducial marks of roll(s) {', '.join(weak['roll'])} well "
              f"(other camera?).\n   Make a template set on a clear image of each of these rolls (step 2.2 'Create the FM templates' "
              f"> 'Launch template creator'), save it in the template folder and run the detection again: the images with "
              f"low scores are then detected again with the new templates.\033[0m")
    return t


def autoFMdetection(image_folder, fiducial_template_folder, dataset, p, black_stripe_location, layout='corners',
                    redo_suspects=True):
    """Automatic detection of the fiducial marks of all images of a folder.

    :param layout: 'corners' (fiducial targets in the four corners) or 'midpoints' (notches in the middle
        of the four sides of the frame, detected with GAPPS_Tool_02f_SideNotchDetection)
    """
    try:
        from GAPPS_tools.GAPPS_Tool_02e_FM_Review import read_layout, write_layout, LAYOUT_LABELS
    except ImportError:
        from GAPPS_Tool_02e_FM_Review import read_layout, write_layout, LAYOUT_LABELS
    print(' ')
    print('=====================================================================')
    print('=         PYTHON SCRIPT FOR AUTOMATIC FIDUCIAL DETECTION            =')
    print('=  Version 2.0.1 (December 2021)  |  B. Smets/A. Dille (RMCA/VUB)   =')
    print('=====================================================================')
    print(' ')

    # image_folder= r'E:\PROCESSING\SCANS\Dossier_Mohamed\_PROCESSING\A_CanvasSized_Cropped\_second_processing'
    # fiducial_template_folder = r"E:\PROCESSING\SCANS\Dossier_Mohamed\_PROCESSING\Fiducial_templates_01"
    # dataset = 'test_01'
    # p = 0.04
    # black_stripe_location = ['bottom', 'right']  # should be included in 'top' 'left' 'right' 'bottom' or 'None'


    # List image files
    allfiles = os.listdir(image_folder)
    imlist = [filename for filename in allfiles if filename.lower().endswith(('.tif', '.tiff', '.TIF', '.TIFF', '.jpg', '.jpeg'))]

    print('\n-------------------------------'
          '\n-------------------------------\n'
          f' > found {str(len(imlist))} images to process in folder: {image_folder}'
          '\n-------------------------------'
          '\n-------------------------------\n')

    # Define output file
    Out_fiducialmarks_CSV = os.path.join(image_folder, 'Out_fiducialmarks.csv')
    if os.path.exists(Out_fiducialmarks_CSV) is False:
        with open(Out_fiducialmarks_CSV, 'w') as f:
            f.write(
                'name, X1, Y1, X2, Y2, X3, Y3, X4, Y4, top_left_accuracy, top_right_accuracy, bot_right_accuracy, bot_left_accuracy\n')
    else:
        n_done = len(pd.read_csv(Out_fiducialmarks_CSV))
        if n_done > 0 and read_layout(image_folder) != layout:
            print(f'\033[91m !! The fiducial marks of this folder were detected with the layout '
                  f'"{LAYOUT_LABELS[read_layout(image_folder)]}", not "{LAYOUT_LABELS[layout]}".\n'
                  f'    Select the same layout, or move Out_fiducialmarks.csv (and _TobeChecked.csv) away to '
                  f'start again.\033[0m')
            return
        print(' > Output file Out_fiducialmarks.csv already exists, will append to it.')
        print(f' >> {str(n_done)} images already processed.\n\n')
    write_layout(image_folder, layout)
    # Images already processed but with a low score or an inconsistent frame: detected again
    # (redo_suspects=False to keep all the existing detections)
    if redo_suspects and layout == 'corners' and os.path.isfile(Out_fiducialmarks_CSV):
        try:
            redo, tkey = images_to_redo(image_folder, fiducial_template_folder)
        except Exception as e:
            redo, tkey = [], None
            print(f' ! Could not list the images to detect again ({type(e).__name__}: {e})')
        if redo:
            backup = forget_detections(image_folder, redo, tkey)
            print(f'\033[93m > {len(redo)} image(s) with a low score or an inconsistent frame are detected again '
                  f'(backup of Out_fiducialmarks.csv: {os.path.basename(backup) if backup else "-"}).\n'
                  f'   Images corrected manually are kept; each image is redone only once per template set '
                  f'({REDONE_TXT}).\033[0m\n')
    print(f' > Fiducial mark layout: {LAYOUT_LABELS[layout]}\n')
    # Main
    # Parallel processing: each worker reads one image (~150 MB in memory); reading the images from the
    # disk is the bottleneck, so more than ~8 workers does not make it faster
    num_cores = max(1, min(8, multiprocessing.cpu_count() - 1))
    RunParallel = True
    S = 2500
    Fiducial_type = 'target'
    type_fidu = 'barycentre'
    overwriting = False
    # p=0.04
    # black_stripe_location = ['bottom', 'right']  # should be included in 'top' 'left' 'right' 'bottom' or 'None'
    # fiducial_template_folder = r'D:\PROCESSING\SCANS\SCANS_Kwamouth_Kutu_1955_1956\Fiducial_templates_01'
    # dataset = 'test_01'

    corner_folder = os.path.join(image_folder, 'corners')
    center_fidu_tempate_CSV = os.path.join(fiducial_template_folder, 'Center_Fiducials.txt')
    # Typical image width: templates without recorded source size are assumed to come from such an image, and
    # are rescaled for images scanned at another resolution (e.g. a folder mixing 1600 and 2400 dpi scans)
    ref_width = typical_image_width(image_folder, imlist) if layout != 'midpoints' else None
    if ref_width:
        print(f' > Typical image width: {ref_width} pix (templates are rescaled for images of another size)\n')

    if layout == 'midpoints':
        try:
            from GAPPS_tools.GAPPS_Tool_02f_SideNotchDetection import run_midpoints
        except ImportError:
            from GAPPS_Tool_02f_SideNotchDetection import run_midpoints
        results = run_midpoints(image_folder, imlist, fiducial_template_folder, corner_folder, Out_fiducialmarks_CSV,
                                center_fidu_tempate_CSV, overwriting, num_cores, RunParallel)
    elif RunParallel is True:
        # imlist = imlist[70:80]
        results = Parallel(n_jobs=num_cores, verbose=10)(delayed(_safe_Main)(image_folder, image_name, S, p, Fiducial_type, black_stripe_location,
                                                             type_fidu, dataset, fiducial_template_folder, corner_folder,
                                                             Out_fiducialmarks_CSV, center_fidu_tempate_CSV, overwriting,
                                                             write_outputs=False, ref_width=ref_width)
                                                         for image_name in imlist)
        write_parallel_results(results, Out_fiducialmarks_CSV)
        sleep(1)
    else:
        print(f'Parallel processing is disabled. Running in single core mode, one image at the time.\n')
        results = []
        for i, image_name in enumerate(imlist[:]):
            print('\n >>> Image [' + str(i+1) + '/' + str(len(imlist)) + ']: ' + image_name)
            results.append(_safe_Main(image_folder, image_name, S, p, Fiducial_type, black_stripe_location, type_fidu, dataset,
                                      fiducial_template_folder, corner_folder, Out_fiducialmarks_CSV, center_fidu_tempate_CSV, overwriting,
                                      ref_width=ref_width))

    # Images that could not be processed
    errors = [r for r in results if r and r.get('error')]
    if errors:
        print(f'\n\033[91m{len(errors)} image(s) could not be processed:\033[0m')
        with open(os.path.join(image_folder, '__FM_detection_errors.txt'), 'w') as f:
            for r in errors:
                print(f'\033[91m   {r["image"]}: {r["error"]}\033[0m')
                f.write(f'{r["image"]}: {r["error"]}\n')
        print(f'   (list saved in {os.path.join(image_folder, "__FM_detection_errors.txt")})')

    # Check of the detections: geometry of the four FMs (parallelogram) and low matching scores
    print('\n==============================')
    print('CHECKING THE FIDUCIAL MARKS')
    try:
        from GAPPS_tools.GAPPS_Tool_02e_FM_Review import print_geometry_summary, build_review_queue
    except ImportError:
        from GAPPS_Tool_02e_FM_Review import print_geometry_summary, build_review_queue
    print_geometry_summary(image_folder)
    if layout == 'corners':
        try:
            print_roll_summary(image_folder)
        except Exception as e:
            print(f' ! Could not summarise the scores per roll ({type(e).__name__}: {e})')
    to_review = build_review_queue(image_folder)
    if len(to_review) > 0:
        print(f'\033[93m > {len(to_review)} corner(s) to review: use "Review / correct FM detection" '
              f'(the four FMs of each image are also shown in corners/_all_fiducials)\033[0m')
    else:
        print(' > No corner to review')

    print('==============================')
    print(' FID MARK DETECTION COMPLETED ')
    print('==============================')
    return

if __name__ == "__main__":
    pass

# ------------------------------------------------------------------------------
# END OF FUNCTION SCRIPT
# ------------------------------------------------------------------------------


TEST= False
if TEST:
    # Check for outliers in Out_fiducialmarks.csv
    Out_fiducialmarks_CSV = r"E:\AIRPHOTOS\_PROCESSING\Kwamouth-Kutu_1955-1956\A_CanvasSized_Cropped\Out_fiducialmarks - Copy - Copy.csv"
    Out_fiducialmarks = pd.read_csv(Out_fiducialmarks_CSV)
    Out_fiducialmarks = Out_fiducialmarks.dropna(subset=['name'])

    # Function to detect outliers using IQR
    def detect_outliers(df, column):
        Q1 = df[column].quantile(0.25)
        Q3 = df[column].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 2 * IQR
        upper_bound = Q3 + 2 * IQR
        return df[(df[column] < lower_bound) | (df[column] > upper_bound)]


    # Check for outliers in each column except 'name'
    for col in Out_fiducialmarks.columns:
        if col != 'name':
            outliers = detect_outliers(Out_fiducialmarks, col)
            if not outliers.empty:
                print(f"Outliers detected in column {col}:")
                print(outliers)
    print(f'column names: {list(Out_fiducialmarks.drop(columns="name").columns)}')
    print(f'mean values : {list(round(Out_fiducialmarks.drop(columns="name").mean()))}')


    # Now copy the preview corners of the outliers for check
    Canvas_sized_folder = os.path.dirname(Out_fiducialmarks_CSV)
    corner_folder = rf"{Canvas_sized_folder}\corners"
    os.makedirs(f'{corner_folder}/_outliers', exist_ok=True)
    for i, name in enumerate(outliers['name']):
        print(f'Copying corner preview for {name} to outliers folder (corners/_outliers)')
        shutil.copy(f'{corner_folder}/_all_fiducials/_FiducialsDetection_{name}.tif.png', f'{corner_folder}//_outliers/{name}.png')

    print('Outliers preview copied to corners/_outliers folder')

    REMOVE = False
    if REMOVE:
        # Remove the outliers from the outlier_corners folder (if they are still there after check)
        folders = [f'{os.path.dirname(Canvas_sized_folder)}/A_CanvasSized',f'{os.path.dirname(Canvas_sized_folder)}/A_CanvasSized_Cropped']
        folders = [f'{os.path.dirname(Canvas_sized_folder)}/B_Reprojected',f'{os.path.dirname(Canvas_sized_folder)}/C_Resampled']

        outliers_left = [os.path.splitext(im)[0].split('_')[0] for im in os.listdir(f'{corner_folder}/_outliers') if im.endswith('.png')]
        for folder in folders:
            for i, name in enumerate(outliers_left):
                for file_name in os.listdir(folder):
                    if name in file_name:
                        print(f'Removing {file_name} from {folder}')
                        os.remove(f'{folder}/{file_name}')
        # Remove the outliers from the Out_fiducialmarks.csv
        Out_fiducialmarks = Out_fiducialmarks[~Out_fiducialmarks['name'].isin(outliers_left)]
        Out_fiducialmarks.to_csv(Out_fiducialmarks_CSV, index=False)
        print(f'{str(len(outliers_left))} outliers removed from {Out_fiducialmarks_CSV}')

    OUTLIERS_CHECK = False
    if OUTLIERS_CHECK:
        # Check the outliers left in the corners/_outliers folder
        corner_folder = rf"{Canvas_sized_folder}\corners"
        outliers_left = [os.path.splitext(im)[0] for im in os.listdir(f'{corner_folder}/_outliers') if im.endswith('.png')]
        Out_fiducialmarks_outliers = pd.read_csv(r"E:\AIRPHOTOS\_PROCESSING\Kwamouth-Kutu_1955-1956\A_CanvasSized_Cropped\Out_fiducialmarks - Copy - Copy_outliers.csv")
        cornerToCheck2_path = f'{Canvas_sized_folder}/cornerToCheck2'
        os.makedirs(cornerToCheck2_path, exist_ok=True)

        S = 3500
        p = 0.04
        Fiducial_type = 'target'
        black_stripe_location = ['bottom', 'right']

        for i, outlier_name in enumerate(outliers_left):
            print(f'Checking outlier {outlier_name} ({i+1}/{len(outliers_left)})')
            image_path = f'{Canvas_sized_folder}/{outlier_name}.tif'
            if os.path.exists(image_path):
                img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)  # 8-bit, 1 channel (converted to BGR per corner)
                F = select_fiducial_corners(img, S, p, Fiducial_type, black_stripe_location)  # cropping image corner
                for corner in ['top_left', 'top_right', 'bot_left', 'bot_right']:
                    # corner_coord = pd.read_csv(
                    #     f'{corner_folder}/_all_fiducials/_FiducialsDetection_{outlier_name}.tif.csv')

                    # saving corner

                    cornerName = '{}_{}.png'.format(outlier_name, corner)
                    path = os.path.join(cornerToCheck2_path, cornerName)
                    cv2.imwrite(path, F[corner][0])

                    # save figure

                    # create folder if does no exist
                    # Path(cornerToCheck2_path).mkdir(parents=True, exist_ok=True)
                    # plt.savefig(cornerToCheck2_path + '/_ToCheck_' + outlier_name + '_' + corner + '.png', dpi=150)
                    # plt.close()

                    # fidu_coordinates = pd.concat([fidu_coordinates, pd.DataFrame(
                    #     [{'image': outlier_name, 'corner': corner, 'template': template_name, 'xc': xc,
                    #       'yc': yc, 'u1': best['u1'], 'v1': best['v1'],
                    #       'maxVal': best['maxVal']}]
                    # )], ignore_index=True)
                    #
                    # FiducialFig(F, fidu_coordinates, corner_folder)  # save a figure


        outliers_left_inCorner = []

        cornerToCheckPath = f'{Canvas_sized_folder}/cornerToCheck'
        corners_image = [f for f in os.listdir(cornerToCheckPath) if f.endswith('.png')]
        # os.makedirs(cornerToCheckPath, exist_ok=True)
        for outlier_name in outliers_left:
            # Check if the outlier is in the cornerToCheck folder
            for corner in corners_image:
                if f'{outlier_name}' in corner:
                    print(f'{outlier_name} is in the cornerToCheck folder')
                    outliers_left_inCorner.append(outlier_name)
                else:
                    print(f'{outlier_name} is NOT in the cornerToCheck folder')
        # remove duplicates
        outliers_left_inCorner = list(dict.fromkeys(outliers_left_inCorner))
        if len(outliers_left_inCorner) != len(outliers_left):
            print(f'{len(outliers_left)-len(outliers_left_inCorner)} outliers left in the _outliers folder')


            # saving corner
            cornerName = '{}_{}.png'.format(outlier_name, cornerToCheckPath)
            path = os.path.join(cornerPath, cornerName)
            cv2.imwrite(path, F[corner][0])

            # save figure
            save_folder_path = corner_folder + '/_To_Be_Checked'

            # create folder if does no exist
            Path(save_folder_path).mkdir(parents=True, exist_ok=True)
            plt.savefig(save_folder_path + '/_ToCheck_' + image_name + '_' + corner + '.png', dpi=DPI)
            plt.close()

    ##############################################################################################
    # Check for outliers in corners/_outliers folder
    Canvas_sized_folder = r'E:\PROCESSING\SCANS\Dossier_Mohamed\_PROCESSING\A_CanvasSized_Cropped/_second_processing'
    outlier_folder = rf"{Canvas_sized_folder}\corners\_outliers"
    outliers_left = [os.path.splitext(im)[0] for im in os.listdir(f'{outlier_folder}') if im.endswith('.png')]
    # harmonize by renaming
    for outlier in outliers_left:
        if '_FiducialsDetection_' in outlier:
            print(f'Renaming {outlier} to {outlier.replace("_FiducialsDetection_", "").replace(".tif", "")}.png')
            try:
                os.rename(f'{outlier_folder}/{outlier}.png', f'{outlier_folder}/{outlier.replace("_FiducialsDetection_", "").replace(".tif", "")}.png')
            except:
                print(f'Error renaming {outlier}')

    # copy all those images for new processing with other fiducials
    os.makedirs(f'{Canvas_sized_folder}/_second_processing', exist_ok=True)
    outliers_left = [os.path.splitext(im)[0] for im in os.listdir(f'{outlier_folder}') if im.endswith('.png')]
    print(f'I found {len(outliers_left)} outliers left in the _outliers folder')

    for i, outlier in enumerate(outliers_left):
        print(f'Copying outlier {outlier} to _second_processing folder [{i+1}/{len(outliers_left)}]')
        shutil.copy(f'{Canvas_sized_folder}/{outlier}.tif', f'{Canvas_sized_folder}/_second_processing/{outlier}.tif')

    # keep only images that are in the outliers list
    allfiles = os.listdir(Canvas_sized_folder)
    imlist = [filename for filename in allfiles if filename.lower().endswith(('.tif', '.tiff', '.TIF', '.TIFF', '.jpg', '.jpeg'))]
    img_to_remove = [im for im in imlist if im.split('.')[0] not in outliers_left]
    for im in img_to_remove:
        print(f'Removing {im} from {Canvas_sized_folder}')
        os.remove(f'{Canvas_sized_folder}/{im}')


    ##############################################################################################
    # Remove duplicates in Out_fiducialmarks.csv
    Out_fiducialmarks_CSV = r"E:\PROCESSING\SCANS\Dossier_Mohamed\_PROCESSING\A_CanvasSized_Cropped\Out_fiducialmarks.csv"
    Out_fiducialmarks = pd.read_csv(Out_fiducialmarks_CSV)
    Out_fiducialmarks = Out_fiducialmarks.dropna(subset=['name'])
    print(f'Found {len(Out_fiducialmarks)} entries in {Out_fiducialmarks_CSV}')
    # keep the occurence which minimal accuracy in col _accuracy is the highest when there are duplicates
    accuracy_columns = [col for col in Out_fiducialmarks.columns if col.endswith('_accuracy')]
    Out_fiducialmarks['min_accuracy'] = Out_fiducialmarks[accuracy_columns].min(axis=1)
    Out_fiducialmarks = Out_fiducialmarks.loc[Out_fiducialmarks.groupby('name')['min_accuracy'].idxmax()]
    print(f'After removing duplicates, {len(Out_fiducialmarks)} entries left')
    Out_fiducialmarks.to_csv(Out_fiducialmarks_CSV, index=False)
    print(f'Updated {Out_fiducialmarks_CSV}')

    ##############################################################################################
    # Remove outliers from folders
    folder_list = [r"E:\PROCESSING\SCANS\Dossier_Mohamed\_PROCESSING\B_Reprojected",
                   r"E:\PROCESSING\SCANS\Dossier_Mohamed\_PROCESSING\C_Resampled"]
    outlier_folder = r"E:\PROCESSING\SCANS\Dossier_Mohamed\_PROCESSING\A_CanvasSized_Cropped\_second_processing"
    outliers_left = [os.path.splitext(im)[0] for im in os.listdir(f'{outlier_folder}') if im.endswith('.tif')]
    for folder in folder_list:
        allfiles = os.listdir(folder)
        imlist = [filename for filename in allfiles if filename.lower().endswith(('.tif', '.tiff', '.TIF', '.TIFF', '.jpg', '.png'))]
        for outlier in outliers_left:
            for im in imlist:
                if '_'.join(outlier.split('_')[:-1]) in im:
                    print(f'Removing {im} from {folder}')
                    os.remove(f'{folder}/{im}')

    # Remove outliers from Out_fiducialmarks.csv
    Out_fiducialmarks_CSV = r"E:\PROCESSING\SCANS\Dossier_Mohamed\_PROCESSING\A_CanvasSized_Cropped\Out_fiducialmarks.csv"
    Out_fiducialmarks = pd.read_csv(Out_fiducialmarks_CSV)
    Out_fiducialmarks = Out_fiducialmarks.dropna(subset=['name'])
    Out_fiducialmarks = Out_fiducialmarks[~Out_fiducialmarks['name'].isin(outliers_left)]
    Out_fiducialmarks.to_csv(Out_fiducialmarks_CSV, index=False)
    print(f'{str(len(outliers_left))} outliers removed from {Out_fiducialmarks_CSV}')


    ##############################################################################################