# -*- coding: utf-8 -*-
"""
========================================================================================
                     GAPPS – GeoRiskA Airphoto Pre-Processing Suite
========================================================================================
                                 = ADD CAMERA MENU =

Description: Secondary Graphical User Interface (GUI) to add a new camera to the
    pre-processing program. The user can define the camera name, the high and low
    resolution, the total length in X and Y, the length between fiducial marks in X
    and Y, and the unit of the length (cm or inch).

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

Last update: 2024-08-30
========================================================================================
"""

import tkinter as tk
from tkinter import ttk
import sys,os
import time as t


def add_camera_interface():
    root = tk.Tk()
    root.title("GAPPS — Add camera to pre-processing program")

    # GAPPS paths
    absolute_file_path = os.path.abspath(__file__)  # Extract the path of the GUI
    gapps_main_folder = os.path.dirname(absolute_file_path)  # Retrieve the main GAPPS folder path
    sys.path.insert(0, '{}/GAPPS_tools'.format(gapps_main_folder))  # Local tool imports

    # Import useful GAPPS tool
    from GAPPS_Tool_02a_Add_Camera import add_camera

    # Camera name
    tk.Label(root, text="   Camera name without spaces:   ", font=("Arial", 14), fg='black').grid(
        row=1, column=0)
    cam = tk.StringVar(root)
    camera = tk.Entry(root, textvariable=cam)
    camera.grid(row=1, column=1)
    
    # Resolution
    tk.Label(root, text="    High resolution:", font=("Arial", 14), fg='black').grid(row=3, column=0)
    resh=tk.IntVar(root,value=2400)
    resolution = tk.Entry(root, textvariable=resh)
    resolution.grid(row=3, column=1)
    
    tk.Label(root, text="    Low resolution:", font=("Arial", 14), fg='black').grid(row=4, column=0)
    resl=tk.IntVar(root, value=600)
    resolution = tk.Entry(root, textvariable=resl)
    resolution.grid(row=4,column=1)
    
    # Total length in x
    tk.Label(root, text="    Total length X:", font=("Arial", 14), fg='black').grid(row=5, column=0)
    lx=tk.DoubleVar(root)
    resolution = tk.Entry(root, textvariable=lx)
    resolution.grid(row=5,column=1)
    
    # Total length in y
    tk.Label(root, text="    Total length Y:", font=("Arial", 14), fg='black').grid(row=6, column=0)
    ly = tk.DoubleVar(root)
    resolution = tk.Entry(root, textvariable=ly)
    resolution.grid(row=6,column=1)
    
    # Length between fiducial marks in x
    tk.Label(root, text="    Length between fiducial marks X:", font=("Arial", 14), fg='black').grid(row=7, column=0)
    lxfm = tk.DoubleVar(root)
    resolution = tk.Entry(root, textvariable=lxfm)
    resolution.grid(row=7,column=1)
    
    # Length between fiducial marks in y
    tk.Label(root, text="    length between fiducial marks Y:", font=("Arial", 14), fg='black').grid(row=8, column=0)
    lyfm = tk.DoubleVar(root)
    resolution = tk.Entry(root, textvariable=lyfm)
    resolution.grid(row=8,column=1)
    
    # Unit
    style = ttk.Style(root)
    style.configure('TMenubutton', font=('Arial', 12), foreground='black')
    u = tk.StringVar(root,"Unit")
    tk.OptionMenu(root, u, *["cm","inch"]).grid(row=10,columnspan=2)
    entry_unit = ttk.OptionMenu(root, u, "Unit", "cm", "inch", style='TMenubutton')
    entry_unit.grid(row=10, columnspan=2)

    def main():
        add_camera(cam.get(), resh.get(), resl.get(), lx.get(), ly.get(), lxfm.get(), lyfm.get(), u.get())
        t.sleep(0.3)
        root.destroy()
    
    # add camera button
    style = ttk.Style(root)
    style.configure('Accent.TButton', font=('Arial', 14, 'bold'), foreground='black')
    ttk.Button(root, text="Add camera", style='Accent.TButton',
               command=main).grid(row=12, columnspan=2)
    
    tk.Label(root, text=" ").grid(row=11, column=1)
    tk.Label(root, text=" ").grid(row=13, column=1)
    tk.Label(root, text=" ").grid(row=13, column=2)
    tk.Label(root, text="   ").grid(row=0, column=2)
    tk.Label(root, text=" ").grid(row=9, column=2)
    
    root.mainloop()

if __name__ == "__main__":
    add_camera_interface()

# ------------------------------------------------------------------------------
# END OF SECONDARY GUI
# ------------------------------------------------------------------------------