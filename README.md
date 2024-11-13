<div align="center">
	<img src="https://github.com/GeoRiskA/GAPPS/blob/main/GAPPS_logo_forGUI.png">
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
GAPPS is coded in Python 3 (Python 3.8 and 3.12 have been tested), and requires the following Python packages to run: `opencv matplotlib tk pathlib joblib pillow numpy pandas scikit-image subprocess`.

A suitable Python environment can be set up using conda and the packages installed from conda-forge:

            conda create --name gapps python=3.12
            conda activate gapps
            conda config --env --add channels conda-forge
            conda config --env --set channel_priority strict
            conda install opencv matplotlib tk pathlib joblib pillow numpy pandas scikit-image subprocess

Would you have troubles with the installation of the modules using conda, we recommend using mamba (https://github.com/mamba-org/mamba).
It also uses Sun Valley ttk theme (https://github.com/rdbende/Sun-Valley-ttk-theme) for the tKinter theme. It can be installed with `pip install sv-ttk`.
## HOW TO RUN GAPPS  

In progress ...  

----------------

*&copy; Royal Museum for Central Africa / Vrije Universiteit Brussel – 2020-2024*
