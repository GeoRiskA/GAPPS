
"""


"""

import os, glob
import subprocess

otb_folder = r'C:\Users\adille\Desktop\Softwares\OTB-9.1.0-Win64\bin'
###########################################################
dem_folder = r'D:\ADille_Data\GIS\DEM_Lite\Copernicus\COPERNICUS_DEM_WGS84'
epsg_code = '32735'

# Pleiades
pleiades_main_folder = r'D:\ADille_Data\GIS\Optical_Imagery\Pleiades_Bukavu_20230913_mono\7176891101'
pleiades_main_folder = r'G:\PROCESSING\LACTOSE\Pleiades_Bukavu_v2024\Pleiades_Bukavu_201303_stereo\FCGC600053727\IMG_PHR1B_MS_002'

#############################################################

# list all files in the input directory and subdirectories
files = glob.glob(os.path.join(pleiades_main_folder, '**', 'IMG*.JP2'), recursive=True)
files = glob.glob(os.path.join(pleiades_main_folder, '**', 'DIM*.XML'), recursive=True)

print(f'\n > I found {str(len(files))} Pléiades image(s) to process')

# First convert images to tif
for i, image in enumerate(files):
    print(f'\n > processing {os.path.basename(image)} [{str(i+1)}/{str(len(files))}]')

    # launch OTB
    cmd = [os.path.join(otb_folder, 'otbcli_DynamicConvert'), '-in', image, '-out', os.path.join(pleiades_main_folder, f'{os.path.basename(image).split(("."))[0][4:]}.tif')]
    # using gdal
    cmd = f'gdal_translate -of GTiff -co COMPRESS=NONE -co BIGTIFF=IF_NEEDED {image} {os.path.join(pleiades_main_folder,os.path.basename(image).split(("."))[0][4:])}.tif'

    print(cmd)
    subprocess.check_call(cmd)

# launch otbcli_OrthoRectification
for i, image in enumerate(files):
    print(f'\n > processing {os.path.basename(image)} [{str(i+1)}/{str(len(files))}]')

    # launch OTB
    cmd = [os.path.join(otb_folder, 'otbcli_OrthoRectification.bat'), '-io.in', image,
           '-io.out', os.path.join(pleiades_main_folder, f'{os.path.basename(image).split(("."))[0]}_ortho.tif'),
           '-map', 'epsg', '-map.epsg.code', epsg_code,'-elev.dem',dem_folder , '-opt.ram', '4092']
    print(cmd)
    subprocess.check_call(cmd)

