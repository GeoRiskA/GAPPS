"""
========================================================================================
                     GAPPS – GeoRiskA Airphoto Pre-Processing Suite
========================================================================================
                       = MANUAL FIDUCIAL MARK CORRECTION TOOL =

Description: This script aims to correct the coordinates of the fiducial marks
             (4 corners) of a set of aerial images. The script reads the coordinates of
             the fiducial marks from a CSV file and corrects them according to the
             user's input. The corrected coordinates are saved in a new CSV file.

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

import pandas as pd
import cv2
import os, sys
import json

def Main_correction_fid_marks(dataset, path, p, black_stripe_location):
    fidFile = pd.read_csv(os.path.join(path, f'_fiducial_marks_coordinates_{dataset}.csv'), sep=",", encoding='utf-8').copy()
    correctfidFile = pd.read_csv('manual_fiducial_marks.csv')

    newfidFile = os.path.join(path, f'new_fiducial_marks_coordinates_{dataset}.csv')
    columns = list(fidFile.columns)

    for i in range(len(fidFile['name'])):
        imgName = fidFile.iloc[i]['name']
        fid = fidFile.loc[i]

        L = [correctfidFile.iloc[j] for j in range(len(correctfidFile['image'])) if correctfidFile.iloc[j]['image'] in imgName]
        D = pd.DataFrame(columns=columns)
        for l in L:
            D = D.append(l)

        for d in range(len(D)):
            fid = correct_fid(fid, D.iloc[d].to_dict(), imgName, path, p, black_stripe_location)

        new_line = pd.DataFrame(dict(fid), index=[i])
        fidFile.update(new_line)

    fidFile.to_csv(newfidFile, mode='w', header=list(fidFile.columns), sep=",", index=False)
    print(fidFile)

def correct_fid(fid, correction, imgName, path, p, black_stripe_location):
    img = cv2.imread(os.path.join(path, f'{imgName}.tif'))

    cornerW = correction['corner width']
    cornerH = correction['corner height']
    x = correction['x']
    y = correction['y']
    h, w = img.shape[0], img.shape[1]

    if correction['corner'] == 'top_left':
        fid['X1'] = x
        fid['Y1'] = y
    elif correction['corner'] == 'top_right':
        fid['X2'] = w - cornerW + x
        fid['Y2'] = y
    elif correction['corner'] == 'bot_right':
        fid['X3'] = w - cornerW + x
        fid['Y3'] = h - cornerH + y
    elif correction['corner'] == 'bot_left':
        fid['X4'] = x
        fid['Y4'] = h - cornerH + y

    if 'top' in black_stripe_location:
        if correction['corner'] == 'top_left':
            fid['Y1'] += h * p
        if correction['corner'] == 'top_right':
            fid['Y2'] += h * p
    if 'bottom' in black_stripe_location:
        if correction['corner'] == 'bot_right':
            fid['Y3'] += h * p
        if correction['corner'] == 'bot_left':
            fid['Y4'] += h * p
    if 'left' in black_stripe_location:
        if correction['corner'] == 'top_left':
            fid['X1'] += w * p
        if correction['corner'] == 'bot_left':
            fid['X4'] += w * p
    if 'right' in black_stripe_location:
        if correction['corner'] == 'top_right':
            fid['X2'] -= w * p
        if correction['corner'] == 'bot_right':
            fid['X3'] -= w * p

    return fid

if __name__ == '__main__':
    with open('GAPPS_config.json', 'r') as f:
        config = f.read()
    user_config = json.loads(config)

    output_results_folder = user_config['output_results_folder_path']
    dataset = os.path.basename(output_results_folder)
    p = float(sys.argv[1])
    black_stripe_location = sys.argv[2]

    Main_correction_fid_marks(dataset, output_results_folder, p, black_stripe_location)
