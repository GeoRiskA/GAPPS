"""
========================================================================================
                     GAPPS – GeoRiskA Airphoto Pre-Processing Suite
========================================================================================
                    = DETECTION OF MID-SIDE FIDUCIAL NOTCHES =

Description: Detection of fiducial marks shaped as notches in the middle of the four
    sides of the image frame (e.g. the 1949 Leopoldville photos), instead of fiducial
    targets in the corners. Used by Tool 2c when the layout 'midpoints' is selected.

    The notches are cut in the dark film frame. Their appearance is dominated by the
    image content next to them (dark forest, bright towns...), so they are not matched
    on their grey values but on the shape of the dark frame: the frame is segmented
    (pixels much darker than the image) in the search window and in the template, and
    the two binary masks are matched (normalized correlation). The match is done on a
    half resolution copy, then refined at full resolution.

    FM 1, 2, 3, 4 of Out_fiducialmarks.csv are the top, right, bottom and left notches.
    Templates: Template_<dataset>_<top|right|bottom|left>_<n>.tif (FM template creator,
    layout 'Mid-side notches').

Copyright:
    RMCA — Royal Museum for Central Africa (Tervuren, BELGIUM)
        Natural Hazards and Cartography (GeoRiskA), Dpt. of Earth Sciences
    © 2026

Software authorship:
    - Antoine DILLE (RMCA)

Last update: 2026-10-22
========================================================================================
"""

import os
import time

import cv2
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.patches import Rectangle

try:
    from GAPPS_tools.GAPPS_Tool_02e_FM_Review import (SIDES, FM_COLUMNS, template_key, mark_array,
                                                      reference_shape, predict_marks)
except ImportError:
    from GAPPS_Tool_02e_FM_Review import (SIDES, FM_COLUMNS, template_key, mark_array, reference_shape,
                                          predict_marks)

# Search windows, as fractions of the image size: centred on the middle of each side,
# ALONG = half length along the side (the notches are within ~2 % of the middle when the images
# are cropped to the frame: a narrow window avoids false matches), DEPTH = distance from the edge
ALONG = 0.06
DEPTH = 0.15
RADIUS = 400  # second pass: search radius (pix) around the position predicted from the other notches
MAX_DEVIATION = 150  # second pass: a notch further than this (pix) from its predicted position is searched again
MAX_OFFSET = 300  # ... or further than this (pix) from its usual position in the dataset (cropped images)
MATCH_THRESHOLD = 0.88  # below: the notch is listed for the manual review
COARSE = 2  # downsampling factor of the coarse matching
DEFAULT_HALFWIDTH = 250  # recommended template half width for notches at ~1600 dpi


# 1. Frame segmentation and matching
# -----------------------------------

def frame_mask(gray, sigma=3, opening=9, q=10, k=0.3):
    """Binary mask (float32, 1 = dark film frame) of an 8-bit image.

    The frame level is the q-th percentile and the image level the median of the (blurred) image:
    pixels darker than frame + k * (image - frame) are the frame. Small dark spots of the image
    are removed by a morphological opening.
    """
    b = cv2.GaussianBlur(gray, (0, 0), sigma).astype(np.float32)
    sub = b[::2, ::2]
    lo, med = np.percentile(sub, q), np.median(sub)
    m = (b < lo + k * (med - lo)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((opening, opening), np.uint8))
    return m.astype(np.float32)


def side_windows(shape):
    """Search window (y0, x0, y1, x1) of each side notch."""
    H, W = shape[:2]
    a_w, a_h, d_w, d_h = int(ALONG * W), int(ALONG * H), int(DEPTH * W), int(DEPTH * H)
    return {'top': (0, W // 2 - a_w, d_h, W // 2 + a_w),
            'bottom': (H - d_h, W // 2 - a_w, H, W // 2 + a_w),
            'left': (H // 2 - a_h, 0, H // 2 + a_h, d_w),
            'right': (H // 2 - a_h, W - d_w, H // 2 + a_h, W)}


def match_notch(window, template, xc, yc):
    """Find a notch template in a search window (both 8-bit grayscale).

    :return: (x, y, score): position of the template centre (xc, yc) in the window, and matching score
        of the frame masks (normalized correlation, 1 = identical shapes); None if no match is possible.
    """
    th, tw = template.shape
    wh, ww = window.shape
    if th >= wh or tw >= ww:
        return None
    f = COARSE
    # coarse: half resolution
    wm = frame_mask(cv2.resize(window, (ww // f, wh // f), interpolation=cv2.INTER_AREA))
    tm = frame_mask(cv2.resize(template, (tw // f, th // f), interpolation=cv2.INTER_AREA))
    if tm.std() == 0 or wm.std() == 0:
        return None
    r = cv2.matchTemplate(wm, tm, cv2.TM_CCOEFF_NORMED)
    _, score, _, loc = cv2.minMaxLoc(r)
    # fine: full resolution, around the coarse position
    m = 3 * f
    x0, y0 = max(loc[0] * f - m, 0), max(loc[1] * f - m, 0)
    x1, y1 = min(loc[0] * f + m + tw, ww), min(loc[1] * f + m + th, wh)
    wmf = frame_mask(window[y0:y1, x0:x1], sigma=2 * 3, opening=2 * 9 - 1)
    tmf = frame_mask(template, sigma=2 * 3, opening=2 * 9 - 1)
    if wmf.shape[0] >= th and wmf.shape[1] >= tw and tmf.std() > 0 and wmf.std() > 0:
        r2 = cv2.matchTemplate(wmf, tmf, cv2.TM_CCOEFF_NORMED)
        _, score_f, _, loc_f = cv2.minMaxLoc(r2)
        # position refined at full resolution; score: best of the two resolutions (the coarse one is less
        # sensitive to the film edge text, the fine one to blur). Wrong positions with a high score are
        # caught by the position checks of the 2nd pass (run_midpoints)
        return x0 + loc_f[0] + xc, y0 + loc_f[1] + yc, float(max(score, score_f))
    return loc[0] * f + xc, loc[1] * f + yc, float(score)


def load_side_templates(fiducial_template_folder, center_fidu_tempate_CSV):
    """Side templates: {side: [(template name, 8-bit template, xc, yc), ...]}."""
    centers = {}
    if os.path.isfile(center_fidu_tempate_CSV):
        for line in open(center_fidu_tempate_CSV):
            parts = line.split()
            if len(parts) >= 3:
                centers[parts[0]] = (int(parts[1]), int(parts[2]))
    templates = {s: [] for s in SIDES}
    for f in sorted(os.listdir(fiducial_template_folder)):
        if not f.lower().endswith(('.tif', '.tiff')):
            continue
        key = template_key(f)
        name = os.path.splitext(f)[0]
        if key in SIDES and name in centers:
            path = os.path.join(fiducial_template_folder, f)
            t = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            if t is not None:
                templates[key].append((name, t, *centers[name]))
    return templates


# 2. Detection of the four notches of one image
# ----------------------------------------------

def notches_figure(img, windows, coords, scores, templates_used, corner_folder, image_name):
    """Figure with the four search windows and the detected notches (corners/_all_fiducials)."""
    fig = Figure(figsize=(12, 12))
    FigureCanvasAgg(fig)
    for i, side in enumerate(SIDES):
        ax = fig.add_subplot(2, 2, i + 1)
        y0, x0, y1, x1 = windows[side]
        w = img[y0:y1, x0:x1]
        step = max(1, max(w.shape) // 1500)
        ax.imshow(w[::step, ::step], cmap='gray', extent=(x0, x1, y1, y0))
        if side in coords:
            x, y = coords[side]
            _, t, xc, yc = templates_used[side]
            col = 'r' if scores[side] < MATCH_THRESHOLD else 'lime'
            ax.add_patch(Rectangle((x - xc, y - yc), t.shape[1], t.shape[0], edgecolor=col, fill=False, lw=1.5))
            ax.plot(x, y, '+', color=col, ms=14, mew=2)
            ax.set_title(f'{side}: ({x}, {y})  score {scores[side]:.2f}', color='k' if col == 'lime' else 'r')
        else:
            ax.set_title(f'{side}: not found', color='r')
    fig.suptitle(image_name, fontweight='bold')
    fig.tight_layout()
    folder = os.path.join(corner_folder, '_all_fiducials')
    os.makedirs(folder, exist_ok=True)
    fig.savefig(os.path.join(folder, f'_FiducialsDetection_{image_name}.png'), dpi=100)


def MainSides(image_folder, image_name, fiducial_template_folder, corner_folder, Out_fiducialmarks_CSV,
              center_fidu_tempate_CSV, overwriting=False, write_outputs=True, priors=None, fixed=None):
    """Detect the four mid-side notches of one image (same outputs and return value as Tool 2c Main).

    Second pass (used by run_midpoints): `fixed` = {side: (x, y, score)} notches kept as they are,
    `priors` = {side: (x, y)} positions predicted from the other notches: the notch is searched within
    RADIUS pixels; if the match stays below MATCH_THRESHOLD, the predicted position is kept (accuracy 0)
    and the notch is listed for the review.
    """
    result = {'image': image_name, 'line': None, 'tobechecked': None, 'error': None}
    start = time.time()
    name = os.path.splitext(image_name)[0]
    second_pass = bool(priors or fixed)

    if not overwriting and not second_pass and os.path.exists(Out_fiducialmarks_CSV):
        done = pd.read_csv(Out_fiducialmarks_CSV)
        if name in done[done.columns[0]].astype(str).values:
            print(f'Fiducial detection already done for {image_name}')
            return result

    templates = load_side_templates(fiducial_template_folder, center_fidu_tempate_CSV)
    missing = [s for s in SIDES if not templates[s]]
    if missing:
        result['error'] = (f'no template for the {", ".join(missing)} notch(es) in {fiducial_template_folder} '
                           f'(create them with the template creator, layout "Mid-side notches")')
        print(f'\033[91m !! {image_name}: {result["error"]}\033[0m')
        return result

    image_path = os.path.join(image_folder, image_name)
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        size = os.path.getsize(image_path) if os.path.exists(image_path) else 0
        result['error'] = (f'unreadable image ({size} bytes): empty, truncated or corrupted file '
                           f'-> delete it and run Tool 1 again for this image')
        print(f'\033[91m !! {image_name}: {result["error"]}\033[0m')
        return result
    H, W = img.shape

    windows = side_windows(img.shape)
    coords, scores, accuracy, used = {}, {}, {}, {}
    for side in SIDES:
        if fixed and side in fixed:
            x, y, sc = fixed[side]
            coords[side], scores[side], accuracy[side] = (int(x), int(y)), sc, sc
            used[side] = templates[side][0]
            continue
        if priors and side in priors:  # narrow window around the predicted position
            px, py = priors[side]
            m = RADIUS + max(max(t[1].shape) for t in templates[side])
            windows[side] = (int(max(py - m, 0)), int(max(px - m, 0)), int(min(py + m, H)), int(min(px + m, W)))
        y0, x0, y1, x1 = windows[side]
        win = img[y0:y1, x0:x1]
        best = None
        for t in templates[side]:
            mt = match_notch(win, t[1], t[2], t[3])
            if mt is not None and (best is None or mt[2] > best[0][2]):
                best = (mt, t)
        if best is not None:
            (x, y, score), t = best
            coords[side], scores[side], accuracy[side], used[side] = (int(round(x0 + x)), int(round(y0 + y))), score, score, t
        if priors and side in priors and (best is None or scores[side] < MATCH_THRESHOLD):
            # no reliable match near the predicted position: keep the prediction (accuracy 0)
            coords[side] = (int(round(priors[side][0])), int(round(priors[side][1])))
            scores[side] = scores.get(side, 0.0)
            accuracy[side] = 0.0
            used[side] = best[1] if best else templates[side][0]

    if len(coords) < 4:
        result['error'] = f'notch(es) not found: {", ".join(s for s in SIDES if s not in coords)}'
        print(f'\033[91m !! {image_name}: {result["error"]}\033[0m')
        return result

    # Output line (FM 1-4 = top, right, bottom, left) and notches to review
    row = {'name': name}
    for k, side in enumerate(SIDES, start=1):
        row[f'X{k}'], row[f'Y{k}'] = coords[side]
        row[FM_COLUMNS[8 + k]] = round(accuracy[side], 2)
    line = pd.DataFrame([row])[FM_COLUMNS]
    low = [s for s in SIDES if accuracy[s] < MATCH_THRESHOLD]
    tobechecked = pd.DataFrame([{'image': image_name, 'corner': s, 'x': coords[s][0], 'y': coords[s][1],
                                 'maxVal': scores[s], 'is Check': 'predicted' if accuracy[s] == 0 else ''}
                                for s in low]) if low else None

    def fmt(s):
        return f"{s} {'pred.' if accuracy[s] == 0 else f'{scores[s]:.2f}'} {coords[s]}"
    print(f"   >> {image_name}{' (2nd pass)' if second_pass else ''} [{time.time() - start:.1f} s]: " +
          '  '.join(fmt(s) for s in SIDES) + (f"  -> to review: {', '.join(low)}" if low else ''))
    try:
        notches_figure(img, windows, coords, accuracy, used, corner_folder, image_name)
    except Exception as e:
        print(f'   (figure not saved: {e})')

    if write_outputs:
        write_results([dict(result, line=line, tobechecked=tobechecked)], Out_fiducialmarks_CSV)
    else:
        result['line'] = line
        result['tobechecked'] = tobechecked
    return result


def _safe_MainSides(*args, **kwargs):
    try:
        return MainSides(*args, **kwargs)
    except Exception as e:
        print(f'\033[91m !! {args[1]}: {type(e).__name__}: {e}\033[0m')
        return {'image': args[1], 'line': None, 'tobechecked': None, 'error': f'{type(e).__name__}: {e}'}


def write_results(results, Out_fiducialmarks_CSV):
    """Write the lines and notches to review (replacing the lines of images processed again)."""
    lines = [r['line'] for r in results if r and r.get('line') is not None]
    if lines:
        f = pd.read_csv(Out_fiducialmarks_CSV)
        new = pd.concat(lines, ignore_index=True)
        new.columns = f.columns
        f = f[~f[f.columns[0]].isin(new[new.columns[0]])]
        (pd.concat([f, new], ignore_index=True) if len(f) else new).to_csv(Out_fiducialmarks_CSV, index=False)
    checks = [r['tobechecked'] for r in results if r and r.get('tobechecked') is not None]
    if checks:
        tbc = Out_fiducialmarks_CSV[:-4] + '_TobeChecked.csv'
        pd.concat(checks, ignore_index=True).to_csv(tbc, mode='a', header=not os.path.isfile(tbc))


# 3. Detection of all images (two passes)
# ----------------------------------------

def plan_second_pass(results, Out_fiducialmarks_CSV):
    """Notches to search again: low score, or inconsistent with the other notches of the image.

    The shape of the four notches is learnt from the confident detections (previous ones in the CSV file
    and the new ones). :return: list of (image name, priors, fixed) for MainSides
    """
    new = [r for r in results if r and r.get('line') is not None]
    if not new:
        return []
    f = pd.read_csv(Out_fiducialmarks_CSV)
    f.columns = f.columns.str.strip()
    lines = pd.concat([r['line'] for r in new], ignore_index=True)
    f = f[~f['name'].isin(lines['name'])]
    all_rows = pd.concat([f, lines], ignore_index=True) if len(f) else lines
    P, S = mark_array(all_rows)
    ref = reference_shape(P, S, MATCH_THRESHOLD)
    n_ref = int(((S[:, 1] >= MATCH_THRESHOLD) & (S[:, 3] >= MATCH_THRESHOLD)).sum())
    print(f' > Shape of the notches learnt on {n_ref} images (normalized positions, left = 0, right = 1): ' +
          ', '.join(f'{s} ({ref[k].real:.3f}, {ref[k].imag:.3f})' for k, s in enumerate(SIDES)))
    # usual position of each notch in the dataset (confident detections)
    usual = np.array([np.median(P[S[:, k] >= MATCH_THRESHOLD, k].real) + 1j * np.median(P[S[:, k] >= MATCH_THRESHOLD, k].imag)
                      if (S[:, k] >= MATCH_THRESHOLD).sum() >= 3 else np.nan for k in range(4)])
    plan = []
    for r in new:
        p, sc = mark_array(r['line'])
        p, sc = p[0], sc[0]
        low = [k for k in range(4) if sc[k] < MATCH_THRESHOLD]
        good = [k for k in range(4) if sc[k] >= MATCH_THRESHOLD]
        # confident notches far from their usual position (e.g. a straight part of the frame matched)
        for k in list(good):
            if not np.isnan(usual[k]) and abs(p[k] - usual[k]) > MAX_OFFSET:
                good.remove(k)
                low.append(k)
        # confident notches inconsistent with the others
        for k in list(good):
            others = [j for j in good if j != k]
            if len(others) >= 2:
                pk = predict_marks(p, others, ref)[k]
                if not np.isnan(pk) and abs(pk - p[k]) > MAX_DEVIATION:
                    good.remove(k)
                    low.append(k)
        if not low:
            continue
        pred = predict_marks(p, good, ref)
        for k in low:  # not enough reliable notches to predict: usual position in the dataset
            if np.isnan(pred[k]) and not np.isnan(usual[k]):
                pred[k] = usual[k]
        priors = {SIDES[k]: (pred[k].real, pred[k].imag) for k in low if not np.isnan(pred[k])}
        if priors:
            fixed = {SIDES[k]: (p[k].real, p[k].imag, sc[k]) for k in range(4) if SIDES[k] not in priors}
            plan.append((r['image'], priors, fixed))
    return plan


def run_midpoints(image_folder, imlist, fiducial_template_folder, corner_folder, Out_fiducialmarks_CSV,
                  center_fidu_tempate_CSV, overwriting=False, num_cores=1, parallel=True):
    """Detect the notches of all images in two passes, write the results; returns the list of results.

    1st pass: each notch is searched in a window centred on the middle of its side.
    The shape of the four notches is then learnt from the confident detections of all images, and the
    notches with a low matching score, or inconsistent with the other notches of their image, are searched
    again around their position predicted from the other notches (2nd pass).
    """
    from joblib import Parallel, delayed

    def run(jobs):
        if parallel and len(jobs) > 1:
            return Parallel(n_jobs=num_cores, verbose=10)(delayed(_safe_MainSides)(*a, **k) for a, k in jobs)
        return [_safe_MainSides(*a, **k) for a, k in jobs]

    common = (fiducial_template_folder, corner_folder, Out_fiducialmarks_CSV, center_fidu_tempate_CSV)
    print('\n > 1st pass: notches searched in the middle of each side')
    results = run([((image_folder, im) + common, {'overwriting': overwriting, 'write_outputs': False})
                   for im in imlist])

    plan = plan_second_pass(results, Out_fiducialmarks_CSV)
    if plan:
        print(f'\n > 2nd pass: {len(plan)} image(s) with notches searched around their predicted position')
        index = {r['image']: i for i, r in enumerate(results)}
        jobs = [((image_folder, im) + common, {'overwriting': True, 'write_outputs': False,
                                              'priors': priors, 'fixed': fixed}) for im, priors, fixed in plan]
        for r2 in run(jobs):
            if r2.get('line') is not None:
                results[index[r2['image']]] = r2

    write_results(results, Out_fiducialmarks_CSV)
    return results
