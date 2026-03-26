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

Last update: 2024-10-03
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

from GAPP_ORIGINAL_AutomaticFiducialDetection import MatchingValueThreshold

# so that no figures are showing up (note that it may pose problems when using Spyder (?))
matplotlib.use('Agg')

# Developer's setup (Do not modify)
# -----------------
DebugMode = False
OneTemplateMax = True



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

        # Create folder if does not exist
        Path(save_folder_path).mkdir(parents=True, exist_ok=True)
        plt.imsave(save_folder_path + "/file_%s.png" % (text), final_mask)

    elif type_fidu == "fixed":
        x = xc
        y = yc
        final_mask = copy.deepcopy(im_gray)
        final_mask = cv2.circle(
            final_mask, (int(round(x)), int(round(y))), 1, 255, -1)
        save_folder_path = corner_folder + '/' + corner + "/fixedCopie/"

        # Create folder if does not exist
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

        F['top_left'] = [img[v_top:v_top+S, u_left:u_left+S], v_top, u_left]
        F['top_right'] = [img[v_top:v_top+S, u_right:u_right+S], v_top, u_right]
        F['bot_right'] = [img[v_bot:v_bot+S, u_right:u_right+S], v_bot, u_right]
        F['bot_left'] = [img[v_bot:v_bot+S, u_left:u_left+S], v_bot, u_left]
        
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
                       5, color='r', marker=".", markersize=2)

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

def Main(image_folder, image_name, S, p, Fiducial_type, black_stripe_location, type_fidu, dataset, fiducial_template_folder, corner_folder, Out_fiducialmarks_CSV, center_fidu_tempate_CSV, overwriting=False):

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
        img = cv2.imread(image_path)

        F = select_fiducial_corners(img, S, p, Fiducial_type, black_stripe_location)  # cropping image corner
        F_area = F.keys()

        Coord = {}
        ToBeChecked = pd.DataFrame(columns=['image', 'corner', 'x', 'y', 'maxVal','is Check'])
        fidu_coordinates = pd.DataFrame(columns=['image', 'corner', 'template', 'xc', 'yc', 'u1', 'v1', 'maxVal'])


        for corner in F_area:
            # -------------------------------------------------------------------------------------
            # 1.1 Load fiducial template
            # -------------------------------------------------------------------------------------
            # create dic with fiducial template that match
            # template_list = [template for template in os.listdir(fiducial_template_folder) if template.endswith('.tif')]
            # template_list = [template for template in template_list if template.startswith(f'Template_{dataset}_{corner}')]
            template_list_all=[template for template in os.listdir(fiducial_template_folder) if template[-4:] in ['.tif'] ]
            template_list=[template for template in template_list_all if corner in template ]


            if len(template_list) == 0:
                print("Can't find any corresponding fiducial template")
                #sys.exit()

            else:
                template_dic = {}
                for template_name in template_list:
                    template_img = cv2.imread(fiducial_template_folder +
                                              '/' + template_name)
                    template_dic[template_name] = template_img

            # -------------------------------------------------------------------------------------
            # 1.2. select a smaller area where the fiducial should be and match it with the found fiducial templates
            # -------------------------------------------------------------------------------------
            center_fidu_tempate = open(center_fidu_tempate_CSV)
            Lcenter = center_fidu_tempate.readlines()
            best_template = pd.DataFrame(columns=['template', 'u1', 'v1', 'maxVal'])

            if OneTemplateMax is True:  # will only use the first matching template
                template_list = [template_list[0]]

            xc, yc = 0, 0
            for template_name in template_list:
                for line in Lcenter:
                    line = line.split(' ')
                    if template_name.split('.')[0] == line[0]:
                        # coordinates of the center of the fiducial template (pointed by hand)
                        xc, yc = (int(line[1]), int(line[2]))
                        # print(str(xc) + ' '+ str(yc))
                        break

                if xc != 0 and yc != 0:  # i.e., it found a template
                    try:
                        if Fiducial_type == 'target':
                            orient = 'False'
                            u, v, maxVal = CenterFiducial_LUCASKANADE(F[corner][0],
                                                                      Fiducial_type,
                                                                      orient,
                                                                      template_dic[template_name],
                                                                      xc,
                                                                      yc,
                                                                      image_name,
                                                                      corner,
                                                                      type_fidu,
                                                                      corner_folder)

                            u1 = int(F[corner][2]+u)  # colon
                            v1 = int(F[corner][1]+v)  # line
                            # Coord[corner]=[u1,v1] #line,colon

                            best_template = pd.concat([best_template, pd.DataFrame(
                                [{'template': template_name, 'u1': u1, 'v1': v1, 'maxVal': maxVal}])], ignore_index=True)

                            if template_name == template_list[-1]:
                                best = best_template.iloc[best_template['maxVal'].idxmax()]

                                if best['maxVal'] >= MatchingValueThreshold:
                                    Coord[corner] = [best['u1'],
                                                     best['v1']]  # line,colon
                                    fidu_coordinates = pd.concat([fidu_coordinates, pd.DataFrame(
                                        [{'image': image_name, 'corner': corner, 'template': template_name, 'xc': xc,
                                          'yc': yc, 'u1': best['u1'], 'v1': best['v1'], 'maxVal': best['maxVal']}])], ignore_index=True)

                                # Value could be increased to be more constraining on the quality of the match
                                elif best['maxVal'] < MatchingValueThreshold:
                                    print(f" \033[91m  !!   first try with {corner} gives {np.round(best['maxVal'], 2)}\033[0m")

                                    # Another try with larger corner area?
                                    S2 = S+400
                                    if p-0.02 >= 0:
                                        p2 = p-0.02
                                    else:
                                        p2 = 0

                                    F2 = select_fiducial_corners(img, S2, p2, Fiducial_type,black_stripe_location)  # cropping image corner
                                    u, v, maxVal = CenterFiducial_LUCASKANADE(F2[corner][0], Fiducial_type, orient,
                                                                              template_dic[template_name], xc, yc,
                                                                              image_name, corner, type_fidu, corner_folder)

                                    u1 = int(F[corner][2] + u)  # colon
                                    v1 = int(F[corner][1] + v)  # line
                                    best_template = pd.concat([best_template, pd.DataFrame(
                                        [{'template': template_name, 'u1': u1, 'v1': v1, 'maxVal': maxVal}]
                                    )], ignore_index=True)
                                    best = best_template.iloc[best_template['maxVal'].idxmax()]

                                    # second check: Value could be increased to be more constraining on the quality of the match
                                    if best['maxVal'] >= MatchingValueThreshold:
                                        Coord[corner] = [best['u1'], best['v1']]
                                        fidu_coordinates = pd.concat([fidu_coordinates, pd.DataFrame(
                                            [{'image': image_name, 'corner': corner, 'template': template_name, 'xc': xc,
                                              'yc': yc, 'u1': best['u1'], 'v1': best['v1'], 'maxVal': best['maxVal']}]
                                             )], ignore_index=True)

                                    else:
                                            ToBeChecked = pd.concat([ToBeChecked, pd.DataFrame(
                                                {'image': [image_name], 'corner': [corner], 'x': [best['u1']],
                                                 'y': [best['v1']], 'maxVal': [best['maxVal']]}
                                                 )], ignore_index=True)

                                            # Try with circle
                                            corner_monoband = [item[0]for item in F[corner][0][0]]
                                            detected_fiducial_circles = FindCircles(np.asarray(corner_monoband),
                                                                                    DP=1, MinDist=500,
                                                                                    MinRadius=xc - 50,
                                                                                    MaxRadius=xc + 50,
                                                                                    parameter2=120)

                                            # Create a fancy figure for the corner with problem
                                            fig, axs = plt.subplots(1, 2, figsize=(6, 4))
                                            fig.suptitle('to check: ' + image_name + '_' + corner, fontweight="bold")
                                            axs[0].imshow(F[corner][0], cmap=plt.cm.gray)
                                            axs[0].set_title('corner image')

                                            # Add a rectangle with location of template
                                            rect = patches.Rectangle((best['u1']-int(F[corner][2]-xc),best['v1']-int(F[corner][1])-yc),
                                                                     template_dic[template_name].shape[0],
                                                                     template_dic[template_name].shape[1],
                                                                     linewidth=2, edgecolor='r', facecolor='none')

                                            # Add the patch to the Axes
                                            axs[0].add_patch(rect)
                                            axs[1].imshow(template_dic[template_name], cmap=plt.cm.gray)
                                            axs[1].set_title('template')

                                            if detected_fiducial_circles is not None:
                                                Coord[corner] = [detected_fiducial_circles[0][0][0], detected_fiducial_circles[0][0][1]]
                                                fidu_coordinates = pd.concat([fidu_coordinates, pd.DataFrame(
                                                    [{'image': image_name, 'corner': corner, 'template': template_name,
                                                      'xc': xc,
                                                      'yc': yc, 'u1': detected_fiducial_circles[0][0][0],
                                                      'v1': detected_fiducial_circles[0][0][1],
                                                      'maxVal': 0}]
                                                    )], ignore_index=True)

                                                # add circle
                                                circle = plt.Circle((detected_fiducial_circles[0][0][0], detected_fiducial_circles[0][0][1]),
                                                                    (detected_fiducial_circles[0][0][2]), fill=False, color='r')
                                                axs[0].add_patch(circle)
                                                axs[0].plot(detected_fiducial_circles[0][0][0],
                                                            detected_fiducial_circles[0][0][1],
                                                            'r', marker=".",markersize=10)
                                                axs[0].add_patch(circle)

                                            else:
                                                Coord[corner] = [best['u1'], best['v1']]
                                                fidu_coordinates = pd.concat([fidu_coordinates, pd.DataFrame(
                                                    [{'image': image_name, 'corner': corner, 'template': template_name, 'xc': xc,
                                                      'yc': yc, 'u1': best['u1'], 'v1': best['v1'],
                                                      'maxVal': best['maxVal']}]
                                                     )], ignore_index=True)

                                            # saving corner
                                            cornerPath = '{}/cornerToCheck'.format(image_folder)
                                            Path(cornerPath).mkdir(parents=True, exist_ok=True)
                                            cornerName = '{}_{}.png'.format(image_name,corner)
                                            path = os.path.join(cornerPath,cornerName)
                                            cv2.imwrite(path,F[corner][0])

                                            # save figure
                                            save_folder_path = corner_folder + '/_To_Be_Checked'

                                            # create folder if does no exist
                                            Path(save_folder_path).mkdir(parents=True, exist_ok=True)
                                            plt.savefig(save_folder_path + '/_ToCheck_' + image_name + '_' + corner + '.png', dpi=DPI)
                                            plt.close()

                            if len(Coord) == 4 and template_name == template_list[-1] and corner == list(F.keys())[-1]:
                                # print("     --> " + image_name + ' > found for fiducial coordinates: ' + str(Coord))
                                print(f"   >> found acceptable solution for {image_name}  [in {round(time.time() - start, 1)} seconds]")
                                for corner in Coord.keys():
                                    val = fidu_coordinates[fidu_coordinates['corner'] == corner]['maxVal'].values[0]
                                    if val < 0.85:
                                        print(f" \033[91m           {corner} : {np.round(val, 2)} | {Coord[corner]}\033[0m")
                                    elif 0.85 <= val < 0.92:
                                        print(f" \033[93m           {corner} : {np.round(val, 2)} | {Coord[corner]}\033[0m")
                                    else:
                                        print(f" \033[92m           {corner} : {np.round(val, 2)} | {Coord[corner]}\033[0m")

                                # Add to CSV file
                                addLine(image_name, Coord,fidu_coordinates, Out_fiducialmarks_CSV)

                                fidu_coordinates = fidu_coordinates.dropna(subset=['image']) # temp solution, drop nan (!need to know why)
                                FiducialFig(F, fidu_coordinates, corner_folder)  # save a figure

                    except (ValueError, IndexError) as e:
                        print(e)
                        print('cannot find fidu ', image_name, '   ', corner)

                else:
                    print(
                        "! Could not find center coordinates for template | << check 'Center_Fiducial.csv' file >>")
                    print('Template_%s_%s' %(Fiducial_type, dataset) + " != " + line[0])



                fidu_coordinates = pd.concat([fidu_coordinates, pd.DataFrame(
                    [{'template': template_name, 'xc': 0, 'yc': 0, 'u': 0, 'v': 0}]
                    )], ignore_index=True)
                # sys.exit(0)

        if not ToBeChecked.empty:
            # write to file
            if not os.path.isfile(Out_fiducialmarks_CSV[:-4] + '_TobeChecked.csv'):
                ToBeChecked.to_csv(Out_fiducialmarks_CSV[:-4] + '_TobeChecked.csv',
                                   mode='w', header=['image', 'corner', 'x', 'y', 'maxVal','is Check'])  # append to file

            else:  # else it exists so append without writing the header
                ToBeChecked.to_csv(Out_fiducialmarks_CSV[:-4] + '_TobeChecked.csv', mode='a', header=False)  # append to file
    return

def autoFMdetection(image_folder, fiducial_template_folder, dataset, p, black_stripe_location):
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
        print(' > Output file Out_fiducialmarks.csv already exists, will append to it.')
        print(f' >> {str(len(pd.read_csv(Out_fiducialmarks_CSV)) - 1)} images already processed.\n\n')
    # Main
    num_cores = multiprocessing.cpu_count() - 1
    RunParallel = False  # Assuming parallel processing is desired
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

    if RunParallel is True:
        # imlist = imlist[70:80]
        Parallel(n_jobs=num_cores, verbose=30)(delayed(Main)(image_folder, image_name, S, p, Fiducial_type, black_stripe_location,
                                                             type_fidu, dataset, fiducial_template_folder, corner_folder,
                                                             Out_fiducialmarks_CSV, center_fidu_tempate_CSV,overwriting) for image_name in imlist)
        sleep(3)
    else:
        print(f'Parallel processing is disabled. Running in single core mode, one image at the time.\n')
        for i, image_name in enumerate(imlist[:]):
            print('\n >>> Image [' + str(i+1) + '/' + str(len(imlist)) + ']: ' + image_name)
            Main(image_folder, image_name, S, p, Fiducial_type, black_stripe_location, type_fidu, dataset,
                 fiducial_template_folder, corner_folder, Out_fiducialmarks_CSV, center_fidu_tempate_CSV, overwriting)

    # NEW: Check for outliers in Out_fiducialmarks.csv (works if cropped to photo frame)
    print('\n==============================')
    print('CHECKING FOR OUTLIERS IN FIDUCIAL MARKS')
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
    if not Out_fiducialmarks.empty:
        # Check for outliers in each column except 'name'
        for col in Out_fiducialmarks.columns:
            if col != 'name':
                outliers = detect_outliers(Out_fiducialmarks, col)
                if not outliers.empty:
                    print(f"Outliers detected in column {col}:")
                    print(outliers)
        if not outliers.empty:
            print(f'column names: {list(Out_fiducialmarks.drop(columns="name").columns)}')
            print(f'mean values : {list(round(Out_fiducialmarks.drop(columns="name").mean()))}')

            # Now copy the preview corners of the outliers for check
            Canvas_sized_folder = os.path.dirname(Out_fiducialmarks_CSV)
            corner_folder = rf"{Canvas_sized_folder}\corners"
            os.makedirs(f'{corner_folder}/_outliers', exist_ok=True)
            for i, name in enumerate(outliers['name']):
                print(f'Copying corner preview for {name} to outliers folder (corners/_outliers)')
                shutil.copy(f'{corner_folder}/_all_fiducials/_FiducialsDetection_{name}.tif.png',
                            f'{corner_folder}//_outliers/{name}.png')


            print('Outliers preview copied to corners/_outliers folder')

    # Print list of image corners to check (uncertainties in the template matching)
    if os.path.isfile('{}_TobeChecked.csv'.format(Out_fiducialmarks_CSV[:-4])):
        ToBeChecked_O2 = pd.read_csv('{}_TobeChecked.csv'.format(Out_fiducialmarks_CSV[:-4]))

    # if not ToBeChecked.empty:
    #     # write to file
    #     if not os.path.isfile(Out_fiducialmarks_CSV[:-4] + '_TobeChecked.csv'):
    #         ToBeChecked.to_csv(Out_fiducialmarks_CSV[:-4] + '_TobeChecked.csv',
    #                            mode='w', header=['image', 'corner', 'x', 'y', 'maxVal','is Check'])  # append to file
    #     else:  # else it exists so append without writing the header
    #         ToBeChecked.to_csv(Out_fiducialmarks_CSV[:-4] + '_TobeChecked.csv', mode='a', header=False)  # append to file

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
                img = cv2.imread(image_path)
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