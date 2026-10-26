<div align="center">
	<img src="https://github.com/GeoRiskA/GAPPS/blob/main/assets/GAPPS_logo_forGUI.png?raw=true">
</div> 

<h3 align="center">
<i>Prepare your scanned aerial photographs for photogrammetric processing!</i>
</h3>

<br>

**GAPPS is a set of tools to prepare scanned aerial photographs for photogrammetric processing. It allows strandardizing the size/resolution of the photographs, as well as orienting them to get the centre of perspective of the photos at the centre of the digital image.**  

**GAPPS offers 5 main tools:**  
- **1. Canvas sizing:**  This first tool makes sure that all the scanned images have the same dimensions, by adding pixel rows or columns if needed, or crops them to the photo frame.  
- **2. Fiducial mark detection:** This group of tools is used to create fiducial mark templates by clicking on an image, to automatically detect the fiducial marks on the sides of the photographs, and to review/correct the detections manually.  
- **3. Reprojection:** This tool exploits the position of the fiducial marks to reproject and crop the images, to get images devoid of black margins, with their centre corresponding to the centre of perspective.  
- **4. Resize:** This tool downsamples and sharpens the reprojected images, for better photogrammetric results.  
- **5. Mask creation:** This tool creates a mask image that will hide the fiducial marks visible within the images during the photogrammetric processing.

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54) [![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

-------

***Software Management and Coordination:***  
- Prof. Dr. Benoît SMETS – Royal Museum for Central Africa (RMCA) / Vrije Universiteit Brussel (VUB) – BE  

***Contributors:***. 
- Prof. Dr. Benoît SMETS – Royal Museum for Central Africa (RMCA) / Vrije Universiteit Brussel (VUB) – BE  
  > *Main tools, Graphical User Interface*   
- Dr. Antoine DILLE – Royal Museum for Central Africa (RMCA) / Vrije Universiteit Brussel (VUB) – BE  
  > *Image resampling/sharpening tool, Fiducial Mark Detection, Graphical User Interface*   
- Mr. Paul BARRIERE - Former student of ENSG-Géomatique – FR
  > *Fiducial Mark Detection*  
- Ms. Amélie MAGINOT – Former student of ENSG-Géomatique – FR
  > *Fiducial Mark Detection, Graphical User Interface*  

***Citation:*** *(in progress)*  

When using GAPPS or part of the scripts developed in GAPPS, please cite the following references in you work:  

- ***The repository:*** Smets, B., Dille, A., 2026.  GAPPS — GeoRiskA Airphoto Pre-Processing Suite. Version 0.4.0 Zenodo XXXX
- ***The publication (in preparation):*** XXXX

--------------

### User guide

A step-by-step guide to the tools, with figures and recommended settings: [docs/GAPPS_user_guide.pdf](docs/GAPPS_user_guide.pdf).

### Dependencies
GAPPS is coded in Python 3 (Python 3.8 and 3.12 have been tested), and requires Tkinter, which usually comes by default with Python 3.
To make sure that Tkinter is installed, you can run the following command in your terminal:
```bash
python3 -m tkinter
```
If tkinter is not installed, you can install it using the following command:
```bash
sudo apt-get install python3-tk
```

GAPPS also requires the following Python packages to run: `opencv, matplotlib, joblib, pillow, numpy, pandas, scikit-image, scikit-learn`. They will be installed in a virtual environment during the installation procedure.

### Installation of GAPPS

GAPPS is a Python application and should be installed inside its own virtual environment. The recommended structure is to keep the virtual environment inside the GAPPS folder as `.venv/`.

The `.venv/` folder does not come from Github. It is created locally during installation.

<br>

## INSTALLATION ON LINUX (Ubuntu)

#### 1. Download GAPPS from GitHub
Open a terminal and clone the repository:
```bash
git clone https://github.com/GeoRiskA/GAPPS.git
```

#### 2. Place APPS in its preferred location
Move the GAPPS folder to your preferred location, for example: `/home/your_username/Applications/GAPPS`.   

Then, enter the GAPPS folder using the terminal:
```bash
cd /home/your_username/Applications/GAPPS
``` 

#### 3. Create the virtual environment
Once the terminal has entered the GAPPS folder, create a virtual environment named `.venv` inside the GAPPS folder:
```bash
python3 -m venv .venv
```
Now, install the required Python packages inside the virtual environment:
```bash
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
``` 

#### 4. Prepare the application launcher
For this, you can follow the instructions in the [LaunchGAPPS_Linux_CreationGuide.md](LaunchGAPPS_Linux_CreationGuide.md) file.

Make sure the launcher is executable and that you have allowed launching from the desktop.

#### 5. Launch GAPPS
Before launching GAPPS, make sure that you modified the file `GAPPS_config.json` to set the correct existing folder paths. Without this, GAPPS will not launch properly and will display an error message in the terminal.  

Launch GAPPS by double-clicking the launcher icon on your desktop. The application should start properly.
If not, launch GAPPS from the terminal using the following command (from the GAPPS folder):
```bash
./.venv/bin/python run_gapps.py
```

<br>

## INSTALLATION ON MAC OS

#### 1. Download GAPPS from GitHub
Open Terminal and clone the repository:
```bash
git clone https://github.com/GeoRiskA/GAPPS.git
```
#### 2. Place GAPPS in its preferred location
Move the GAPPS folder to your preferred location, for example: `/Users/your_username/Applications/GAPPS`.   

Then, enter the GAPPS folder using Terminal:
```bash
cd /Users/your_username/Applications/GAPPS
```
#### 3. Create the virtual environment
Once Terminal has entered the GAPPS folder, create a virtual environment named `.venv` inside the GAPPS folder:
```bash
python3 -m venv .venv
```
Now, install the required Python packages inside the virtual environment:
```bash
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
``` 

#### 4. Prepare the application launcher
For this, you can follow the instructions in the [LaunchGAPPS_MacOS_CreationGuide.md](LaunchGAPPS_MacOS_CreationGuide.md) file.

Make sure the launcher is executable and that you have allowed launching from Finder.

#### 5. Launch GAPPS
Before launching GAPPS, make sure that you modified the file `GAPPS_config.json` to set the correct existing folder paths. Without this, GAPPS will not launch properly and will display an error message in the terminal.

Launch GAPPS by double-clicking the launcher icon or the `Launch_GAPPS.command` file. The application should start properly.
If not, launch GAPPS from Terminal using the following command (from the GAPPS folder):
```bash
./.venv/bin/python run_gapps.py
```

<br>

## INSTALLATION ON WINDOWS 11

#### 1. Download GAPPS from GitHub
Open PowerShell and clone the repository:
```powershell
git clone https://github.com/GeoRiskA/GAPPS.git
```

#### 2. Place GAPPS in its preferred location
Move the GAPPS folder to your preferred location, for example: `C:\Users\your_username\Applications\GAPPS`.   

Then, enter the GAPPS folder using PowerShell:
```powershell
cd C:\Users\your_username\Applications\GAPPS
``` 

#### 3. Create the virtual environment
Once PowerShell has entered the GAPPS folder, create a virtual environment named `.venv` inside the GAPPS folder:
```powershell
py -m venv .venv
```
Now, install the required Python packages inside the virtual environment:
```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
``` 

#### 4. Prepare the application launcher
For this, you can follow the instructions in the [LaunchGAPPS_Windows_CreationGuide.md](LaunchGAPPS_Windows_CreationGuide.md) file.

Make sure the launcher or shortcut is properly created and, if desired, associated with the GAPPS icon.

#### 5. Launch GAPPS
Before launching GAPPS, make sure that you modified the file `GAPPS_config.json` to set the correct existing folder paths. Without this, GAPPS will not launch properly and will display an error message in the terminal.

Launch GAPPS by double-clicking the launcher icon, the shortcut, or the `Launch_GAPPS.bat` file. The application should start properly.
If not, launch GAPPS from PowerShell using the following command (from the GAPPS folder):
```powershell
.\.venv\Scripts\python.exe run_gapps.py
```


<br>

## WHAT'S NEW (development version, October 2026)

This version merges the development branch (`Dev_202603`) into v0.4.0 and adds the following changes.

#### Tool 1 – Canvas sizing / crop to photo frame
- **Faster:** when *Crop to photo frame* is selected, the original scans are cropped directly and the canvas sizing (whose output was not used in that case) is skipped. The black frame is detected on a 1/4 downsampled copy of the image, and the images are cropped in parallel (~2 s per 1600 dpi scan instead of minutes; the former full-resolution check figure alone needed more than 7 GB of RAM).
- **Fixed:** images already processed are skipped again (the check failed for `.tiff` files, which were all reprocessed); the output folders (e.g. `output_results` inside the input folder, with the FM templates) are no longer scanned as input folders; the canvas size is computed on all images, so that resumed runs keep the same canvas size.
- The *Crop to photo frame* option is now read when the tools run (changing it after launching GAPPS had no effect on Tools 2 and 3).

#### Tool 2 – Fiducial marks (FM)
- **Template creator (2.2):** instead of typing pixel coordinates, the first image of `A_CanvasSized_Cropped` (or any image) is displayed and the four FMs are picked by clicking near them; a zoom view (mouse wheel, click, arrow keys for 1-pixel moves) allows a pixel-precise centring, with live previews of the four templates. Templates are saved directly in `output_results/_FM_templates` (also proposed by default as template folder for the detection).
- **Automatic detection (2.3) – fixed:** when the first match was weak, the second try (larger search window) converted its result with the offsets of the first window, giving FM coordinates **400 px off** for the right/bottom corners. This is fixed; datasets processed with the previous version can be checked with the review tool below.
- **Automatic detection – simplified outputs:** `corners/_all_fiducials` (one figure per image), `Out_fiducialmarks.csv` and `Out_fiducialmarks_TobeChecked.csv`. The `_To_Be_Checked` figures (template box drawn at a wrong position), the `cornerToCheck` copies and the per-corner debug images are no longer created. The final check now tests the geometry of the four FMs of each image (they must form a parallelogram, whatever the rotation of the scan).
- **New: Review / correct FM detection.** Shows, one by one, the corners with a low matching score, the images whose four FMs are geometrically inconsistent and the images without coordinates (optionally all corners), with a corner view and a zoom view. Markers show the automatic detection and the position expected from the three other FMs.
  - `Enter`: keep / save the position and go to the next corner (a correct detection only needs `Enter`)
  - click: set the FM centre · mouse wheel: zoom · right drag: pan · arrows: move 1 pixel (`Shift`: 10)
  - `E`: use the expected position · `R`: reset · `S`: skip · `Backspace`: previous · `A`: also review the other corners of the image
  - Each review is saved immediately in `Out_fiducialmarks.csv` (a backup is made before the first change) and logged in `Out_fiducialmarks_review_log.csv`.
  - **Select images…**: review the four FMs of images chosen manually, e.g. images that look badly reprojected. They can be selected directly among the outputs (`B_Reprojected`, `C_Resampled` or `_preview`); *Reload list* goes back to the automatic list.
  - **Corrections are applied on the next run:** Tool 3 records the FM coordinates used for each image (`_fiducialmarks_used.csv` in its output folder) and reprojects again the images whose FMs changed since (for outputs made before this record existed: images reviewed after their reprojection). Tool 4 resamples again the images reprojected after their resampling. The other images are skipped as before.
- Images are read as 8-bit grayscale for the detection (identical results, 1/3 of the memory).

#### Fiducial marks as mid-side notches (e.g. the 1949 photos)
Some cameras have no fiducial targets in the corners, but notches cut in the middle of the four sides of the image frame. Select **Fiducial marks: Mid-side notches** in Tool 2 (default: *Corners*); the option is used by the template creator, the detection, the review tool and the reprojection.
- **Templates:** in the template creator, click near the tip of the top, right, bottom and left notches (half width 250 pix by default: mostly the notch shape). Several template sets can be created (e.g. one per camera or scanning batch); the best match is kept.
- **Detection:** the notches are not matched on their grey values, dominated by the image content next to them, but on the shape of the dark film frame, in narrow windows in the middle of each side. The shape of the four notches is then learnt on the confident detections of all images, and the notches with a low score or at an unusual position are searched again around their position predicted from the other notches; if they are still not found, the predicted position is kept (accuracy 0).
- **Review:** three reliable notches are enough for the reprojection, so the review tool only lists the images with less than three reliable notches, or with an inconsistent geometry. The expected position (cyan circle) is predicted from the other notches.
- **Reprojection:** no camera model is needed: the target positions of the notches are learnt from the dataset, and each image is reprojected with an affine transform fitted on its reliable notches (score ≥ 0.88 or reviewed).
- **A notch missing on the scans** (e.g. no top notch on the 1949 photos of box X0039: the top frame edge is outside the scan): create the templates of the three other notches only (the template creator asks for confirmation). The missing notch is not searched, its position is predicted, and the reprojection uses the three other notches. In the review tool, a notch that is not visible on an image can be marked as such (`N`): it is then excluded from the reprojection.
- The layout used is saved in `Out_fiducialmarks_layout.txt`; mixing layouts in one folder is refused. In `Out_fiducialmarks.csv`, FM 1–4 are then the top, right, bottom and left notches.
- Tool 1 now stops if two input images have the same name (their outputs would overwrite each other).

#### Tools 3 and 4 – Reprojection and resampling
- **Faster:** the reprojection runs in parallel.
- **New option *Directly at output resolution*:** reprojects the cropped images directly at the output resolution, with sharpening and histogram calibration, i.e. Tools 3 + 4 in one step without writing the full-resolution `B_Reprojected` images (about twice as fast, and ~230 MB less written per image). The geometry is identical to the two-step processing (< 0.02 px) and the images are visually identical.
- **Fixed:** the *Histogram calibration* and *Sharpening intensity* options chosen in the GUI are now applied (the default values were always used).

#### Parallel processing and memory
Each worker holds one full-resolution image in memory (~0.5–1.5 GB for a 1600 dpi scan). The number of images processed in parallel is limited to 4 by default and can be changed with `num_cores_crop` (Tool 1) and `num_cores` (Tool 3).


----------------

*&copy; Royal Museum for Central Africa / Vrije Universiteit Brussel – 2020-2026*
