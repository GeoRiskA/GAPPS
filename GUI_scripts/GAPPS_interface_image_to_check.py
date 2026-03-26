"""
========================================================================================
                     GAPPS – GeoRiskA Airphoto Pre-Processing Suite
========================================================================================
                       = INTERFACE TO CHECK FIDUCIAL MARKS =

Description: This script aims to provide an interface to check the fiducial marks
             of a set of aerial images. The user can visualize the images and check
             the coordinates of the fiducial marks. The script reads the images from
             a folder and displays them one by one. The user can zoom in and out, move
             the image, and check the coordinates of the fiducial marks.

Copyright:
    RMCA — Royal Museum for Central Africa (Tervuren, BELGIUM)
        Natural Hazards and Cartography (GeoRiskA), Dpt. of Earth Sciences
    VUB — Vrije Universiteit Brussel (Brussels, BELGIUM)
        Cartography and GIS research group (CGIS), Dpt. of Geography
    © 2022 – 2024

Software management and coordination:
    - Benoît SMETS (RMCA / VUB)

Software authorship:
    - Amélie MAGINOT (ENSG)
    - Benoît SMETS (RMCA / VUB)

The script was developed on Windows 10 and MacOS ≥ 14.6.

Last update: 2024-10-04
========================================================================================
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
import pandas as pd
import json

# GAPPS paths and tools
absolute_file_path = os.path.abspath(__file__)
gapps_main_folder, this_gui = os.path.split(absolute_file_path)
sys.path.insert(0, '{}/GAPPS_tools'.format(gapps_main_folder))

from GAPPS_tools.zoom_and_move_app import Zoom_Advanced

# Input/output folders
with open('GAPPS_config.json', 'r') as f:
    config = f.read()
user_config = json.loads(config)

output_results_folder = user_config['output_results_folder_path']
images_to_check_folder = os.path.join(output_results_folder, "out_01_name", "_To_Be_Checked")

def save_fiducial_marks(fiducial_marks):
    df = pd.DataFrame(fiducial_marks, columns=['image', 'x', 'y'])
    df.to_csv('manual_fiducial_marks.csv', index=False)

def on_click(event, fiducial_marks, canvas, image_name):
    x, y = event.x, event.y
    fiducial_marks.append((image_name, x, y))
    canvas.create_oval(x-5, y-5, x+5, y+5, outline='red', width=2)

def load_image(canvas, image_path):
    image = Image.open(image_path)
    photo = ImageTk.PhotoImage(image)
    canvas.create_image(0, 0, anchor=tk.NW, image=photo)
    canvas.image = photo

def interface_image_to_check(image_path):
    root = tk.Tk()
    root.title("Manual Fiducial Mark Detection")

    fiducial_marks = []
    image_name = os.path.basename(image_path)

    canvas = tk.Canvas(root, width=800, height=600)
    canvas.pack()

    load_image(canvas, image_path)
    canvas.bind("<Button-1>", lambda event: on_click(event, fiducial_marks, canvas, image_name))

    save_button = tk.Button(root, text="Save Fiducial Marks", command=lambda: save_fiducial_marks(fiducial_marks))
    save_button.pack()

    root.mainloop()

if __name__ == "__main__":
    image_path = filedialog.askopenfilename()
    p = float(sys.argv[1])
    black_stripe_location = sys.argv[2]
    interface_image_to_check(image_path)