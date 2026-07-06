"""
========================================================================================
                     GAPPS – GeoRiskA Airphoto Pre-Processing Suite
========================================================================================
                          = CREATE FM TEMPLATES FUNCTION =

Description: This script aims to create templates for the four fiducial marks
    (4 corners) of an aerial image for later automatic detection of the fiducial marks
    on a large set of aerial images.
    Simply provide the path of one image of the set with representative fiducial marks.
    Note that automatic FM detection allows to test multiple templates.

Copyright:
    RMCA — Royal Museum for Central Africa (Tervuren, BELGIUM)
        Natural Hazards and Cartography (GeoRiskA), Dpt. of Earth Sciences
    VUB — Vrije Universiteit Brussel (Brussels, BELGIUM)
        Cartography and GIS research group (CGIS), Dpt. of Geography
    © 2021 – 2024

Software management and coordination:
    - Benoît SMETS (RMCA / VUB)

Software authorship:
    - Antoine Dille (RMCA)
    - Benoît SMETS (RMCA / VUB)

The script was developed on Windows 10 and MacOS ≥ 14.6.

Last update: 2024-10-02
========================================================================================
"""

import cv2
import os
import csv
import matplotlib.pyplot as plt

def fiducialTemplateCreator(image4template_path,output_template_folder, fiducialCenters, halfwidth=240, dataset='WRC10'):
    print(fiducialCenters)

    img4template = cv2.imread(image4template_path, cv2.IMREAD_UNCHANGED)
    corner_list = ['top_left', 'top_right', 'bot_right', 'bot_left']

    fiducialCenters_images = {}

    fiducialCenters_images['top_left'] = [img4template[fiducialCenters['top_left'][1] -
                                                       halfwidth:fiducialCenters['top_left'][1] +
                                                       halfwidth,
                                                       fiducialCenters['top_left'][0] -
                                                       halfwidth:fiducialCenters['top_left'][0] +
                                                       halfwidth]][0]

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
        axs[x, y].imshow(fiducialCenters_images[corner_image],
                         cmap=plt.cm.gray)
        axs[x, y].set_title(corner_image)
        x = x + 1
        if x == 2:
            x = 0
            y = 1

    # save templates as images
    i = 1
    
    if not os.path.exists(output_template_folder):
        os.makedirs(output_template_folder)
    
    for corner_image in corner_list:
        template_name = 'Template_' + dataset + "_" + corner_image + '_' + str(i) + '.tif'
        while os.path.exists(output_template_folder + "/" + template_name):
            i = i+1
            template_name = 'Template_' + dataset + "_" + corner_image + '_' + str(i) + '.tif'

        corner_image_name = output_template_folder + "/" + template_name
        cv2.imwrite(corner_image_name, fiducialCenters_images[corner_image])

    # create an associated     txt file
    f = open(output_template_folder + '/' +
             "Center_Fiducials.txt", "a", newline='')
    w = csv.writer(f, delimiter=" ")
    for corner_image in corner_list:
        template_name = 'Template_' + dataset + "_" + corner_image + '_' + str(i)  # + '.tif'
        line = [[template_name, str(halfwidth), str(halfwidth)]]
        w.writerows(line)
    f.close()


if __name__ == '__main__':
    fiducialTemplateCreator(image4template_path,output_template_folder,
                            fiducialCenters, halfwidth, dataset)

# ------------------------------------------------------------------------------
# END OF FUNCTION SCRIPT
# ------------------------------------------------------------------------------