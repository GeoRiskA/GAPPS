"""
========================================================================================
                     GAPPS – GeoRiskA Airphoto Pre-Processing Suite
========================================================================================
                                     = MAIN MENU =

                      #####     OOOOO    OOOOOO    OOOOOO     OOOOO
                     ##    #   O    OO   OO   OO   OO   OO   OO
                     ##        O    OO   OO    O   OO    O   OOOO
                     ##  ###   OOOOOOO   OOOOOO    OOOOOO      OOOO
                     ##    #   O    OO   OO        OO            OO
                      #####    O    OO   OO        OO        OOOOO

Description: Main Graphical User Interface (GUI) allowing the user to open the
             different tools of the software suite.

Copyright:
    RMCA — Royal Museum for Central Africa (Tervuren, BELGIUM)
        Natural Hazards and Cartography (GeoRiskA), Dpt. of Earth Sciences
    VUB — Vrije Universiteit Brussel (Brussels, BELGIUM)
        Cartography and GIS research group (CGIS), Dpt. of Geography
    © 2020 – 2024

GAPPS software management and coordination:
    - Benoît SMETS (RMCA / VUB)

GAPPS software authorship:
    GRAPHICAL USER INTERFACES (GUIs)
    - Benoît SMETS (RMCA / VUB)
    - Antoine DILLE (RMCA)
    - Amélie MAGINOT (ENSG, France)
    PRE-PROCESSING TOOLS
    - Benoît SMETS (RMCA / VUB)
    - Paul BARRIERE (ENSG, France)  — Auto. Fiducial Mark detection
    - Amélie MAGINOT (ENSG, France) — Auto./Manual Fid. Mark detection

The scripts were mostly developed on MacOS ≥ 10.11 and tested on Windows
versions 10 and 11.

Last update: 2024-08-30
========================================================================================
"""
version = "0.2.1"

import json
import sys, os
import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
import pandas as pd
import subprocess
import threading
from pathlib import Path

# PART 1 — Defining the different file and folder paths
# ======================================================

# 1.1. GAPPS paths
# -----------------

absolute_file_path = os.path.abspath(__file__) # Extract the path of the main GUI
gapps_main_folder, this_gui = os.path.split(absolute_file_path) # Retrieve the main GAPPS folder path
sys.path.insert(0, '{}/GAPPS_tools'.format(gapps_main_folder))  # Local tool imports

camera_folder = os.path.join(gapps_main_folder, "camera_models") # Define the folder storing the camera models
gui_folder = os.path.join(gapps_main_folder, "GUI_scripts") # Define the folder storing the GUI scripts

    # Import GAPPS tools
from GAPPS_tools.GAPPS_Tool_01_AirPhoto_CanvasSizing import script_01_csize as csize
from GAPPS_tools.GAPPS_Tool_02c_AutomaticFiducialDetection import autoFMdetection
from GAPPS_tools.GAPPS_Script_03_AirPhoto_Reprojection import image_reprojection
from GAPPS_tools.GAPPS_Script_04_AirPhotos_Resize import image_resampling_sharpening
from GAPPS_tools.GAPPS_Script_05_AirPhoto_CreateSingleMask import image_masking

# 1.2. Input and output folder paths
# -----------------------------------

with open('GAPPS_config.json', 'r') as f:
    # Read the contents of the file
    config = f.read()
user_config = json.loads(config)

input_img_folder = user_config['raw_scanned_airphoto_folder_path']
# 1.3. Check if the input folder exists
# --------------------------------------
if not os.path.exists(input_img_folder):
    print(f"Error: The input folder {input_img_folder} does not exist. Please check the configuration file 'GAPPS_config.json.")
    sys.exit()

output_results_folder = user_config['output_results_folder_path']
os.mkdir(output_results_folder) if not os.path.exists(output_results_folder) else None


# PART 2 — The graphical user interface (GUI)
# ============================================

# 2.1. Main window and logo
# --------------------------

    # Create the main window
root = tk.Tk()
root.title(f"GAPPS – GeoRiskA Airphoto Pre-Processing Suite, v. {version}")
root.geometry("900x800")  # Set window size (width x height)

# Configure the grid layout with three columns
root.columnconfigure(0, weight=1)
root.columnconfigure(1, weight=1)
root.columnconfigure(2, weight=1)

    # Configure the last row to expand
root.rowconfigure(28, weight=1)

    # Add the GAPPS logo
logo = Image.open(f"{gapps_main_folder}/GAPPS_logo_forGUI.png")
photo_image = ImageTk.PhotoImage(logo)
label_logo = tk.Label(root, image=photo_image)
label_logo.grid(row=0, column=0, columnspan=3, pady=15, sticky='n')

# Add the paths from GAPPS_config.json
input_folder_label = tk.Label(root, text=f"   Input folder:  {input_img_folder}", font=("Arial", 10), fg='black')
input_folder_label.grid(row=1, column=0, columnspan=3, pady=3, sticky='w')

# output_folder_label = tk.Label(root, text=f"   Output folder:  {output_results_folder}", font=("Arial", 10), fg='black')
# output_folder_label.grid(row=2, column=0, columnspan=3, pady=3, sticky='w')
# Create a horizontal separator
separator1 = ttk.Separator(root, orient='horizontal')
separator1.grid(row=2, column=0, columnspan=3, sticky='ew', pady=10)

# 2.2. Tool 1 – Airphoto Canvas Sizing
# -------------------------------------

# Define the input and output folders
input_01 = input_img_folder
out_01_name = "A_CanvasSized"
output_01 = os.path.join(output_results_folder, out_01_name)

# Function to create output folder and launch the tool
def canvas_sizing():
    def task_csize():
        # Create the output folder if it doesn't exist
        try:
            os.mkdir(output_01)
            print(f"Directory '{out_01_name}' created successfully!")
        except FileExistsError:
            print(f"Directory '{out_01_name}' already exists. Continuing...")

        if check_01.get() == 1:
            subfolders = True
        else:
            subfolders = False
        # Call the tool
        csize(input_01, output_01, subfolder=subfolders)

    # Run the task in a separate thread
    threading.Thread(target=task_csize).start()

# Create a button to open the tool
label_01 = tk.Label(root, text="   Tool 1 – Airphoto Canvas Sizing", font=("Arial", 14, "bold"), fg='black')
label_01.grid(row=3, column=0, columnspan=3, pady=5, sticky='w')
button_01 = tk.Button(root, text="OK", font=("Arial", 12, "bold"), command=canvas_sizing, fg='black', width=20, height=1)
button_01.grid(row=4, column=0, pady=10)
subfolders = False
check_01 = tk.IntVar()
c = ttk.Checkbutton(root, text="Check subfolders", variable=check_01).grid(row=4, column=2, sticky="w")

# Create a horizontal separator
separator1 = ttk.Separator(root, orient='horizontal')
separator1.grid(row=5, column=0, columnspan=3, sticky='ew', pady=10)
#space_01 = tk.Label(root, text=" ", font=("Arial", 12, "bold")
#space_01.grid(row=3, column=0)


# 2.3. Tool 2 – Fiducial Mark Detection
# --------------------------------------

    # Main label
label_02 = tk.Label(root, text="   Tool 2 – Fiducial Mark (FM) Detection", font=("Arial", 14, "bold")
, fg='black')
label_02.grid(row=6, column=0, columnspan=3, pady=5, sticky='w')

        # Sub-label 1
label_02a = tk.Label(root, text="         2.1. Select or create the new camera model", font=("Arial", 14, "italic"), fg='black')
label_02a.grid(row=7, column=0, columnspan=3, pady=5, sticky='w')

        # camera selection
            # Read the camera models from the file
camera_file_path = os.path.join(gapps_main_folder, "camera_models", "camera_list.txt")
with open(camera_file_path, "r") as camera_file:
    camera_value_list = camera_file.readlines()[0].split(";")
            # Create a StringVar to hold the selected camera model
chosen_camera = tk.StringVar(root)
chosen_camera.set("Choose a camera")
            # Create a custom style for the OptionMenu
style = ttk.Style(root)
style.configure('TMenubutton', foreground='black', font=('Arial', 12, "bold"))
            # Create the OptionMenu for camera selection with the custom style
entry_camera = ttk.OptionMenu(root, chosen_camera, *camera_value_list, style='TMenubutton')
entry_camera.grid(row=9, column=0)

        # Camera refresh button

            # Function to refresh the camera list
def refresh_camera_list():
    def task():
        with open(camera_file_path, "r") as camera_file:
            camera_value_list = camera_file.readlines()[0].split(";")

        # Update the OptionMenu on the main thread
        root.after(0, update_option_menu, camera_value_list)

    def update_option_menu(camera_value_list):
        menu = entry_camera["menu"]
        menu.delete(0, "end")
        for camera in camera_value_list:
            menu.add_command(label=camera, command=lambda value=camera: chosen_camera.set(value))

    # Run the task in a separate thread
    threading.Thread(target=task).start()

            # Create the refresh button
refresh_button = tk.Button(root, text="Refresh camera list", command=refresh_camera_list, fg='black')
refresh_button.grid(row=7, column=2, pady=5)

        # New camera model
def launch_add_camera_gui():
    script_path = os.path.join(gui_folder, "GAPPS_interface_add_camera.py")
    subprocess.Popen([sys.executable, script_path])


camera_option = tk.Label(root, text="Alternative option:", font=("Arial", 12), fg='black')
camera_option.grid(row=9, column=1, sticky='e')

add_camera_button = tk.Button(root, text="Add new camera model...", font=("Arial", 12, "bold")
, fg='black', command=launch_add_camera_gui)
add_camera_button.grid(row=9, column=2, sticky='w')

        # Sub-label 2
label_02b = tk.Label(root, text="         2.2. Create the FM templates", font=("Arial", 14, "italic"), fg='black')
label_02b.grid(row=11, column=0, columnspan=3, pady=10, sticky='w')

        # Launch template creator button
def fm_template_creator_gui():
    script_path = os.path.join(gui_folder, "GAPPS_interface_FM_TemplateCreator.py")
    subprocess.Popen([sys.executable, script_path])

button_02b = tk.Button(root, text="Launch template creator...", font=("Arial", 12, "bold")
, command=fm_template_creator_gui, fg='black', width=20, height=1)
button_02b.grid(row=12, column=0)

        # Sub-label 3
label_02c = tk.Label(root, text="         2.3. FM detection (automatic, manual correction)", font=("Arial", 14, "italic"), fg='black')
label_02c.grid(row=13, column=0, columnspan=3, pady=10, sticky='w')

        # Template folder selection
template_folder_label = tk.Label(root, text="Template folder:", font=("Arial", 12), fg='black')
template_folder_label.grid(row=16, column=0, sticky='e')

template_folder_path = tk.StringVar(root)
entry_template_folder = tk.Entry(root, textvariable=template_folder_path, width=50)
entry_template_folder.grid(row=16, column=1, columnspan=2, sticky='w')

def select_template_folder():
    fm_templates_folder = os.path.join(output_results_folder, "FM_templates")
    folder_selected = filedialog.askdirectory(initialdir=fm_templates_folder, title="Select Template Folder")
    template_folder_path.set(folder_selected)

button_template_folder = tk.Button(root, text="Browse", font=("Arial", 12), command=select_template_folder, fg='black')
button_template_folder.grid(row=16, column=3, sticky='w')

        # P-value selection
pValue_label = tk.Label(root, text="P-value:", font=("Arial", 12), fg='black')
pValue_label.grid(row=17, column=0)

p_value_list = [0.0, 0.01, 0.02, 0.04, 0.06, 0.08, 0.1, 0.15, 0.20]
chosen_p = tk.StringVar(root)
chosen_p.set(p_value_list[3]) # default value

entry_p = ttk.OptionMenu(root, chosen_p, *p_value_list)
entry_p.grid(row=18, column=0)

        # Stripe location
stripe_label = tk.Label(root, text="Stripe location:", font=("Arial", 12), fg='black')
stripe_label.grid(row=17, column=1)

stripe_list = ["Right", "Left", "Top", "Bottom"]
chosen_stripe = tk.StringVar(root)

entry_stripe = ttk.OptionMenu(root, chosen_stripe, *stripe_list)
entry_stripe.grid(row=18, column=1)

        # Launch automatic FM detection
def auto_FM_detection():
    dataset = Path(output_results_folder).name
    image_folder = os.path.join(output_results_folder, out_01_name)
    fiducial_template_folder = template_folder_path.get()
    p = float(chosen_p.get())
    black_stripe_location = chosen_stripe.get()

    # Debugging print statements
    print("Debugging information:")
    print("======================")
    print(f"Dataset: {dataset}")
    print(f"Image Folder: {image_folder}")
    print(f"Fiducial Template Folder: {fiducial_template_folder}")
    print(f"P-value: {p}")
    print(f"Black Stripe Location: {black_stripe_location}")
    print(" ")

    # Check if paths exist
    print("Checking if paths exist:")
    print("========================")
    if not os.path.exists(image_folder):
        print(f"Error: Image folder {image_folder} does not exist.")
        return
    if not os.path.exists(fiducial_template_folder):
        print(f"Error: Fiducial template folder {fiducial_template_folder} does not exist.")
        return
    else:
        print(f"Paths exist. All is good on this side.")
    print(" ")

    autoFMdetection(image_folder, fiducial_template_folder, dataset, p, black_stripe_location)

auto_FM_detection_button = tk.Button(root, text="Run automatic FM detection", font=("Arial", 12, "bold")
, command=auto_FM_detection, fg='black', width=25, height=1)
auto_FM_detection_button.grid(row=17, column=2)

        # Launch manual FM correction
def manual_FM_detection():
    p = float(chosen_p.get())
    black_stripe_location = chosen_stripe.get().lower()
    script_path = os.path.join(gui_folder, "GAPPS_interface_image_to_check.py")
    subprocess.Popen([sys.executable, script_path, str(p), black_stripe_location])

manual_FM_detection_button = tk.Button(root, text="Run manual FM correction", font=("Arial", 12, "bold")
, command=manual_FM_detection, fg='black', width=25, height=1)
manual_FM_detection_button.grid(row=18, column=2)

    # Create a horizontal separator
separator2 = ttk.Separator(root, orient='horizontal')
separator2.grid(row=19, column=0, columnspan=3, sticky='ew', pady=15)

# 2.4. Tool 3 – Image Reprojection
# ---------------------------------

    # Main label
label_03 = tk.Label(root, text="   Tool 3 – Image Reprojection", font=("Arial", 14, "bold")
, fg='black')
label_03.grid(row=20, column=0, columnspan=1, pady=5, sticky='w')

    # Reprojection button
def reproject_image():
    def task_reproject():
        image_reprojection()
    threading.Thread(target=task_reproject).start()
button_03 = tk.Button(root, text="Launch Image Reprojection", font=("Arial", 12, "bold")
, command=reproject_image, fg='black', width=25, height=1)
button_03.grid(row=21, column=0)


# 2.5. Tool 4 – Image Resampling and Sharpening
# ----------------------------------------------

    # Main label
label_04 = tk.Label(root, text="   Tool 4 – Image Resampling and Sharpening", font=("Arial", 14, "bold")
, fg='black')
label_04.grid(row=20, column=1, columnspan=2, pady=5, sticky='w')

    # Define resolution lists
def resolution_list(self, camera):
    # this function changes the list of resolution depending on the chosen camera
    # remove current list
    root.entry_input_res['menu'].delete(0, 'end')
    root.entry_ouput_res['menu'].delete(0, 'end')

    # select file
    resolution_file = r"{}/camera_models/{}_Airphoto_Photo_dimensions_vs_dpi.csv".format(gapps_main_folder, camera)

    res_file = pd.read_csv(resolution_file, sep=',', header=[0])

    res_col = res_file['Resolution']
    res_list = res_col.tolist()

    # Insert list of new options in the input and output resolution lists
    for choice in res_list:
        root.entry_input_res['menu'].add_command(label=choice, command=tk._setit(self.chosen_input_res, choice))
        root.entry_ouput_res['menu'].add_command(label=choice, command=tk._setit(self.chosen_output_res, choice))

    # resolution buttons
input_resol_label = tk.Label(root, text="Input resolution (dpi)", font=("Arial", 12), fg='black')
input_resol_label.grid(row=21, column=1)

chosen_input_res = tk.StringVar(root)
chosen_input_res.set("Choose resolution")
entry_input_res = ttk.OptionMenu(root, chosen_input_res, "Choose resolution")
entry_input_res.grid(row=22, column=1)

output_resol_label = tk.Label(root, text="Output resolution (dpi)", font=("Arial", 12), fg='black')
output_resol_label.grid(row=23, column=1)

chosen_output_res = tk.StringVar(root)
chosen_output_res.set("Choose resolution")
entry_ouput_res = ttk.OptionMenu(root, chosen_output_res, "Choose resolution")
entry_ouput_res.grid(row=24, column=1)

    # Sharpening options
clahe_label = tk.Label(root, text="Histogram calibration", font=("Arial", 12), fg='black')
clahe_label.grid(row=21, column=2)

clahe_list = ["True", "False"]
chosen_clahe = tk.StringVar(root)
chosen_clahe.set(clahe_list[0]) # default value

entry_clahe = ttk.OptionMenu(root, chosen_clahe, *clahe_list)
entry_clahe.grid(row=22, column=2)

sharpening_intensity_label = tk.Label(root, text="Sharpening intensity", font=("Arial", 12), fg='black')
sharpening_intensity_label.grid(row=23, column=2)

sharpening_intensity_list = [0, 1, 2]
chosen_intensity = tk.StringVar(root)
chosen_intensity.set(sharpening_intensity_list[2]) # default value

entry_intensity = ttk.OptionMenu(root, chosen_intensity, *sharpening_intensity_list)
entry_intensity.grid(row=24, column=2)

    # Resampling and sharpening button
def im_resampling_sharpening():
    def task_resampling_sharpening():
        image_resampling_sharpening(chosen_input_res.get(), chosen_output_res.get(), chosen_clahe.get(), chosen_intensity.get())
    threading.Thread(target=task_resampling_sharpening).start()
button_04 = tk.Button(root, text="Run Resampling/Sharpening", font=("Arial", 12, "bold")
, command=im_resampling_sharpening, fg='black', width=25, height=1)
button_04.grid(row=25, column=1)

    # Create a horizontal separator
separator4 = ttk.Separator(root, orient='horizontal')
separator4.grid(row=26, column=0, columnspan=3, sticky='ew', pady=10)
#space_04 = tk.Label(root, text=" ", font=("Arial", 12, "bold")
#space_04.grid(row=19, column=0)


# 2.6. Tool 5 – Image Masking
# ----------------------------

    # Main label
label_05 = tk.Label(root, text="   Tool 5 – Image Masking", font=("Arial", 14, "bold")
, fg='black')
label_05.grid(row=27, column=0, columnspan=3, pady=5, sticky='w')

    # entry titles
entry_x_title = tk.Label(root, text="% in X", font=("Arial", 12), fg='black')
entry_x_title.grid(row=28, column=0)

entry_y_title = tk.Label(root, text="% in Y", font=("Arial", 12), fg='black')
entry_y_title.grid(row=28, column=1)

    # entry fields
entry_x = tk.Entry(root)
entry_x.grid(row=29, column=0)

entry_y = tk.Entry(root)
entry_y.grid(row=29, column=1)

    # Masking button
def masking():
    def task_masking():
        image_masking(entry_x.get(), entry_y.get())
    threading.Thread(target=task_masking).start()
mask_button = tk.Button(root, text="Create mask", font=("Arial", 12, "bold")
, command=masking, fg='black', width=25, height=1)
mask_button.grid(row=29, column=2)


# 2.7. Copyright label and end of GUI
# ------------------------------------

# Add copyright label at the bottom using grid with sticky option
copyright_label = tk.Label(root, text="© Royal Museum for Central Africa / Vrije Universiteit Brussel, 2020-2024. This software is released under the GPL-3.0 license.",
                         font=("Arial", 9, "italic"), fg="gray")
copyright_label.grid(row=34, column=0, columnspan=3, sticky='s')

# Start the main event loop
root.mainloop()

# ------------------------------------------------------------------------------
# END OF THE MAIN GUI
# ------------------------------------------------------------------------------