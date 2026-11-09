<div align="center">
	<img src="https://github.com/GeoRiskA/GAPPS/blob/main/assets/GAPPS_logo_forGUI.png?raw=true">
</div> 

<h3 align="center">
<i>Prepare your scanned aerial photographs for photogrammetric processing!</i>
</h3>

<br>

**GAPPS is a set of tools to prepare scanned aerial photographs for photogrammetric processing. It allows strandardizing the size/resolution of the photographs, as well as orienting them to get the centre of perspective of the photos at the centre of the digital image.**  

**GAPPS offers 6 main tools:**  
- **1. Canvas sizing:**  This first tool makes sure that all the scanned images have the same dimensions, by adding pixel rows or columns if needed, or crops them to the photo frame.  
- **2. Fiducial mark detection:** This group of tools is used to create fiducial mark templates by clicking on an image, to automatically detect the fiducial marks on the sides of the photographs, and to review/correct the detections manually.  
- **3. Reprojection:** This tool exploits the position of the fiducial marks to reproject and crop the images, to get images devoid of black margins, with their centre corresponding to the centre of perspective.  
- **4. Resize:** This tool downsamples and sharpens the reprojected images, for better photogrammetric results.  
- **5. Mask creation:** This tool creates a mask image that will hide the fiducial marks visible within the images during the photogrammetric processing.  
- **6. Shape2GCPs (new in v0.5.0):** This tool locates each photograph on OpenStreetMap from a few roads, lake shores or rivers drawn on it, and produces approximate ground control points (GCPs) to seed the markers in Agisoft Metashape.

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54) [![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

-------

***Software Management and Coordination:***  
- Prof. Dr. Benoît SMETS – Royal Museum for Central Africa (RMCA) / Vrije Universiteit Brussel (VUB) – BE  

***Contributors:***. 
- Prof. Dr. Benoît SMETS – Royal Museum for Central Africa (RMCA) / Vrije Universiteit Brussel (VUB) – BE  
  > *Main tools, Graphical User Interface*   
- Dr. Antoine DILLE – Royal Museum for Central Africa (RMCA) / Vrije Universiteit Brussel (VUB) – BE  
  > *Image resampling/sharpening tool, Fiducial Mark Detection, Shape2GCP tool, Graphical User Interface*   
- Mr. Paul BARRIERE - Former student of ENSG-Géomatique – FR
  > *Fiducial Mark Detection*  
- Ms. Amélie MAGINOT – Former student of ENSG-Géomatique – FR
  > *Fiducial Mark Detection, Graphical User Interface*  

***Citation:*** *(in progress)*  

When using GAPPS or part of the scripts developed in GAPPS, please cite the following references in you work:  

- ***The repository:*** Smets, B., Dille, A., 2026.  GAPPS — GeoRiskA Airphoto Pre-Processing Suite. Version 0.5.1 Zenodo XXXX
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

GAPPS also requires the following Python packages to run: `opencv, matplotlib, joblib, pillow, numpy, pandas, scikit-image, scikit-learn`, and for Tool 6 `geopandas, shapely, pyogrio, pyproj, scipy, rasterio` (+ optionally `gdal`). They are listed in `environment.yml` (conda) and `requirements.txt` (pip), and are installed in a dedicated environment during the installation procedure.

### Installation of GAPPS

GAPPS is a Python application and should be installed in **its own environment** (never in the base Python, nor in an environment used for other software). Two ways are possible:

- **Recommended: a conda environment created from `environment.yml`** (section *Installation with conda* below, same procedure on Windows, macOS and Linux). All the packages come from conda-forge, so the compiled libraries used by Tool 6 (GDAL, PROJ, GEOS) and by OpenCV are built to work together, and the conda solver keeps all the versions compatible (e.g. numpy). This is the safest installation, in particular on Windows.
- **Alternative: a Python virtual environment `.venv/` inside the GAPPS folder, with pip** (sections *Installation on Linux / macOS / Windows* below). It works with the Python installed on the computer, but pip installs each package from its own pre-compiled wheel and does not check the packages already installed: never `pip install` other packages in this environment afterwards, and do not mix pip and conda in the same environment.

The launchers (`Launch_GAPPS_Win.bat`, `Launch_GAPPS_Mac.command`) use `.venv/` if it exists in the GAPPS folder, otherwise the conda environment `gapps`.

<br>

## INSTALLATION WITH CONDA (RECOMMENDED – Windows, macOS, Linux)

#### 1. Install conda (once)
If no conda distribution is installed yet, install **Miniforge** (conda + mamba, with conda-forge as default channel): https://conda-forge.org/download/ – on Windows, keep the default options and use the *Miniforge Prompt* for the commands below. An existing Anaconda, Miniconda or Mambaforge installation also works.

#### 2. Download GAPPS from GitHub
```bash
git clone https://github.com/GeoRiskA/GAPPS.git
cd GAPPS
```
(or download the ZIP from GitHub, unzip it in its preferred location, and open the terminal / Miniforge Prompt in that folder).

#### 3. Create the environment
```bash
conda env create -f environment.yml
```
This creates the environment `gapps` (a few minutes; `mamba env create -f environment.yml` is faster). Check it:
```bash
conda activate gapps
python -c "import cv2, geopandas, rasterio, tkinter; print('GAPPS environment OK')"
```

#### 4. Set the folders and launch GAPPS
Edit `GAPPS_config.json` (input and output folder paths), then:
```bash
conda activate gapps
python run_gapps.py
```
or double-click `Launch_GAPPS_Win.bat` (Windows) / `Launch_GAPPS_Mac.command` (macOS), which find the `gapps` environment automatically (Miniforge, Mambaforge, Miniconda or Anaconda installed in the usual places). On Linux, see [LaunchGAPPS_Linux_CreationGuide.md](LaunchGAPPS_Linux_CreationGuide.md).

#### 5. Update after pulling a new GAPPS version
```bash
git pull
conda env update -n gapps -f environment.yml --prune
```

<br>

<br>

## INSTALLATION ON LINUX (Ubuntu) – ALTERNATIVE WITH PIP (.venv)

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

## INSTALLATION ON MAC OS – ALTERNATIVE WITH PIP (.venv)

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

## INSTALLATION ON WINDOWS 11 – ALTERNATIVE WITH PIP (.venv)

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

## TOOL 6 – SHAPE2GCPs: LOCATING THE PHOTOS ON OPENSTREETMAP (new in v0.5.0)

Historical photographs have no georeference, and finding the first GCPs of each photo in Metashape is slow. Shape2GCPs locates each photo from a few lines drawn on it — roads, lake shores, rivers — by matching their shape against OpenStreetMap (OSM), and writes approximate GCPs (image pixel ↔ ground coordinate + height) that are imported as markers in Metashape, where they only need to be checked and nudged.

Launch it with *Launch Shape2GCPs...* (Tool 6 of the main menu; it opens `C_Resampled` if it exists, otherwise the input folder) or on its own:
```bash
python GUI_scripts/GAPPS_interface_Shape2GCPs.py <image_folder> <output_results_folder>
```

#### Workflow
1. **Project (once):** AOI polygon, OSM extract, and optionally a DEM and the Metashape camera calibration (strongly recommended, see *Camera model* below). The OSM extract is made once per area from the Geofabrik country GeoPackage (`congo-democratic-republic-latest-free.gpkg`) with *Clip country OSM to AOI…*; it keeps the layers `roads` (without tracks), `water` (lakes, reservoirs, river areas; no wetlands) and `waterways`.
   - **Known GCPs (optional, recommended for dense towns):** *Import Metashape markers…* reads the markers already placed in Metashape (*File > Export > Export Markers*, XML; lon/lat or a projected CRS). The images with markers are highlighted in the list (column *mk*), the markers are drawn on the photos (magenta), and the tool points to the image with the most markers: **start with it**. With 2 markers or more on an image no search is needed (seconds instead of minutes); with 1 marker the search is limited to the area the photo can cover around it. The markers stay in the fits as strong constraints, which keeps dense street networks from pulling the match away.
2. **Draw** a few features on the photo: `1` road, `2` lake shore, `3` river. Click to add points, double-click or `Enter` to finish a line, `Backspace` undo point, `Esc` cancel, `X` delete mode (click a line), `D` back to drawing. Mouse wheel: zoom, right/middle drag: pan, `F`: fit. Lines digitised in QGIS on the raw image can be imported (*Import lines…*). Good features: long, curved, still existing today (main roads, hairpins, junctions, shorelines, bays). Spread them over the photo.
3. **Match** (`M`). The OSM roads (yellow) and water (cyan, dashed) are then drawn over the photo with the proposed GCPs (`R03` road, `L01` lake, …): a good match is obvious. Other candidates can be chosen in the list; *Open QA figure* shows an overview.
4. **Decide:** `A` accept and next, `S` skip the image (and optionally remove its GCPs from the table), `PageDown`/`PageUp` next/previous image. Everything is saved continuously: the tool can be closed and resumed.
5. **Metashape:** run `GAPPS_tools/GAPPS_Tool_06c_Metashape_ImportGCPs.py` in Metashape (*Tools > Run Script*, argument: `.../F_Shape2GCPs/osm_gcps_all.csv`). Markers are created on all the images of the active chunk listed in the table, with their reference coordinates and accuracies. Projections are blue (unpinned): check each marker and drag it onto the exact feature, which pins it (green). Re-running updates the markers instead of duplicating them.

#### How it works
- **Oriented shape matching.** The drawn lines and the OSM features are both turned into *oriented* line fields (Gaussian-blurred `exp(2iφ)`, φ = local direction). A placement only scores where the lines overlap *and* run in the same direction, so dense street networks and crossing roads cancel out instead of attracting every match.
- **Global search.** For every scale (GSD) and rotation, the drawn lines are rasterised and cross-correlated with the OSM field of the whole AOI by FFT (all translations at once); roads, lake shores and rivers are separate channels of the same transform (lake/river points weigh ×2: shorelines change much less than roads since the 1950s). The best positions are refined on a finer grid, then by ICP (iterative closest point, orientation-aware).
- **Ranking: distinctness.** Each candidate is compared with ~24 slightly shifted/rotated copies of itself. A true match is a sharp peak (the copies fit much worse); a placement in a dense town is a plateau (the copies fit almost as well). This *distinctness* ranks the candidates and flags ambiguous results; it measures how unique the location is, not its accuracy.
- **Camera model (relief and tilt).** A photo is a central perspective: with a flat (similarity) fit, the relief displaces the features by tens of metres towards the edges (25–30 m on the hills west of Bukavu, ~5,800 m flying height). With a DEM and the Metashape calibration, the flat match is refined into the full camera model — camera position, height and tilt (6 parameters), Metashape's frame lens model (f, cx, cy, k1–k4, p1, p2, b1, b2) and the DEM heights — by point-to-line ICP in image space between the drawn lines and the OSM features projected through the camera. On photo 5828_104 the median road misfit (left / centre / right third) went from 29 / 6 / 26 m to 5 / 3 / 11 m. The GCPs then carry their DEM height, and the overlay is projected through the camera.
- **Fit to OSM.** With the final model: share of the drawn lines within 15 m of a same-direction OSM feature (per feature and in total), median distance, and left/centre/right medians. Shown in the result panel (green ≥ 70 % and median ≤ 10 m, orange ≥ 40 %, red below) and in the *fit %* column of the image list. Features that disappeared or moved since the photo lower it locally; a wrong match gives a low fit everywhere.
- **GCPs.** Placed along the matched lines (12 along roads, 4 along lakes/rivers by default), evenly spread and preferably on bends (a point on a straight stretch is undetermined along it); only where the line fits OSM. The ground coordinate is the matched OSM point (with its DEM height), the pixel is the drawn point; the accuracy written for Metashape is the larger of the fit RMSE and the local residual (≥ 5 m).
- **Known GCPs (anchors).** With ≥ 2 markers the fit starts from the similarity defined by the markers; with 1 marker the search area is limited and the candidates that do not put the marker within 250 m of its position are rejected (flag `ANCHOR_MISMATCH` otherwise). In the ICP and in the camera model the markers have, together, the same weight as all the drawn points (`--anchor-weight 1`); their residuals are reported in the log. Markers are not written again as GCPs (they are already in Metashape).
- **Priors from the images already matched.** GSD (median ±25 %), rotation (same as the nearest matched image, or −90°, −180°, +90°, each ±15°) and location (within 15 km of the nearest matched image; same strip and closest frame number first). The first image needs a full search (a few minutes over a 100 × 100 km AOI); the next ones take seconds to a minute. If a prior-based result is doubtful (`AMBIGUOUS`, `LOW_CONTRAST`, `GSD_AT_SEARCH_BOUND`), the search is automatically widened (whole AOI, then no priors).

#### Important parameters
| Setting (GUI) | Command-line option | Default | Role / advice |
|---|---|---|---|
| AOI polygon | `--region` | – | Search area (any CRS); the working CRS is the UTM zone of the AOI. |
| OSM extract | `--osm` | – | GeoPackage with `roads`, `water`, `waterways` (Clip country OSM to AOI…). |
| DEM | `--dem` | – | e.g. Copernicus GLO-30 (any CRS). Needed for the camera model and the GCP heights. |
| Camera calibration | `--camera-xml` | – | Metashape *Tools > Camera Calibration > Export* (frame XML), same image size as the photos (8100 × 8100 for `DownSharp`). With the DEM: camera model ON. |
| GSD start range | `--gsd-range` | 0.5–2.0 m/px | Scale range of the first (full) search. Narrow it if known (≈0.6–0.9 for the 1950s Kivu photos at 8100 px) — but not too much: a result at the edge of the range is flagged `GSD_AT_SEARCH_BOUND`. |
| Rotation window ± | `--rotation-halfwidth` (with `--rotation-centers`) | 15° | Width of the rotation windows around the neighbour's rotation and ±90°/180°. |
| Search radius around neighbour | `--prior-radius` | 15 km | Location prior. Increase for a new strip far from the matched ones. |
| GCPs / image, + along lake/river | `--n-gcps`, `--aux-gcps` | 12, 4 | Number of GCPs per image. |
| Import Metashape markers… | `--anchors` (CSV: label, px_col, px_row, lon, lat, z) | – | Known GCPs of the image. ≥ 2: no search; 1: search limited around it. |
| – | `--anchor-tol` | 250 m | Candidates placing a marker further than this (flat fit) are rejected. |
| – | `--anchor-weight` | 1 | Total weight of the markers relative to all the drawn points. |
| – | `--inlier-dist` | 30 m | Distance under which a drawn point is considered to match OSM (ICP, GCP selection). Lake/river: ×1.5 (`--aux-inlier-factor`). |
| – | `--fit-dist` | 15 m | Distance used by the *fit to OSM* score. |
| – | `--aux-weight` | 2 | Weight of lake/river points relative to road points. |
| – | `--exclude-classes` / `--include-classes` | footways, paths, steps… excluded | OSM road classes used. |
| – | `--model` | similarity | Flat model when no camera model (similarity or affine). |

The matching engine can also be used without the interface: `python GAPPS_tools/GAPPS_Tool_06_Shape2GCPs.py --help` (single image; `--road`, `--aux` lines in pixel coordinates, e.g. digitised in QGIS on the raw image).

Metashape import options (*Arguments* box of *Run Script*): `--pinned` (green flags directly — only for matches already checked), `--acc-z 15` (vertical accuracy, default 50 m), `--only <camera labels>`, `--set-chunk-crs EPSG::32735`. A chunk in *Local Coordinates* is switched to the UTM zone of the table; WGS 84-based chunks get the coordinates directly (no datum conversion).

#### Outputs (`output_results/F_Shape2GCPs`)
- `osm_gcps_all.csv`: GCPs of all the images (label, camera, pixel, lon/lat, height, UTM x/y, accuracy, feature, flags); the rows of an image are replaced when it is matched again. Marker labels: `osm_<strip>_<frame>_<feature>_NN`, e.g. `osm_5828_170_road_03`.
- `match/<image>/`: GCP table, transform and candidates (JSON), QA figure, GeoPackage (georeferenced lines, GCPs, footprint).
- `features/<image>.geojson`: the drawn lines (pixel coordinates, QGIS convention x = col, y = −row); `shape2gcps_project.json`: settings and status of every image.

#### Limits
- The GCPs are seeds (typically 5–15 m with the camera model, more without): always check them in Metashape.
- A short or straight feature can fit several places (flag `AMBIGUOUS`): add another feature, ideally a shoreline or a junction.
- The camera calibration must come from the same camera and image size; without it, a 2D fit cannot follow the relief in hilly areas.

<br>

## WHAT'S NEW IN v0.5.1 (November 2026)

- **Installation with conda (recommended):** new `environment.yml` (conda-forge); the launchers use `.venv/` if present, otherwise the conda environment `gapps`.

- **Tool 6 – known GCPs:** import of the Metashape markers (XML) as anchors: start image proposed, no search with ≥ 2 markers, limited search with 1, markers kept as constraints in the flat and camera fits; markers drawn on the photo and counted in the image list.
- **Tool 6 – fixes:** *fit to OSM* score and drawing of long OSM outlines (e.g. the lake shore) were missing from v0.5.0; the image list scrolls with the mouse wheel (and has a scrollbar); river GCPs are labelled `Ri..` on the photo (roads `R..`, lakes `L..`).
- **Main menu:** scrollable window, limited to the screen height (Tool 6 was out of reach on small screens).

## WHAT'S NEW IN v0.5.0 (November 2026)

- **New Tool 6 – Shape2GCPs** (see the section above).
- Earlier changes of the development branch (October 2026):

These changes (development branch `Dev_202610`) merge `Dev_202603` into v0.4.0 and add the following.

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
- **All the template sets are used** (the best match is kept for each corner): before, only the first template of each corner was used, so additional sets (e.g. made for a part of the dataset where the marks look different) were ignored. The matching is done coarse to fine (half resolution, then refined at full resolution).
- **Folders mixing scan resolutions** (e.g. 1600 and 2400 dpi): the templates are rescaled to the size of each image. The template creator now records the size of the image the templates are cut from (`Center_Fiducials.txt`); older templates are assumed to come from an image of the typical size of the folder. The search window grows with the image size.
- **Cross-shaped marks** (e.g. the X of Wild cameras): the centre is refined at the intersection of the two lines of the cross. The bright disc and the dark frame around the cross, which dominate the template matching, do not always have the same position relative to the cross (different cameras, uneven illumination of the marks): the matched position could be tens of pixels off the cross. Results obtained before can be re-centred without running the detection again (the corners reviewed manually are kept): `recentre_on_cross(image_folder, template_folder)` in `GAPPS_Tool_02c_AutomaticFiducialDetection.py`.
- Template half width: keep it small (about 250 pix at 1600 dpi: the mark and a dark margin). Larger templates include part of the photo, which changes from image to image and lowers the matching scores.
- When the marks look different in part of the dataset (e.g. uneven illumination of the fiducial marks in one film roll), create one more template set from an image of that part.

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
- **No input resolution to give:** the scan resolution of each image is measured on its fiducial marks (distance between the marks in the image / their distance on the photograph: camera model for corner marks; for mid-side notches, learnt from the dataset with the dpi tags of the scans, recorded by Tool 1 in `_scan_resolution.csv`). A folder can thus mix scans made at different resolutions, and wrong dpi tags (e.g. 2400 dpi scans tagged 1500 dpi) do no harm; the resolutions found, and the scans whose tag differs, are listed in the console. With *Directly at output resolution*, all the images are reprojected onto the output resolution grid; otherwise each image is reprojected at its own (nominal) scan resolution, written in its TIFF tags, and Tool 4 reads it to resample the image. The outputs of Tools 3 and 4 carry their dpi.
- **New option *Directly at output resolution*:** reprojects the cropped images directly at the output resolution, with sharpening and histogram calibration, i.e. Tools 3 + 4 in one step without writing the full-resolution `B_Reprojected` images (about twice as fast, and ~230 MB less written per image). The geometry is identical to the two-step processing (< 0.02 px) and the images are visually identical.
- **Fixed:** the *Histogram calibration* and *Sharpening intensity* options chosen in the GUI are now applied (the default values were always used).
- Direct reprojection: the downsampling factor is measured on the fiducial marks of each image, so that scans made at another resolution than the nominal one are also correctly downsampled.

#### Parallel processing and memory
Each worker holds one full-resolution image in memory (~0.5–1.5 GB for a 1600 dpi scan). The number of images processed in parallel is limited to 4 by default and can be changed with `num_cores_crop` (Tool 1) and `num_cores` (Tool 3).

----------------

*&copy; Royal Museum for Central Africa / Vrije Universiteit Brussel – 2020-2026*
