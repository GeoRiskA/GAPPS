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

CORNERS = ['top_left', 'top_right', 'bot_right', 'bot_left']  # FM 1, 2, 3, 4 of Out_fiducialmarks.csv (corner layout)
SIDES = ['top', 'right', 'bottom', 'left']  # FM 1, 2, 3, 4 of Out_fiducialmarks.csv (mid-side notch layout)
LAYOUTS = {'corners': CORNERS, 'midpoints': SIDES}
LAYOUT_LABELS = {'corners': 'Corners (fiducial targets)', 'midpoints': 'Mid-side notches'}
LAYOUT_TXT = 'Out_fiducialmarks_layout.txt'
IMAGE_EXTENSIONS = ('.tif', '.tiff', '.jpg', '.jpeg')
FM_CSV = 'Out_fiducialmarks.csv'
TOBECHECKED_CSV = 'Out_fiducialmarks_TobeChecked.csv'
REVIEW_LOG_CSV = 'Out_fiducialmarks_review_log.csv'
FM_COLUMNS = ['name', 'X1', 'Y1', 'X2', 'Y2', 'X3', 'Y3', 'X4', 'Y4', 'top_left_accuracy',
              'top_right_accuracy', 'bot_right_accuracy', 'bot_left_accuracy']
ACC_COLUMNS = FM_COLUMNS[9:]  # accuracy of FM 1, 2, 3, 4 (named after the corners, also used for the sides)
MIN_GEOMETRY_TOL = 60.0  # minimum closure error (pix) flagged by the geometry check


# 0. Layout of the fiducial marks
# --------------------------------

def mark_names(layout):
    """Names of FM 1, 2, 3, 4 for a layout ('corners' or 'midpoints')."""
    return LAYOUTS.get(layout, CORNERS)


def read_layout(image_folder):
    """Layout of the FMs detected in a folder (written by Tool 2c; 'corners' by default)."""
    path = os.path.join(image_folder, LAYOUT_TXT)
    if os.path.isfile(path):
        layout = open(path).read().strip()
        if layout in LAYOUTS:
            return layout
    return 'corners'


def write_layout(image_folder, layout):
    with open(os.path.join(image_folder, LAYOUT_TXT), 'w') as f:
        f.write(layout)


def template_key(template_name):
    """FM of a template file 'Template_<dataset>_<FM>_<n>.tif' (e.g. 'top_left' or 'top'), or None."""
    root = os.path.splitext(os.path.basename(template_name))[0]
    parts = root.rsplit('_', 1)
    if len(parts) == 2 and parts[1].isdigit():
        root = parts[0]
    for key in CORNERS + SIDES:  # corners first: '_top_left' must not be read as '_left'
        if root.endswith('_' + key):
            return key
    return None


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
    names = SIDES if corner in SIDES else CORNERS
    k = names.index(corner) + 1
    if name in df.index:
        df.loc[name, f'X{k}'] = int(round(x))
        df.loc[name, f'Y{k}'] = int(round(y))
        df.loc[name, ACC_COLUMNS[k - 1]] = accuracy
        write_fm(fm_csv, df)
        return True
    if pending is not None:
        pending.setdefault(name, {})[corner] = (int(round(x)), int(round(y)))
        if len(pending[name]) == 4:
            row = {'name': name}
            for kk, c in enumerate(names, start=1):
                row[f'X{kk}'], row[f'Y{kk}'] = pending[name][c]
                row[ACC_COLUMNS[kk - 1]] = accuracy
            df = pd.concat([df.reset_index(drop=True), pd.DataFrame([row])], ignore_index=True).set_index('name', drop=False)
            write_fm(fm_csv, df)
            del pending[name]
            return True
    return False


# 2. Geometry check
# ------------------

CONFIDENT = 0.88  # matching score above which a detection is used to learn the shape of the four FMs


def mark_array(df):
    """Complex coordinates (n x 4) and scores (n x 4) of FM 1-4 of a Out_fiducialmarks DataFrame."""
    P = np.stack([df[f'X{k}'].astype(float).values + 1j * df[f'Y{k}'].astype(float).values
                  for k in range(1, 5)], axis=1)
    S = np.stack([pd.to_numeric(df[c], errors='coerce').fillna(0).values for c in ACC_COLUMNS], axis=1)
    return P, S


def reference_shape(P, S, confident=CONFIDENT, symmetric=True):
    """Shape of the four FMs of a camera (mid-side notches), learnt from the confident detections.

    Coordinates are normalized by the left (FM4) and right (FM2) notches: left -> 0, right -> 1, so that
    the shape does not depend on the position, rotation and scale of the scan.
    :return: complex array of 4 normalized positions (NaN if never detected with confidence)
    """
    ref = np.full(4, np.nan, dtype=complex)
    ok_lr = (S[:, 1] >= confident) & (S[:, 3] >= confident)
    if ok_lr.sum() == 0:
        return ref
    L, R = P[ok_lr, 3], P[ok_lr, 1]
    for k in range(4):
        sel = S[ok_lr, k] >= confident
        if sel.sum() > 0:
            z = (P[ok_lr, k][sel] - L[sel]) / (R[sel] - L[sel])
            ref[k] = np.median(z.real) + 1j * np.median(z.imag)
    # Top or bottom notch never detected with confidence (e.g. top of the frame outside the scan):
    # approximated by the symmetric of the other one with respect to the left-right line
    if symmetric:
        if np.isnan(ref[0]) and not np.isnan(ref[2]):
            ref[0] = ref[2].real - 1j * ref[2].imag
        if np.isnan(ref[2]) and not np.isnan(ref[0]):
            ref[2] = ref[0].real - 1j * ref[0].imag
    return ref


def reliable_marks(acc, threshold=CONFIDENT):
    """Indices of the reliable FMs of an image (accuracy >= threshold, or reviewed = 1).
    (Accuracy -1: FM marked as not visible in the review; 0: position predicted from the other FMs.)"""
    return [k for k in range(4) if acc[k] >= threshold]


def predict_marks(p, use, ref):
    """Positions of the four FMs of one image predicted from some of its FMs and the reference shape.

    A similarity (position, rotation, scale) z = a * ref + b is fitted on the FMs listed in `use`
    (at least 2, with a known reference position). :return: complex array of 4 positions (NaN if unknown)
    """
    use = [k for k in use if not np.isnan(ref[k])]
    if len(use) < 2:
        return np.full(4, np.nan, dtype=complex)
    A = np.stack([ref[use], np.ones(len(use))], axis=1)
    (a, b), *_ = np.linalg.lstsq(A, p[use], rcond=None)
    return a * ref + b


def geometry_check_sides(df, min_tol=MIN_GEOMETRY_TOL):
    """Geometry check for mid-side notches: each FM is compared with its position predicted from the
    other (confident) FMs of the image and the shape of the four FMs learnt on the dataset."""
    P, S = mark_array(df)
    ref = reference_shape(P, S)
    n = len(P)
    expected = np.full((n, 4), np.nan, dtype=complex)
    for i in range(n):
        for k in range(4):
            others = [j for j in range(4) if j != k and S[i, j] >= CONFIDENT]
            if len(others) < 2:  # not enough confident FMs: use all the others
                others = [j for j in range(4) if j != k]
            expected[i, k] = predict_marks(P[i], others, ref)[k]
    dev = np.abs(P - expected)
    valid = dev[~np.isnan(dev)]
    med = np.median(valid) if valid.size else 0
    mad = 1.4826 * np.median(np.abs(valid - med)) if valid.size else 0
    tol = max(min_tol, med + 6 * mad)
    worst = np.nanargmax(np.where(np.isnan(dev), -1, dev), axis=1)
    worst_dev = dev[np.arange(n), worst]
    names = SIDES
    res = pd.DataFrame({'name': df['name'].values, 'closure': np.nan_to_num(worst_dev), 'tol': tol,
                        'suspect': np.nan_to_num(worst_dev) > tol,
                        'corner': [names[k] for k in worst]}).set_index('name', drop=False)
    for k, c in enumerate(names):
        res[f'{c}_expected_x'] = expected[:, k].real
        res[f'{c}_expected_y'] = expected[:, k].imag
    return res


def geometry_check(df, min_tol=MIN_GEOMETRY_TOL, layout='corners'):
    """Check that the four FMs of each image form a parallelogram (same shape for all images).

    FM1 + FM3 - FM2 - FM4 (the closure) is ~0 for corner FMs; for mid-side notches, which are not
    exactly at the middle of the sides, it is a constant vector: its deviation from the usual
    (median) value of the dataset is used.

    :return: DataFrame indexed by image name with the closure error (pix), the tolerance, a 'suspect'
        flag, the most likely wrong corner and, for each corner, its position expected from the three
        other FMs (parallelogram completion).
    """
    if df is None or len(df) == 0:
        return pd.DataFrame()
    if layout == 'midpoints':
        return geometry_check_sides(df, min_tol)
    P = np.stack([df[f'X{k}'].astype(float).values + 1j * df[f'Y{k}'].astype(float).values
                  for k in range(1, 5)], axis=1)
    names = mark_names(layout)
    sign = np.array([1, -1, 1, -1])  # FM1 + FM3 - FM2 - FM4 (TL + BR - TR - BL, or T + B - R - L)
    closure = P @ sign
    closure = closure - (np.median(closure.real) + 1j * np.median(closure.imag))
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
                        'corner': [names[k] for k in np.argmax(deviation, axis=1)]}).set_index('name', drop=False)
    for k, c in enumerate(names):
        expected = P[:, k] - sign[k] * closure  # position that closes the parallelogram
        res[f'{c}_expected_x'] = expected.real
        res[f'{c}_expected_y'] = expected.imag
    return res


# 3. List of corners to review
# -----------------------------

def list_images(image_folder):
    files = [f for f in os.listdir(image_folder) if f.lower().endswith(IMAGE_EXTENSIONS)
             and os.path.getsize(os.path.join(image_folder, f)) > 0]  # (empty files cannot be reviewed)
    return {stem(f): f for f in sorted(files)}


def build_review_queue(image_folder, include_score=True, include_geometry=True, include_missing=True,
                       review_all=False, include_reviewed=False):
    """List of corners to review: dicts with keys file, name, corner, reasons, auto (x, y) or None, expected."""
    fm_csv = os.path.join(image_folder, FM_CSV)
    df = read_fm(fm_csv)
    images = list_images(image_folder)
    layout = read_layout(image_folder)
    names = mark_names(layout)
    geo = geometry_check(df, layout=layout) if len(df) >= 5 else pd.DataFrame()

    items = {}  # (name, corner) -> item

    def add(name, corner, reason):
        if name not in images:
            return
        key = (name, corner)
        if key not in items:
            auto = None
            if name in df.index:
                k = names.index(corner) + 1
                auto = (int(df.loc[name, f'X{k}']), int(df.loc[name, f'Y{k}']))
            expected = None
            if len(geo) and name in geo.index:
                expected = (float(geo.loc[name, f'{corner}_expected_x']), float(geo.loc[name, f'{corner}_expected_y']))
            items[key] = {'file': images[name], 'name': name, 'corner': corner, 'reasons': [],
                          'auto': auto, 'expected': expected}
        items[key]['reasons'].append(reason)

    # Mid-side notches: 3 reliable notches are enough for the reprojection (affine transform), so the
    # notches with a low score are only reviewed for images with less than 3 reliable notches
    enough = set()
    if layout == 'midpoints' and len(df):
        _, S_all = mark_array(df)
        enough = {n for n, sc in zip(df['name'], S_all) if len(reliable_marks(sc)) >= 3}

    if include_score:
        tbc = os.path.join(image_folder, TOBECHECKED_CSV)
        if os.path.isfile(tbc):
            t = pd.read_csv(tbc)
            for _, r in t.iterrows():
                if r['corner'] in names and stem(r['image']) not in enough:
                    note = ' – not found, position predicted from the other FMs' \
                        if str(r.get('is Check', '')).strip() == 'predicted' else ''
                    add(stem(r['image']), r['corner'], f"score {float(r['maxVal']):.2f}{note}")
        # also low scores recorded in Out_fiducialmarks.csv
        for name, r in df.iterrows():
            for k, c in enumerate(names):
                acc = r.get(ACC_COLUMNS[k])
                if pd.notna(acc) and float(acc) < CONFIDENT and (name, c) not in items and name not in enough:
                    add(name, c, f'score {float(acc):.2f}')

    if include_geometry and len(geo):
        for name, g in geo[geo['suspect']].iterrows():
            add(name, g['corner'], f"geometry {g['closure']:.0f} px (tol. {g['tol']:.0f})")

    if include_missing:
        for name in images:
            if name not in df.index:
                for c in names:
                    add(name, c, 'no FM coordinates')

    if review_all:
        for name in images:
            for c in names:
                add(name, c, 'all FMs')

    queue = list(items.values())
    if not include_reviewed:
        log = read_review_log(image_folder)
        done = set(zip(log['name'].astype(str), log['corner'].astype(str))) if len(log) else set()
        queue = [it for it in queue if (it['name'], it['corner']) not in done]

    queue.sort(key=lambda it: (it['name'], names.index(it['corner']) if it['corner'] in names else 0))
    usual = {}
    if len(df):
        for k, c in enumerate(names, start=1):
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
    geo = geometry_check(df, layout=read_layout(image_folder))
    bad = geo[geo['suspect']].sort_values('closure', ascending=False)
    print(f' > Geometry check (parallelogram closure FM1+FM3-FM2-FM4, deviation from its usual value): median {geo["closure"].median():.0f} px, '
          f'tolerance {geo["tol"].iloc[0]:.0f} px')
    if len(bad) == 0:
        print('   all images are consistent')
    for name, g in bad.iterrows():
        print(f"\033[91m   suspect: {name}  closure {g['closure']:.0f} px  (most likely {g['corner']})\033[0m")
    return list(bad.index)
