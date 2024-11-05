# -*- coding: utf-8 -*-
"""
========================================================================================
                     GAPPS – GeoRiskA Airphoto Pre-Processing Suite
========================================================================================
                             = FM TEMPLATE CREATOR MENU =

Description: Secondary Graphical User Interface (GUI) to create fiducial templates
    for airphoto pre-processing. The user can define the coordinates of the four
    fiducial marks (top left, top right, bottom right, bottom left), the half width
    of the fiducial mark templates, the name of the dataset, and the source image to
    extract the template.

Copyright:
    RMCA — Royal Museum for Central Africa (Tervuren, BELGIUM)
        Natural Hazards and Cartography (GeoRiskA), Dpt. of Earth Sciences
    VUB — Vrije Universiteit Brussel (Brussels, BELGIUM)
        Cartography and GIS research group (CGIS), Dpt. of Geography
    © 2022 – 2024

Software management and coordination:
    - Benoît SMETS (RMCA / VUB)

Software authorship:
    - Amélie MAGINOT (ENSG, France)
    - Benoît SMETS (RMCA / VUB)

The script was developed on Windows 10 and MacOS ≥ 14.6.

Last update: 2024-10-04
========================================================================================
"""

import tkinter as tk
import os
import sys
import json
from tkinter import ttk
from tkinter import filedialog
from time import sleep
from pathlib import Path


def interface_fiducial_template():
    root = tk.Tk()
    root.title("GAPPS – Fiducial Template creator")
    tk.Label(root, text=" ").grid(rowspan=15, column=0)
    tk.Label(root, text=" ").grid(rowspan=15, column=5)
    tk.Label(root, text=" ").grid(rowspan=15, column=7)

    # GAPPS paths
    absolute_file_path = os.path.abspath(__file__)  # Extract the path of the GUI
    gapps_main_folder = os.path.dirname(absolute_file_path)  # Retrieve the main GAPPS folder path
    sys.path.insert(0, '{}/GAPPS_tools'.format(gapps_main_folder))  # Local tool imports

    # Import useful GAPPS tool
    from GAPPS_Tool_02b_Tool_FiducialTemplateCreator import fiducialTemplateCreator

    # JSON file path
    config_path = os.path.join(gapps_main_folder, '..', 'GAPPS_config.json')

    # Get the main output data folder
    with open(config_path, 'r') as f:
        # Read the contents of the file
        config = f.read()
    user_config = json.loads(config)

    # Get the main output folder path and create the folder for the FM templates
    output_results_folder = user_config['output_results_folder_path']
    out_FM_template_name = "_FM_templates"
    output_FM_templates = os.path.join(output_results_folder, out_FM_template_name)
    try:
        os.mkdir(output_FM_templates)
        print(f"Directory '{out_FM_template_name}' created successfully!")
    except FileExistsError:
        print(f"Directory '{out_FM_template_name}' already exists. Continuing...")

    # Top-left corner
    tk.Label(root, text="Top-left corner coordinates (pix)", font=("Arial", 14), fg='black').grid(row=1, column=0,columnspan=2)
    tk.Label(root, text="X =", font=("Arial", 14), fg='black').grid(row=2, column=0)
    tk.Label(root, text="Y =", font=("Arial", 14), fg='black').grid(row=3, column=0)
    X1 = tk.IntVar(root)
    Y1 = tk.IntVar(root)
    HLx = tk.Entry(root, textvariable=X1)
    HLy = tk.Entry(root, textvariable=Y1)
    HLx.grid(row=2, column=1)
    HLy.grid(row=3, column=1)
    
    # Top-right corner
    tk.Label(root, text="Top-right corner coordinates (pix)", font=("Arial", 14), fg='black').grid(row=1, column=3,columnspan=2)
    tk.Label(root, text="X =", font=("Arial", 14), fg='black').grid(row=2, column=3)
    tk.Label(root, text="Y =", font=("Arial", 14), fg='black').grid(row=3, column=3)
    X2 = tk.IntVar(root)
    Y2 = tk.IntVar(root)
    HRx = tk.Entry(root, textvariable=X2)
    HRy = tk.Entry(root, textvariable=Y2)
    HRx.grid(row=2, column=4)
    HRy.grid(row=3, column=4)
    
    # Bottom-right corner
    tk.Label(root, text="Bottom-right corner coordinates (pix)", font=("Arial", 14), fg='black').grid(row=9, column=3,columnspan=2)
    tk.Label(root, text="X =", font=("Arial", 14), fg='black').grid(row=10, column=3)
    tk.Label(root, text="Y =", font=("Arial", 14), fg='black').grid(row=11, column=3)
    X3 = tk.IntVar(root)
    Y3 = tk.IntVar(root)
    LRx = tk.Entry(root, textvariable=X3)
    LRy = tk.Entry(root, textvariable=Y3)
    LRx.grid(row=10, column=4)
    LRy.grid(row=11, column=4)
    
    # Bottom-left corner
    tk.Label(root, text="Bottom-left corner coordinates (pix)", font=("Arial", 14), fg='black').grid(row=9, column=0,columnspan=2)
    tk.Label(root, text="X =", font=("Arial", 14), fg='black').grid(row=10, column=0)
    tk.Label(root, text="Y =", font=("Arial", 14), fg='black').grid(row=11, column=0)
    X4 = tk.IntVar(root)
    Y4 = tk.IntVar(root)
    LLx = tk.Entry(root, textvariable=X4)
    LLy = tk.Entry(root, textvariable=Y4)
    LLx.grid(row=10, column=1)
    LLy.grid(row=11, column=1)
    
    # settings
    # half width (of the fiducial mark template to crop)
    tk.Label(root, text="Template half width (pix)", font=("Arial", 14), fg='black').grid(row=4, column=2)
    halfwidth = tk.IntVar(root)
    tk.Entry(root, textvariable=halfwidth).grid(row=5, column=2)
    # dataset
    tk.Label(root, text="Template dataset name (without space)", font=("Arial", 14), fg='black').grid(row=6, column=2)
    dataset = tk.StringVar(root)
    tk.Entry(root, textvariable=dataset).grid(row=7, column=2)
    
    # image
    tk.Label(root, text="  Input image", font=("Arial", 14), fg='black').grid(row=13, column=0)
    entry_input_images = tk.Entry(root, width=80)
    entry_input_images.grid(row=13, column=1, columnspan=4)
    
    tk.Button(root, text="Select image", font=("Arial", 14, "bold"), fg='black', command=lambda: find_input_image(
        entry_input_images, "Select image ")).grid(row=13, column=6)

    global path
    path = "./"

    def find_input_image(e, text):
        global path
        root.filename = filedialog.askopenfilename(initialdir=path, title=text)
        path = root.filename
        e.insert(0, root.filename)
        input_image.append(path)

    input_image = []

    def main():
        fiducialCenters = {'top_left': [X1.get(), Y1.get()],
                           'top_right': [X2.get(),Y2.get()],
                           'bot_right': [X3.get(),Y3.get()],
                           'bot_left': [X4.get(), Y4.get()]}
        print("interface fidcenter: {}".format(X1.get()))
        w = halfwidth.get()
        d = dataset.get()

        template_dataset_folder = os.path.join(output_FM_templates, d)
    
        fiducialTemplateCreator(input_image[0], template_dataset_folder, fiducialCenters, w, d)
        sleep(1)
        root.destroy()
    
    
    tk.Label(root, text=" ").grid(row=12)
    tk.Label(root, text=" ").grid(row=15)
    tk.Label(root, text=" ").grid(row=17)

    style = ttk.Style()
    style.configure("TButton", font=("Arial", 14, "bold"), foreground='black')
    ttk.Button(root, text="Create fiducial template", style='TButton',
               command=main).grid(row=16, column=2)
    
    root.mainloop()

if __name__ == '__main__':
    interface_fiducial_template()

# ------------------------------------------------------------------------------
# END OF SECONDARY GUI
# ------------------------------------------------------------------------------