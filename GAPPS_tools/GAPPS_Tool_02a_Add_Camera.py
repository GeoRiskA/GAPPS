"""
========================================================================================
                     GAPPS – GeoRiskA Airphoto Pre-Processing Suite
========================================================================================
                                 = ADD CAMERA FUNCTION =

Description: Add a new camera model to the camera list. The user can define the camera
    name, the high and low resolution, the total length in X and Y, the length between
    fiducial marks in X and Y, and the unit of the length (cm or inch).

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

import os
import numpy as np
import pandas as pd
from pathlib import Path

def add_camera(camera_name, high_res, low_res, length_x, length_y, length_fiducial_x, length_fiducial_y, unit):
    # Retrieve the main GAPPS folder path
    gapps_main_folder = Path(__file__).resolve().parent.parent
    camera_model_folder = gapps_main_folder / "camera_models"
    camera_folder = camera_model_folder / "cameras"
    camera_file_path = camera_model_folder / "camera_list.txt"

    # Ensure the camera and camera_models directories exist
    camera_model_folder.mkdir(parents=True, exist_ok=True)
    camera_folder.mkdir(parents=True, exist_ok=True)

    # Print action starts
    print()
    print("-------------------------")
    print("   ADD CAMERA FUNCTION   ")
    print("-------------------------")
    print(f"Adding camera {camera_name} to the list of camera models...")

    # Update camera_list.txt
    with open(camera_file_path, "a") as camera_file:
        camera_file.write(f";{camera_name}")

    # Create the camera description file in CSV format
    new_camera_csv_path = os.path.join(camera_folder, f"{camera_name}_camera_description.csv")
    with open(new_camera_csv_path, "w") as new_camera_csv:
        new_camera_csv.write(f"Camera name: {camera_name}\n")
        new_camera_csv.write(f"High Resolution: {high_res}\n")
        new_camera_csv.write(f"Low Resolution: {low_res}\n")
        new_camera_csv.write(f"Total Length X: {length_x} {unit}\n")
        new_camera_csv.write(f"Total Length Y: {length_y} {unit}\n")
        new_camera_csv.write(f"Length between Fiducial Marks X: {length_fiducial_x} {unit}\n")
        new_camera_csv.write(f"Length between Fiducial Marks Y: {length_fiducial_y} {unit}\n")

    # List the resolution range
    res = []
    for r in range(low_res, high_res+100, 100):
        res.append(r)

    # Create the lists of resolution values
    lpx = []
    lpy = []
    fmpx = []
    fmpy = []

    # Deal with the cm and inch units

    if unit == "inch":
        for i in range(len(res)):
            lpx.append(round(length_x*res[i]))
            lpy.append(round(length_y*res[i]))
            fmpx.append(round(length_fiducial_x*res[i]))
            fmpy.append(round(length_fiducial_y*res[i]))
    elif unit == "cm":
        for i in range(len(res)):
            lpx.append(round(length_x*res[i]/2.54))
            lpy.append(round(length_y*res[i]/2.54))
            fmpx.append(round(length_fiducial_x*res[i]/2.54))
            fmpy.append(round(length_fiducial_y*res[i]/2.54))

    # Transform the lists into arrays
    lpx = np.array(lpx)
    lpy = np.array(lpy)
    fmpx = np.array(fmpx)
    fmpy = np.array(fmpy)

    # Calculate the pixel coordinates of the fiducial marks, for each resolution
    fm_left_x = (lpx - fmpx) / 2
    fm_right_x = fm_left_x + fmpx

    fm_top_y = (lpy - fmpy) / 2
    fm_bottom_y = fm_top_y + fmpy

    # Make them integers
    fm_left_x_int = [round(i) for i in fm_left_x]
    fm_right_x_int = [round(i) for i in fm_right_x]

    fm_top_y_int = [round(i) for i in fm_top_y]
    fm_bottom_y_int = [round(i) for i in fm_bottom_y]

    # Create the camera model as a dataframe
    new_camera_model = pd.DataFrame({"Resolution": pd.Series(res),
                         "X dimension (pixel)": pd.Series(lpx),
                         "Y dimension (pixel)": pd.Series(lpy),
                         "X distance between FM": pd.Series(fmpx),
                         "Y distance between FM": pd.Series(fmpy),
                         "Xp1": fm_left_x_int,
                         "Yp1": fm_top_y_int,
                         "Xp2": fm_right_x_int,
                         "Yp2": fm_top_y_int,
                         "Xp3": fm_right_x_int,
                         "Yp3": fm_bottom_y_int,
                         "Xp4": fm_left_x_int,
                         "Yp4": fm_bottom_y_int,
                         })

    # Save the camera model as a CSV file
    new_camera_model.to_csv(camera_model_folder / f"{camera_name}_Airphoto_dimensions_vs_dpi.csv", sep=",", index=False)

    # Print action ends
    print()
    print(f"Camera {camera_name} added to the camera list.")
    print()

if __name__ == "__main__":
    add_camera(camera_name, high_res, low_res, length_x, length_y, length_fiducial_x, length_fiducial_y, unit)

# ------------------------------------------------------------------------------
# END OF FUNCTION SCRIPT
# ------------------------------------------------------------------------------