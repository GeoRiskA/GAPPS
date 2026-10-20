"""
========================================================================================
                     GAPPS – GeoRiskA Airphoto Pre-Processing Suite
========================================================================================
                    = REVIEW OF THE FIDUCIAL MARK DETECTIONS =

Description: Functions used to review the automatic fiducial mark (FM) detection
    (Tool 2c) and to correct it manually (GUI: GAPPS_interface_FM_review.py).

    The corners to review are:
      - 'score'    : corners whose template matching score is below the threshold
                     (listed in Out_fiducialmarks_TobeChecked.csv by Tool 2c);
      - 'geometry' : images whose four FMs do not form a parallelogram (the four FMs of
                     a camera are the corners of a rectangle, which remains a
                     parallelogram after scanning, whatever the rotation of the scan).
                     The closure error |TL + BR - TR - BL| reveals a wrong FM; the most
                     likely wrong corner is the one furthest from its usual position in
                     the (cropped) image. The position "expected" from the three other
                     FMs (parallelogram completion) is given as a hint;
      - 'missing'  : images without FM coordinates (all four corners).

    Each review is saved immediately in Out_fiducialmarks.csv (a backup is made before
    the first change) and logged in Out_fiducialmarks_review_log.csv; reviewed corners
    are not proposed again.

Copyright:
    RMCA — Royal Museum for Central Africa (Tervuren, BELGIUM)
        Natural Hazards and Cartography (GeoRiskA), Dpt. of Earth Sciences
    VUB — Vrije Universiteit Brussel (Brussels, BELGIUM)
        Physical Geography (FARD), Dpt. of Geography
    © 2026

Software authorship:
    - Antoine DILLE (RMCA)

Last update: 2026-10-20
========================================================================================
"""

import os
import shutil
import time

import numpy as np
import pandas as pd

CORNERS = ['top_left', 'top_right', 'bot_right', 'bot_left']  # FM 1, 2, 3, 4 of Out_fiducialmarks.csv
IMAGE_EXTENSIONS = ('.tif', '.tiff', '.jpg', '.jpeg')
FM_CSV = 'Out_fiducialmarks.csv'
TOBECHECKED_CSV = 'Out_fiducialmarks_TobeChecked.csv'
REVIEW_LOG_CSV = 'Out_fiducialmarks_review_log.csv'
FM_COLUMNS = ['name', 'X1', 'Y1', 'X2', 'Y2', 'X3', 'Y3', 'X4', 'Y4', 'top_left_accuracy',
              'top_right_accuracy', 'bot_right_accuracy', 'bot_left_accuracy']
MIN_GEOMETRY_TOL = 60.0  # minimum closure error (pix) flagged by the geometry check


def stem(name):
    """Image name without extension (e.g. '54102_088_Cropped.tif' -> '54102_088_Cropped')."""
    name = os.path.basename(str(name))
    root, ext = os.path.splitext(name)
    return root if ext.lower() in IMAGE_EXTENSIONS else name


# 1. Reading and writing the FM coordinates
# ------------------------------------------

def read_fm(fm_csv):
    """Read Out_fiducialmarks.csv (column names stripped, one row per image, indexed by image name)."""
    if not os.path.isfile(fm_csv):
        return pd.DataFrame(columns=FM_COLUMNS).set_index('name', drop=False)
    df = pd.read_csv(fm_csv)
    df.columns = df.columns.str.strip()
    df = df.dropna(subset=['name'])
    df['name'] = df['name'].astype(str).map(stem)
    df = df.drop_duplicates(subset='name', keep='last')
    return df.set_index('name', drop=False)


def write_fm(fm_csv, df):
    """Write Out_fiducialmarks.csv, keeping the column names of the existing file (with their spaces)."""
    original_columns = None
    if os.path.isfile(fm_csv):
        original_columns = list(pd.read_csv(fm_csv, nrows=0).columns)
    out = df.reset_index(drop=True)[FM_COLUMNS].copy()
    if original_columns and [c.strip() for c in original_columns] == FM_COLUMNS:
        out.columns = original_columns
    tmp = fm_csv + '.tmp'
    out.to_csv(tmp, index=False)
    os.replace(tmp, fm_csv)  # atomic: the file is never left half written


def backup_fm(fm_csv):
    """Copy Out_fiducialmarks.csv to Out_fiducialmarks_backup_<date-time>.csv (once per review session)."""
    if os.path.isfile(fm_csv):
        backup = f"{fm_csv[:-4]}_backup_{time.strftime('%Y%m%d-%H%M%S')}.csv"
        shutil.copy(fm_csv, backup)
        return backup
    return None


def read_review_log(image_folder):
    path = os.path.join(image_folder, REVIEW_LOG_CSV)
    if os.path.isfile(path):
        return pd.read_csv(path)
    return pd.DataFrame(columns=['time', 'name', 'corner', 'reason', 'x_auto', 'y_auto', 'x', 'y', 'action'])


def log_review(image_folder, name, corner, reason, auto_xy, xy, action):
    path = os.path.join(image_folder, REVIEW_LOG_CSV)
    line = pd.DataFrame([{'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'name': name, 'corner': corner,
                          'reason': reason,
                          'x_auto': None if auto_xy is None else auto_xy[0],
                          'y_auto': None if auto_xy is None else auto_xy[1],
                          'x': xy[0], 'y': xy[1], 'action': action}])
    line.to_csv(path, mode='a', header=not os.path.isfile(path), index=False)


def set_corner(fm_csv, name, corner, x, y, accuracy=1.0, pending=None):
    """Save the (reviewed) coordinates of one FM in Out_fiducialmarks.csv.

    For an image without coordinates, the corners are kept in 'pending' (dict) until the four
    corners are known; the row is then added. Returns True if the CSV file was written.
    """
    df = read_fm(fm_csv)
    k = CORNERS.index(corner) + 1
    if name in df.index:
        df.loc[name, f'X{k}'] = int(round(x))
        df.loc[name, f'Y{k}'] = int(round(y))
        df.loc[name, f'{corner}_accuracy'] = accuracy
        write_fm(fm_csv, df)
        return True
    if pending is not None:
        pending.setdefault(name, {})[corner] = (int(round(x)), int(round(y)))
        if len(pending[name]) == 4:
            row = {'name': name}
            for kk, c in enumerate(CORNERS, start=1):
                row[f'X{kk}'], row[f'Y{kk}'] = pending[name][c]
                row[f'{c}_accuracy'] = accuracy
            df = pd.concat([df.reset_index(drop=True), pd.DataFrame([row])], ignore_index=True).set_index('name', drop=False)
            write_fm(fm_csv, df)
            del pending[name]
            return True
    return False


# 2. Geometry check
# ------------------

def geometry_check(df, min_tol=MIN_GEOMETRY_TOL):
    """Check that the four FMs of each image form a parallelogram.

    :return: DataFrame indexed by image name with the closure error (pix), the tolerance, a 'suspect'
        flag, the most likely wrong corner and, for each corner, its position expected from the three
        other FMs (parallelogram completion).
    """
    if df is None or len(df) == 0:
        return pd.DataFrame()
    P = np.stack([df[f'X{k}'].astype(float).values + 1j * df[f'Y{k}'].astype(float).values
                  for k in range(1, 5)], axis=1)
    sign = np.array([1, -1, 1, -1])  # TL + BR - TR - BL
    closure = P @ sign
    err = np.abs(closure)
    med = np.median(err)
    mad = 1.4826 * np.median(np.abs(err - med))
    tol = max(min_tol, med + 6 * mad)

    # Most likely wrong corner: the one furthest from its usual position (after removing the
    # translation of the image, estimated with the median offset of its four corners)
    usual = np.median(P.real, axis=0) + 1j * np.median(P.imag, axis=0)
    D = P - usual
    shift = np.median(D.real, axis=1) + 1j * np.median(D.imag, axis=1)
    deviation = np.abs(D - shift[:, None])

    res = pd.DataFrame({'name': df['name'].values, 'closure': err, 'tol': tol,
                        'suspect': err > tol,
                        'corner': [CORNERS[k] for k in np.argmax(deviation, axis=1)]}).set_index('name', drop=False)
    for k, c in enumerate(CORNERS):
        expected = P[:, k] - sign[k] * closure  # position that closes the parallelogram
        res[f'{c}_expected_x'] = expected.real
        res[f'{c}_expected_y'] = expected.imag
    return res


# 3. List of corners to review
# -----------------------------

def list_images(image_folder):
    files = [f for f in os.listdir(image_folder) if f.lower().endswith(IMAGE_EXTENSIONS)]
    return {stem(f): f for f in sorted(files)}


def build_review_queue(image_folder, include_score=True, include_geometry=True, include_missing=True,
                       review_all=False, include_reviewed=False):
    """List of corners to review: dicts with keys file, name, corner, reasons, auto (x, y) or None, expected."""
    fm_csv = os.path.join(image_folder, FM_CSV)
    df = read_fm(fm_csv)
    images = list_images(image_folder)
    geo = geometry_check(df) if len(df) >= 5 else pd.DataFrame()

    items = {}  # (name, corner) -> item

    def add(name, corner, reason):
        if name not in images:
            return
        key = (name, corner)
        if key not in items:
            auto = None
            if name in df.index:
                k = CORNERS.index(corner) + 1
                auto = (int(df.loc[name, f'X{k}']), int(df.loc[name, f'Y{k}']))
            expected = None
            if len(geo) and name in geo.index:
                expected = (float(geo.loc[name, f'{corner}_expected_x']), float(geo.loc[name, f'{corner}_expected_y']))
            items[key] = {'file': images[name], 'name': name, 'corner': corner, 'reasons': [],
                          'auto': auto, 'expected': expected}
        items[key]['reasons'].append(reason)

    if include_score:
        tbc = os.path.join(image_folder, TOBECHECKED_CSV)
        if os.path.isfile(tbc):
            t = pd.read_csv(tbc)
            for _, r in t.iterrows():
                add(stem(r['image']), r['corner'], f"score {float(r['maxVal']):.2f}")
        # also low scores recorded in Out_fiducialmarks.csv
        for name, r in df.iterrows():
            for c in CORNERS:
                acc = r.get(f'{c}_accuracy')
                if pd.notna(acc) and float(acc) < 0.88 and (name, c) not in items:
                    add(name, c, f'score {float(acc):.2f}')

    if include_geometry and len(geo):
        for name, g in geo[geo['suspect']].iterrows():
            add(name, g['corner'], f"geometry {g['closure']:.0f} px (tol. {g['tol']:.0f})")

    if include_missing:
        for name in images:
            if name not in df.index:
                for c in CORNERS:
                    add(name, c, 'no FM coordinates')

    if review_all:
        for name in images:
            for c in CORNERS:
                add(name, c, 'all corners')

    queue = list(items.values())
    if not include_reviewed:
        log = read_review_log(image_folder)
        done = set(zip(log['name'].astype(str), log['corner'].astype(str))) if len(log) else set()
        queue = [it for it in queue if (it['name'], it['corner']) not in done]

    queue.sort(key=lambda it: (it['name'], CORNERS.index(it['corner'])))
    usual = {}
    if len(df):
        for k, c in enumerate(CORNERS, start=1):
            usual[c] = (float(df[f'X{k}'].median()), float(df[f'Y{k}'].median()))
    for it in queue:
        it['usual'] = usual.get(it['corner'])  # usual position of this FM in the dataset (start point if no detection)
        if len(geo) and it['name'] in geo.index:
            it['closure'] = float(geo.loc[it['name'], 'closure'])
            it['geometry_ok'] = not bool(geo.loc[it['name'], 'suspect'])
        else:
            it['closure'], it['geometry_ok'] = None, None
    return queue


def print_geometry_summary(image_folder):
    """Print the images whose FMs fail the geometry check (used at the end of Tool 2c)."""
    df = read_fm(os.path.join(image_folder, FM_CSV))
    if len(df) < 5:
        print(' > Geometry check skipped (less than 5 images)')
        return []
    geo = geometry_check(df)
    bad = geo[geo['suspect']].sort_values('closure', ascending=False)
    print(f' > Geometry check (parallelogram closure |TL+BR-TR-BL|): median {geo["closure"].median():.0f} px, '
          f'tolerance {geo["tol"].iloc[0]:.0f} px')
    if len(bad) == 0:
        print('   all images are consistent')
    for name, g in bad.iterrows():
        print(f"\033[91m   suspect: {name}  closure {g['closure']:.0f} px  (most likely {g['corner']})\033[0m")
    return list(bad.index)
