<div align="center">
	<img src="https://github.com/GeoRiskA/GAPPS/blob/main/assets/GAPPS_logo_forGUI.png?raw=true">
</div> 

<h3 align="center">
<i>Prepare your scanned aerial photographs for photogrammetric processing!</i>
</h3>

<br>

**GAPPS is a set of tools to prepare scanned aerial photographs for photogrammetric processing. It allows strandardizing the size/resolution of the photographs, as well as orienting them to get the centre of perspective of the photos at the centre of the digital image.**  

**GAPPS offers 5 main tools:**  
- **1. Canvas sizing:**  This first tool makes sure that all the scanned images have the same dimensions, by adding pixel rows or columns if needed.  
- **2. Fiducial mark detection:** This group of tools is used to automatically or manually detect the fiducial marks on the sides of the photographs.  
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

- ***The repository:*** Smets, B., Dille, A., Barrière, P., Maginot, A., 2024.  GAPPS — GeoRiskA Airphoto Pre-Processing Suite. Zenodo XXXX
- ***The publication (in preparation):*** XXXX

--------------

## INSTALLATION PROCEDURE  

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

GAPPS also requires the following Python packages to run: `opencv, matplotlib, joblib, pillow, numpy, pandas, scikit-image`. They will be installed in a virtual environment during the installation procedure.

### Installation of GAPPS

GAPPS is a Python application and should be installed inside its own virtual environment. The recommended structure is to keep the virtual environment inside the GAPPS folder as `.venv/`.

The `.venv/` folder does not come from Github. It is created locally during installation.

### LINUX (Ubuntu)

#### 1. Download GAPPS from GitHub
Open a terminal and clone the repository:
```bash
git clone https://github.com/YOUR_USERNAME/GAPPS.git
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
./.venv/bin/python -m pip install --upgrad pip
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

### MAC OS

#### 1. Download GAPPS from GitHub
Open Terminal and clone the repository:
```bash
git clone https://github.com/YOUR_USERNAME/GAPPS.git
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

### WINDOWS 11

#### 1. Download GAPPS from GitHub
Open PowerShell and clone the repository:
```powershell
git clone https://github.com/YOUR_USERNAME/GAPPS.git
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




----------------

*&copy; Royal Museum for Central Africa / Vrije Universiteit Brussel – 2020-2026*
