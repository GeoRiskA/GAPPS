"""
========================================================================================
                     GAPPS – GeoRiskA Airphoto Pre-Processing Suite
========================================================================================
                          = CREATE FM TEMPLATES FUNCTION =

Description: This script aims to create templates for the four fiducial marks
    (4 corners) of an aerial image for later automatic detection of the fiducial marks
    on a large set of aerial images.
    Simply provide the path of one image of the set with representative fiducial marks
    and the pixel coordinates of the centre of the four fiducial marks.
    Note that automatic FM detection allows to test multiple templates.

Copyright:
    RMCA — Royal Museum for Central Africa (Tervuren, BELGIUM)
        Natural Hazards and Cartography (GeoRiskA), Dpt. of Earth Sciences
    VUB — Vrije Universiteit Brussel (Brussels, BELGIUM)
        Physical Geography (FARD), Dpt. of Geography
    © 2021 – 2026

Software management and coordination:
    - Benoît SMETS (RMCA / VUB)

Software authorship:
    - Antoine Dille (RMCA)
    - Benoît SMETS (RMCA / VUB)

The script was developed on Windows 10 and MacOS ≥ 14.6.

Last update: 2026-10-14
========================================================================================
"""

import cv2
import os
import csv
import numpy as np
from matplotlib.figure import Figure

CORNER_LIST = ['top_left', 'top_right', 'bot_right', 'bot_left']


def read_image(image_path):
    """Read an image with OpenCV, also for paths with non-ASCII characters (Windows)."""
    img = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise IOError(f"Unable to read the image: {image_path}")
    return img


def write_image(image_path, img):
    """Write an image with OpenCV, also for paths with non-ASCII characters (Windows)."""
    ok, buffer = cv2.imencode(os.path.splitext(image_path)[1], img)
    if not ok:
        raise IOError(f"Unable to write the image: {image_path}")
    buffer.tofile(image_path)


def fiducialTemplateCreator(image4template_path, output_template_folder, fiducialCenters, halfwidth=240,
                            dataset='WRC10'):
    """Crop and save the four fiducial mark templates.

    :param image4template_path: path of the image used to create the templates
    :param output_template_folder: folder where the templates are saved
    :param fiducialCenters: dict {corner: [x, y]} with the pixel coordinates of the centre of the
        fiducial marks, for corners 'top_left', 'top_right', 'bot_right' and 'bot_left'
    :param halfwidth: half width (pix) of the square templates
    :param dataset: name of the template dataset (used in the template file names)
    """
    print(fiducialCenters)

    img4template = read_image(image4template_path)
    h, w = img4template.shape[:2]
    halfwidth = int(halfwidth)

    # Crop the templates around the fiducial mark centres
    fiducialCenters_images = {}
    for corner in CORNER_LIST:
        x, y = int(fiducialCenters[corner][0]), int(fiducialCenters[corner][1])
        if x - halfwidth < 0 or y - halfwidth < 0 or x + halfwidth > w or y + halfwidth > h:
            raise ValueError(f"The {corner} template (centre x={x}, y={y}, half width={halfwidth}) "
                             f"exceeds the image ({w} x {h} pix).")
        fiducialCenters_images[corner] = img4template[y - halfwidth:y + halfwidth,
                                                      x - halfwidth:x + halfwidth]

    if not os.path.exists(output_template_folder):
        os.makedirs(output_template_folder)

    # Find the first template index not used yet
    i = 1
    for corner in CORNER_LIST:
        template_name = 'Template_' + dataset + "_" + corner + '_' + str(i) + '.tif'
        while os.path.exists(output_template_folder + "/" + template_name):
            i = i + 1
            template_name = 'Template_' + dataset + "_" + corner + '_' + str(i) + '.tif'

    # Save templates as images
    for corner in CORNER_LIST:
        template_name = 'Template_' + dataset + "_" + corner + '_' + str(i) + '.tif'
        write_image(output_template_folder + "/" + template_name, fiducialCenters_images[corner])

    # Save a figure with the 4 fiducials for a quick check
    fig = Figure(figsize=(6, 6))
    positions = {'top_left': 1, 'top_right': 2, 'bot_left': 3, 'bot_right': 4}
    for corner in CORNER_LIST:
        ax = fig.add_subplot(2, 2, positions[corner])
        template = fiducialCenters_images[corner]
        if template.ndim == 3:
            template = cv2.cvtColor(template, cv2.COLOR_BGRA2RGBA if template.shape[2] == 4
                                    else cv2.COLOR_BGR2RGB)
        ax.imshow(template, cmap='gray')
        ax.axhline(halfwidth, color='r', lw=0.5)
        ax.axvline(halfwidth, color='r', lw=0.5)
        ax.set_title(corner)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle(f"Templates {dataset} #{i} (half width = {halfwidth} pix)")
    fig.tight_layout()
    fig.savefig(os.path.join(output_template_folder, f"Preview_{dataset}_{i}.png"), dpi=100)

    # Create an associated txt file
    f = open(output_template_folder + '/' + "Center_Fiducials.txt", "a", newline='')
    wr = csv.writer(f, delimiter=" ")
    for corner in CORNER_LIST:
        template_name = 'Template_' + dataset + "_" + corner + '_' + str(i)  # + '.tif'
        wr.writerows([[template_name, str(halfwidth), str(halfwidth)]])
    f.close()

    return i


# ------------------------------------------------------------------------------
# END OF FUNCTION SCRIPT
# ------------------------------------------------------------------------------
