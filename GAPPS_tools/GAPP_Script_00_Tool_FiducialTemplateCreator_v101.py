#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
------------------------------------------------------------------------------
PYTHON SCRIPT FOR CREATING FIDUCIAL TEMPLATES
------------------------------------------------------------------------------

Version: 1.0.1 (22/12/2021)
Author: Antoine Dille
        (Royal Museum for Central Africa )



This script aims at creating templates for the four fiducial (corners) of an aerial image for later automatic
detection of the fiducials on a large set of aerial images (see SCRIPT 02 - Automatic Fiducials Detection).
Simply provide the path of one image of the set with representative fiducial marks. Note that
SCRIPT 02 allows to test multiple templates.


AD December 2021

"""

import cv2
import os, csv
import matplotlib.pyplot as plt
from pathlib import Path


# ----------------------------------------------------------------------------
################################    SETUP     ################################
# ----------------------------------------------------------------------------
# input parameters
image4template_path=r"D:\PROCESSING\SCANS\Test_SCANS_GAPPS\5592-001.tif"
fiducialCenters={'top_left': [778, 916], 'top_right': [11069, 824], 'bot_right': [11114, 11278],'bot_left': [819, 11364]} #manual coordinates



halfwidth=500 #half width (in pixels) required to cover the entirety of the fiducial mark
output_template_folder=r':\Users\adille\Downloads/Fiducial_templates_01' # folder where the fiducial template will be saved
dataset='test_03' # image dataset name (e.g., 'Virunga_1958')
# Fiducial_type='target'

image4template_path=r"E:/PROCESSING/SCANS/Dossier_Mohamed/_PROCESSING/A_CanvasSized_Cropped/5589-016_Cropped.tif"
fiducialCenters={'top_left': [985, 963], 'top_right': [11288, 934], 'bot_right': [11226, 11418],'bot_left': [936, 11430]} #manual coordinates
halfwidth=500 #half width (in pixels) required to cover the entirety of the fiducial mark
output_template_folder=r'E:\PROCESSING\SCANS\Dossier_Mohamed\_PROCESSING\_FM_templates' # folder where the fiducial template will be saved
dataset='test_03' # image dataset name (e.g., 'Virunga_1958')

image4template_path=r"E:\PROCESSING\SCANS\Dossier_Mohamed\_PROCESSING\A_CanvasSized_Cropped\5557_015_Cropped.tif"
fiducialCenters={'top_left': [372, 7644], 'top_right': [7505, 483], 'bot_right': [14739, 7529],'bot_left': [7623, 14699]} #manual coordinates
halfwidth=500 #half width (in pixels) required to cover the entirety of the fiducial mark
output_template_folder=r'E:\PROCESSING\SCANS\Dossier_Mohamed\_PROCESSING\_FM_templates' # folder where the fiducial template will be saved
dataset='test_04' # image dataset name (e.g., 'Virunga_1958')

image4template_path = r"C:\Users\adille\Downloads\5666_164.tiff"
fiducialCenters={'top_left': [688, 954], 'top_right': [11198, 810], 'bot_right': [11226, 11141],'bot_left': [760, 11307]} #manual coordinates
halfwidth=500 #half width (in pixels) required to cover the entirety of the fiducial mark
output_template_folder=r'C:\Users\adille\Downloads/Fiducial_templates_01' # folder where the fiducial template will be saved
dataset='fidu_01' # image dataset name (e.g., 'Virunga_1958')

image4template_path = r"G:\PROCESSING\SCANS\Rwanda_1974_bukavu\Bande_12_13\PROCESSING\A_CanvasSized_Cropped\73_4_361_Cropped.tif"
fiducialCenters={'top_left': [878,1727], 'top_right': [14173,1770], 'bot_right': [14150,15233],'bot_left': [877,15203]} #manual coordinates
halfwidth=300 #half width (in pixels) required to cover the entirety of the fiducial mark
output_template_folder=r'G:\PROCESSING\SCANS\Rwanda_1974_bukavu\Bande_12_13\PROCESSING/fiducial_template' # folder where the fiducial template will be saved
dataset='fidu_01' # image dataset name (e.g., 'Virunga_1958')
# ----------------------------------------------------------------------------
################################ END OF SETUP ###############################
# ----------------------------------------------------------------------------

os.makedirs(output_template_folder, exist_ok=True)




img4template=cv2.imread(image4template_path, cv2.IMREAD_UNCHANGED)
corner_list=['top_left', 'top_right', 'bot_right','bot_left']

fiducialCenters_images={}
fiducialCenters_images['top_left'] = [img4template[fiducialCenters['top_left'][1]-halfwidth:fiducialCenters['top_left'][1]+halfwidth,
                                      fiducialCenters['top_left'][0]-halfwidth:fiducialCenters['top_left'][0]+halfwidth]][0]
fiducialCenters_images['top_right'] = [img4template[fiducialCenters['top_right'][1]-halfwidth:fiducialCenters['top_right'][1]+halfwidth,
                                      fiducialCenters['top_right'][0]-halfwidth:fiducialCenters['top_right'][0]+halfwidth]][0]
fiducialCenters_images['bot_right'] = [img4template[fiducialCenters['bot_right'][1]-halfwidth:fiducialCenters['bot_right'][1]+halfwidth,
                                      fiducialCenters['bot_right'][0]-halfwidth:fiducialCenters['bot_right'][0]+halfwidth]][0]
fiducialCenters_images['bot_left'] = [img4template[fiducialCenters['bot_left'][1]-halfwidth:fiducialCenters['bot_left'][1]+halfwidth,
                                      fiducialCenters['bot_left'][0]-halfwidth:fiducialCenters['bot_left'][0]+halfwidth]][0]


# Create a figure with the 4 fiducials
x = 0
y = 0
fig, axs = plt.subplots(2, 2, figsize=(6, 6))
for corner_image in corner_list:
    axs[x, y].imshow(fiducialCenters_images[corner_image], cmap=plt.cm.gray)
    axs[x, y].set_title(corner_image)
    x = x + 1
    if x == 2:
        x = 0;
        y = 1

# save templates as images
i=1
for corner_image in corner_list:
    template_name= 'Template_' + dataset + "_" + corner_image + '_' + str(i)+ '.tif'
    while os.path.exists(output_template_folder + "/" + template_name):
        i=i+1
        template_name = 'Template_' + dataset + "_" + corner_image + '_' + str(i) + '.tif'

    corner_image_name = output_template_folder + "/" + template_name
    cv2.imwrite(corner_image_name, fiducialCenters_images[corner_image])

# create an associated     txt file

f = open(output_template_folder + '/' + "Center_Fiducials.txt", "a",newline='')
w = csv.writer(f,delimiter=" ")
for corner_image in corner_list:
    template_name= 'Template_' + dataset + "_" + corner_image + '_' + str(i) #+ '.tif'
    line=[[template_name , str(halfwidth), str(halfwidth)]]
    w.writerows(line)
f.close()