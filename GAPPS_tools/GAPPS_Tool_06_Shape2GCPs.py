#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
========================================================================================
                     GAPPS – GeoRiskA Airphoto Pre-Processing Suite
========================================================================================
                        = TOOL 6 – SHAPE2GCPs (OSM MATCHING) =

Description: Locates an un-georeferenced historical aerial photograph by matching
features digitised on it (roads, lake shores, rivers) against OpenStreetMap, and
produces approximate GCPs (image pixel <-> ground coordinate) to seed markers in
Agisoft Metashape. Used by GUI_scripts/GAPPS_interface_Shape2GCPs.py, and usable
on its own from the command line (python GAPPS_Tool_06_Shape2GCPs.py --help).

Copyright:
    RMCA — Royal Museum for Central Africa (Tervuren, BELGIUM)
        Natural Hazards and Cartography (GeoRiskA), Dpt. of Earth Sciences
    © 2026

Software authorship:
    - Antoine DILLE (RMCA), developed with Anthropic's Claude

Last update: 2026-11-06
========================================================================================

Locate a road digitised on an un-georeferenced historical aerial image by
matching its *shape* against OSM roads, then produce approximate GCPs
(image pixel  <->  ground coordinate) to seed markers in Agisoft Metashape.

Pipeline
--------
1. Road shapefile (pixel space, e.g. digitised in QGIS on the raw scan,
   where y is negative)  ->  image (col, row).
2. OSM roads clipped to the search region, projected to UTM, turned into a
   *oriented* road field (Gaussian-blurred exp(2i*phi), phi = road direction):
   a placement only scores where roads run in the same direction, so dense
   urban grids / crossing roads cancel out instead of attracting the match.
3. Coarse global search: for every (GSD, rotation[, mirror]) the road is
   rasterised and cross-correlated with P via FFT -> best translations.
4. Fine local FFT search around the best coarse candidates.
5. Trimmed ICP refinement (similarity or affine) against densified OSM.
Optional extra features (--aux, repeatable): lines digitised on the image for
   a lake shore, river, etc. Each is correlated / fitted against its own
   reference (default: the 'water*' layers of the --osm file, see
   GAPPS_Tool_06b_Shape2GCPs_ClipOSM.py) under the SAME transform. Shorelines barely change in 70
   years whereas roads do, so one lake outline removes most ambiguity.
6. GCPs picked along the matched road (preferring bends, which constrain
   both axes), snapped to the nearest OSM road, optional Z from a DEM.

Outputs (in --out directory)
----------------------------
  <stem>_gcps.csv           GCP table, WGS84 lon/lat (EPSG:4326) + DEM height
                            (read by GAPPS_Tool_06c_Metashape_ImportGCPs.py)
  <stem>_transform.json     pixel -> UTM transform, metrics, candidate list
  <stem>_match.gpkg         layers (WGS84): road_georef, aux_georef, gcps, footprint
  <stem>_match_qa.png       QA figure (overview + zoom)
  <stem>_georef.vrt         (if GDAL python is available) the image with the
                            estimated geotransform, to overlay in QGIS

Dependencies: numpy, scipy, geopandas (>=0.14), shapely (>=2), pyproj,
matplotlib; rasterio (optional: image geotransform check, DEM sampling);
osgeo.gdal (optional: VRT output).

Example
-------
python GAPPS_Tool_06_Shape2GCPs.py \
    --road   /home/adille/PROCESSING/SCANS/Bukavu_Kalehe/road_5828_170.shp \
    --region /home/adille/PROCESSING/SCANS/Bukavu_Kalehe/regions/kivu_SW.geojson \
    --osm    /home/adille/PROCESSING/SCANS/Bukavu_Kalehe/OSM_roads/EasternDRC_roads_noTracks_OSM20261020.gpkg \
    --image  /media/adille/SSDisk/SCANS/Bukavu-Kalehe_1954-55-58/5828_170_Cropped_standardized_DownSharp.tif \
    --gsd-range 0.8 3.0 --out ./osm_match_5828_170

With a lake shore and a pre-clipped OSM extract (GAPPS_Tool_06b_Shape2GCPs_ClipOSM.py):
python GAPPS_Tool_06_Shape2GCPs.py --road road_5828_170.geojson --aux lake_5828_170.geojson \
    --osm OSM_AOI_large.gpkg --region AOI_large.geojson \
    --image 5828_170_Cropped_standardized_DownSharp.tif --gsd-range 0.6 1.4 \
    --aux-gcps 4 --out osm_match_5828_170
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, Point, Polygon
from scipy import fft as sfft
from scipy.ndimage import distance_transform_edt, uniform_filter
from scipy.spatial import cKDTree

DEFAULT_EXCLUDE = ["footway", "path", "steps", "pedestrian", "cycleway",
                   "bridleway", "corridor", "proposed", "construction",
                   "platform", "elevator", "via_ferrata"]


# --------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------
def iter_lines(geoms):
    """Yield (N,2) coordinate arrays for every linear part of the geometries."""
    for g in geoms:
        if g is None or g.is_empty:
            continue
        t = g.geom_type
        if t == "LineString":
            yield np.asarray(g.coords, dtype=float)[:, :2]
        elif t in ("MultiLineString", "GeometryCollection"):
            yield from iter_lines(g.geoms)
        elif t in ("Polygon", "MultiPolygon"):
            yield from iter_lines([g.boundary])


def densify(line: np.ndarray, step: float) -> np.ndarray:
    seg = np.hypot(*np.diff(line, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    if s[-1] <= 0:
        return line[:1].copy()
    keep = np.concatenate([[True], seg > 0])
    s, line = s[keep], line[keep]
    n = max(int(math.ceil(s[-1] / step)), 1) + 1
    t = np.linspace(0.0, s[-1], n)
    return np.column_stack([np.interp(t, s, line[:, 0]),
                            np.interp(t, s, line[:, 1])])


def densify_all(lines, step):
    if not lines:
        return np.zeros((0, 2))
    return np.vstack([densify(l, step) for l in lines])


def rot(theta_deg):
    t = math.radians(theta_deg)
    c, s = math.cos(t), math.sin(t)
    return np.array([[c, -s], [s, c]])


def apply(A, p):
    return p @ A[:, :2].T + A[:, 2]


def make_similarity(gsd, theta, mirror, centroid, t):
    """world = gsd * R(theta) * M * (p - centroid) + t   ->  2x3 matrix."""
    M = np.diag([-1.0, 1.0]) if mirror else np.eye(2)
    L = gsd * rot(theta) @ M
    return np.column_stack([L, t - L @ centroid])


def decompose(A):
    L = A[:, :2]
    det = np.linalg.det(L)
    sx = np.hypot(L[0, 0], L[1, 0])
    sy = abs(det) / sx if sx > 0 else 0.0
    theta = math.degrees(math.atan2(L[1, 0], L[0, 0]))
    shear = (L[0, 0] * L[0, 1] + L[1, 0] * L[1, 1]) / (sx * sx) if sx else 0.0
    return dict(gsd_x=sx, gsd_y=sy, gsd_mean=math.sqrt(abs(det)),
                rotation_deg=theta, mirrored=bool(det < 0), shear=shear)


def fit_similarity(src, dst, w=None, allow_reflection=False):
    """(Weighted) Umeyama similarity: dst ~ s R src + t."""
    w = np.ones(len(src)) if w is None else np.asarray(w, float)
    w = w / w.sum()
    mu_s, mu_d = w @ src, w @ dst
    xs, xd = src - mu_s, dst - mu_d
    cov = (xd * w[:, None]).T @ xs
    U, S, Vt = np.linalg.svd(cov)
    D = np.eye(2)
    if not allow_reflection and np.linalg.det(U @ Vt) < 0:
        D[1, 1] = -1
    R = U @ D @ Vt
    var_s = float(w @ (xs ** 2).sum(1))
    s = np.trace(np.diag(S) @ D) / var_s
    L = s * R
    return np.column_stack([L, mu_d - L @ mu_s])


def fit_affine(src, dst, w=None):
    sw = np.ones(len(src)) if w is None else np.sqrt(np.asarray(w, float))
    X = np.column_stack([src, np.ones(len(src))]) * sw[:, None]
    coef, *_ = np.linalg.lstsq(X, dst * sw[:, None], rcond=None)
    return coef.T


# --------------------------------------------------------------------------
# pixel coordinates of the digitised road
# --------------------------------------------------------------------------
def road_to_pixels(road_gdf, image_path, mode, name="road"):
    lines = list(iter_lines(road_gdf.geometry))
    if not lines:
        sys.exit("Road file contains no line geometry.")
    tr, size = None, None
    if image_path:
        try:
            import rasterio
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                with rasterio.open(image_path) as ds:
                    size = (ds.width, ds.height)
                    if not ds.transform.is_identity:
                        tr = ds.transform
        except Exception as e:  # noqa
            print(f"[warn] could not open image ({e}); pixel mode must be guessed")
    allxy = np.vstack(lines)
    if mode == "auto":
        if tr is not None:
            mode = "raster"
        elif np.median(allxy[:, 1]) <= 0:
            mode = "qgis"
        else:
            mode = "direct"
    if mode == "raster":
        if tr is None:
            sys.exit("--pixel-mode raster but the image has no geotransform.")
        inv = ~tr
        out = [np.column_stack(inv * (l[:, 0], l[:, 1])) for l in lines]
    elif mode == "qgis":          # QGIS shows un-georeferenced rasters with y = -row
        out = [np.column_stack([l[:, 0], -l[:, 1]]) for l in lines]
    elif mode == "direct":
        out = [l.copy() for l in lines]
    else:
        sys.exit(f"unknown pixel mode {mode}")
    print(f"[{name}] pixel mode = {mode}; {len(out)} part(s); "
          f"col {np.vstack(out)[:,0].min():.0f}..{np.vstack(out)[:,0].max():.0f}, "
          f"row {np.vstack(out)[:,1].min():.0f}..{np.vstack(out)[:,1].max():.0f}")
    if size is not None:
        a = np.vstack(out)
        if a[:, 0].min() < -1 or a[:, 1].min() < -1 or a[:, 0].max() > size[0] + 1 \
                or a[:, 1].max() > size[1] + 1:
            print(f"[warn] road pixels fall outside the image ({size[0]}x{size[1]}); "
                  f"check --pixel-mode / --pixel-scale")
    return out, mode, size


# --------------------------------------------------------------------------
# OSM proximity raster + FFT search
# --------------------------------------------------------------------------
class Grid:
    def __init__(self, bounds, cell):
        x0, y0, x1, y1 = bounds
        self.x0, self.y0, self.cell = x0, y0, cell
        self.W = int(math.ceil((x1 - x0) / cell)) + 1
        self.H = int(math.ceil((y1 - y0) / cell)) + 1

    def index(self, pts):
        c = np.floor((pts[:, 0] - self.x0) / self.cell).astype(int)
        r = np.floor((pts[:, 1] - self.y0) / self.cell).astype(int)
        return r, c


def line_dirs(pts_list):
    """Tangent angle (rad) for each point of each densified line."""
    out = []
    for p in pts_list:
        if len(p) < 2:
            out.append(np.zeros(len(p)))
            continue
        g = np.gradient(p, axis=0)
        out.append(np.arctan2(g[:, 1], g[:, 0]))
    return out


def densify_dirs(lines, step):
    d = [densify(l, step) for l in lines]
    return np.vstack(d), np.concatenate(line_dirs(d))


def proximity_raster(osm_pts, osm_dir, step, grid, sigma):
    """Oriented road field: blurred exp(2i*phi). ~1 on an isolated road with
    matching orientation, ~0 far from roads or where orientations mix."""
    from scipy.ndimage import gaussian_filter
    acc = np.zeros((grid.H, grid.W), np.complex128)
    r, c = grid.index(osm_pts)
    ok = (r >= 0) & (r < grid.H) & (c >= 0) & (c < grid.W)
    np.add.at(acc, (r[ok], c[ok]), np.exp(2j * osm_dir[ok]))
    s = sigma / grid.cell
    norm = (step / grid.cell) * math.sqrt(2 * math.pi) * s
    P = (gaussian_filter(acc.real, s) + 1j * gaussian_filter(acc.imag, s)) * norm
    mag = np.abs(P)
    P = np.where(mag > 1, P / np.maximum(mag, 1e-12), P)
    return P.astype(np.complex64)


def fft_search(Ps, grid, chans, gsds, angles, mirrors, n_peaks=2, label=""):
    """Oriented cross-correlation of the rasterised template channels with the
    reference fields Ps for every (gsd, angle, mirror).
    chans: list of (pts_c, dir_c, weight); pts_c in pixel units, centroid 0, y up.
    score = sum_c w_c * sum(conj(T_c) * P_c) / sum_c w_c * n_c"""
    allp = np.vstack([c[0] for c in chans])
    R_px = np.hypot(*allp.T).max()
    hmax = int(math.ceil(2 * R_px * max(gsds) / grid.cell)) + 3
    Hp = sfft.next_fast_len(grid.H + hmax)
    Wp = sfft.next_fast_len(grid.W + hmax)
    FPs = [sfft.fft2(P, s=(Hp, Wp), workers=-1) for P in Ps]
    supp = max(2, int(0.25 * R_px * min(gsds) / grid.cell))
    results = []
    n_tot = len(gsds) * len(angles) * len(mirrors)
    t0, k = time.time(), 0
    for mirror in mirrors:
        Mps = [(c[0] * np.array([-1.0, 1.0]) if mirror else c[0],
                (math.pi - c[1]) if mirror else c[1], c[2]) for c in chans]
        for g in gsds:
            for th in angles:
                k += 1
                R = rot(th).T * (g / grid.cell)
                fls = [np.floor(Mp @ R).astype(int) for Mp, _, _ in Mps]
                off = np.vstack(fls).min(0)
                ext = np.vstack(fls).max(0) - off + 1
                acc = None
                norm = 0.0
                for fl, (_, Md, wc), FP in zip(fls, Mps, FPs):
                    ij = fl - off
                    T = np.zeros((ext[1], ext[0]), np.complex64)
                    T[ij[:, 1], ij[:, 0]] = np.exp(2j * (Md + math.radians(th)))
                    norm += wc * np.count_nonzero(T)
                    term = wc * FP * np.conj(sfft.fft2(T, s=(Hp, Wp), workers=-1))
                    acc = term if acc is None else acc + term
                corr = sfft.ifft2(acc, workers=-1).real / norm
                for _ in range(n_peaks):
                    i, j = np.unravel_index(np.argmax(corr), corr.shape)
                    score = float(corr[i, j])
                    sr = i if i < grid.H else i - Hp
                    sc = j if j < grid.W else j - Wp
                    tx = grid.x0 + (sc - off[0]) * grid.cell
                    ty = grid.y0 + (sr - off[1]) * grid.cell
                    results.append((score, g, th, mirror, tx, ty))
                    corr[max(0, i - supp):i + supp + 1, max(0, j - supp):j + supp + 1] = -np.inf
                if k % 200 == 0 or k == n_tot:
                    el = time.time() - t0
                    print(f"\r  {label} {k}/{n_tot}  ({el:.0f}s, ~{el / k * (n_tot - k):.0f}s left)",
                          end="", flush=True)
    print()
    return results


def nms(cands, min_dist, min_angle, top):
    """Keep distinct candidates (sorted by score)."""
    cands = sorted(cands, key=lambda c: -c[0])
    kept = []
    for c in cands:
        dup = False
        for k in kept:
            dang = abs((c[2] - k[2] + 180) % 360 - 180)
            if c[3] == k[3] and math.hypot(c[4] - k[4], c[5] - k[5]) < min_dist and dang < min_angle:
                dup = True
                break
        if not dup:
            kept.append(c)
        if len(kept) >= top:
            break
    return kept


def geometric_steps(lo, hi, rel):
    if hi <= lo:
        return np.array([lo])
    n = max(1, int(math.ceil(math.log(hi / lo) / math.log1p(rel))))
    return np.geomspace(lo, hi, n + 1)


def angle_steps(center, half, step):
    if half >= 180:
        return np.arange(0.0, 360.0, step)
    n = max(1, int(math.ceil(half / step)))
    return center + np.linspace(-half, half, 2 * n + 1)


# --------------------------------------------------------------------------
# ICP
# --------------------------------------------------------------------------
def oriented_match(A, src, src_tan, tree, dst_dir, thr, max_ang_deg=30.0, k=8):
    """Nearest OSM point within thr whose (undirected) orientation agrees."""
    w = apply(A, src)
    tw = src_tan @ A[:, :2].T
    phi = np.arctan2(tw[:, 1], tw[:, 0])
    d, idx = tree.query(w, k=k, distance_upper_bound=thr, workers=-1)
    n = len(dst_dir)
    valid = idx < n
    dphi = np.abs(((phi[:, None] - dst_dir[np.minimum(idx, n - 1)]) + np.pi / 2) % np.pi - np.pi / 2)
    ok = valid & (dphi < math.radians(max_ang_deg))
    first = np.argmax(ok, axis=1)
    has = ok[np.arange(len(w)), first]
    dd = np.where(has, d[np.arange(len(w)), first], np.inf)
    ii = np.where(has, idx[np.arange(len(w)), first], -1)
    return dd, ii


class Channel:
    """One feature type: lines digitised on the image + their reference lines."""

    def __init__(self, name, px_lines, ref_lines, weight, inlier_dist):
        self.name, self.w, self.inlier_dist = name, weight, inlier_dist
        self.px_lines = px_lines
        self.tpl_lines = [np.column_stack([l[:, 0], -l[:, 1]]) for l in px_lines]  # y up
        self.ref_lines = ref_lines

    def prepare(self, ref_step, src_step_px, max_src=20000):
        self.ref_step = ref_step
        self.ref_dense, self.ref_dir = densify_dirs(self.ref_lines, ref_step)
        self.tree = cKDTree(self.ref_dense)
        src, sdir = densify_dirs(self.tpl_lines, src_step_px)
        if len(src) > max_src:
            sel = np.linspace(0, len(src) - 1, max_src).astype(int)
            src, sdir = src[sel], sdir[sel]
        self.src, self.src_tan = src, np.column_stack([np.cos(sdir), np.sin(sdir)])


def match_all(A, chans, f):
    """Oriented matches for every channel at threshold f * channel.inlier_dist."""
    S, D, W = [], [], []
    for ch in chans:
        d, idx = oriented_match(A, ch.src, ch.src_tan, ch.tree, ch.ref_dir, f * ch.inlier_dist)
        m = np.isfinite(d)
        S.append(ch.src[m])
        D.append(ch.ref_dense[idx[m]])
        W.append(np.full(m.sum(), ch.w))
    return np.vstack(S), np.vstack(D), np.concatenate(W)


def icp(chans, A0, model, mirror, f_start, n_iter=60, anchors=None, anchor_weight=1.0):
    A = A0.copy()
    f = f_start
    n_src = sum(len(ch.src) for ch in chans)
    allsrc = np.vstack([ch.src for ch in chans])
    for it in range(n_iter):
        S, D, W = match_all(A, chans, f)
        if anchors is not None and len(anchors["tpl"]):
            na = len(anchors["tpl"])
            wa = anchor_weight * max(n_src, 1) / na
            S, D = np.vstack([S, anchors["tpl"]]), np.vstack([D, anchors["world"]])
            W = np.concatenate([W, np.full(na, wa)])
        if len(S) < max(10, 0.1 * n_src):
            break
        if model == "affine" and f <= 2:
            A_new = fit_affine(S, D, W)
        elif mirror:
            A_new = _fit_sim_mirror(S, D, W)
        else:
            A_new = fit_similarity(S, D, W)
        change = np.abs(apply(A_new, allsrc) - apply(A, allsrc)).max()
        A = A_new
        if f > 1:
            f = max(1.0, f * 0.7)
        elif change < 0.05 * chans[0].inlier_dist:
            break
    return A


def _fit_sim_mirror(src, dst, w=None):
    M = np.diag([-1.0, 1.0])
    A = fit_similarity(src @ M.T, dst, w)
    return np.column_stack([A[:, :2] @ M, A[:, 2]])


def evaluate(A, chans):
    """Metrics of the road channel + weighted soft score over all channels.
    soft score: ~1 for points right on a reference line, Gaussian decay
    (sigma = inlier_dist / 3), 0 for unmatched points."""
    out, num, den = {}, 0.0, 0.0
    for k, ch in enumerate(chans):
        d, _ = oriented_match(A, ch.src, ch.src_tan, ch.tree, ch.ref_dir, ch.inlier_dist)
        inl = np.isfinite(d)
        rmse = float(np.sqrt(np.mean(d[inl] ** 2))) if inl.any() else float("inf")
        soft = float(np.mean(np.where(inl, np.exp(-0.5 * (d / (ch.inlier_dist / 3.0)) ** 2), 0.0)))
        if k == 0:
            out.update(inlier_frac=float(inl.mean()), rmse_inliers_m=rmse, road_soft=soft)
        else:
            out[f"{ch.name}_inlier_frac"] = float(inl.mean())
            out[f"{ch.name}_rmse_m"] = rmse
            out[f"{ch.name}_soft"] = soft
        n = ch.w * len(ch.src)
        num += n * soft
        den += n
    out["soft_score"] = num / den
    return out


def contrast(A, chans, score, rng, n=24):
    """How much better the fit is than slightly perturbed copies of itself.
    A true match is a sharp peak (perturbed copies score low); a placement in a
    dense street network is a plateau (perturbed copies score about as well)."""
    allsrc = np.vstack([ch.src for ch in chans])
    c = apply(A, allsrc).mean(0)
    d0 = chans[0].inlier_dist
    fr = []
    for _ in range(n):
        a = rng.uniform(0, 2 * np.pi)
        dist = rng.uniform(4 * d0, 12 * d0)
        Rp = rot(rng.uniform(-6, 6))
        L = Rp @ A[:, :2]
        b = Rp @ (A[:, 2] - c) + c + dist * np.array([np.cos(a), np.sin(a)])
        fr.append(evaluate(np.column_stack([L, b]), chans)["soft_score"])
    base = float(np.mean(fr))
    return (score - base) / max(1e-6, 1.0 - base), base


# --------------------------------------------------------------------------
# GCP selection
# --------------------------------------------------------------------------
def turning_angle(pts, win):
    n = len(pts)
    out = np.zeros(n)
    for i in range(n):
        a, b = max(0, i - win), min(n - 1, i + win)
        if i - a < 1 or b - i < 1:
            continue
        v1, v2 = pts[i] - pts[a], pts[b] - pts[i]
        n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
        if n1 == 0 or n2 == 0:
            continue
        out[i] = math.acos(np.clip(v1 @ v2 / (n1 * n2), -1, 1))
    return out


def select_gcps(px_lines, A, osm_tree, osm_dense, n_gcps, inlier_dist, bend_window_m):
    gsd = decompose(A)["gsd_mean"]
    step_px = max(1.0, 10.0 / gsd)               # ~10 m along the road
    win = max(2, int(round(bend_window_m / 10.0)))
    cand = []
    for li, l in enumerate(px_lines):
        d = densify(l, step_px)
        tpl = np.column_stack([d[:, 0], -d[:, 1]])
        w = apply(A, tpl)
        dist, idx = osm_tree.query(w, workers=-1)
        ta = turning_angle(w, win)
        seg = np.hypot(*np.diff(d, axis=0).T) * gsd
        s = np.concatenate([[0], np.cumsum(seg)])
        for k in range(len(d)):
            cand.append((li, s[k], d[k, 0], d[k, 1], w[k, 0], w[k, 1],
                         osm_dense[idx[k], 0], osm_dense[idx[k], 1], dist[k], ta[k]))
    cand = np.array(cand)
    inl = cand[cand[:, 8] < inlier_dist]
    if len(inl) == 0:
        return []
    # global arc-length coordinate over all parts
    order = np.lexsort((inl[:, 1], inl[:, 0]))
    inl = inl[order]
    gs = np.zeros(len(inl))
    acc, last_li, last_s = 0.0, None, 0.0
    for i, r in enumerate(inl):
        if r[0] != last_li:
            last_li, last_s = r[0], r[1]
        acc += r[1] - last_s
        last_s = r[1]
        gs[i] = acc
    edges = np.linspace(0, gs[-1] + 1e-6, n_gcps + 1)
    gcps = []
    min_sep = 0.5 * (edges[1] - edges[0])
    last = -np.inf
    for a, b in zip(edges[:-1], edges[1:]):
        m = (gs >= max(a, last + min_sep)) & (gs < b)
        if not m.any():
            continue
        sub = inl[m]
        # prefer bends; among similar bends prefer small residual and mid-segment
        mid = 0.5 * (a + b)
        sc = sub[:, 9] - 0.002 * sub[:, 8] - 1e-5 * np.abs(gs[m] - mid)
        kbest = np.argmax(sc)
        r = sub[kbest]
        last = gs[m][kbest]
        gcps.append(dict(col=r[2], row=r[3], x_pred=r[4], y_pred=r[5],
                         x_snap=r[6], y_snap=r[7], residual_m=r[8],
                         bend_deg=math.degrees(r[9])))
    return gcps


# --------------------------------------------------------------------------
# camera model (Metashape frame camera) + DEM
# --------------------------------------------------------------------------
class FrameCamera:
    """Metashape 'frame' calibration (pixels). Camera axes: x right, y down, z forward."""

    def __init__(self, xml_path):
        import xml.etree.ElementTree as ET
        r = ET.parse(xml_path).getroot()

        def g(tag, default=0.0):
            e = r.find(tag)
            return float(e.text) if e is not None and e.text else default
        self.path = str(xml_path)
        self.w, self.h = g("width"), g("height")
        self.f, self.cx, self.cy = g("f"), g("cx"), g("cy")
        self.k = [g("k1"), g("k2"), g("k3"), g("k4")]
        self.p1, self.p2 = g("p1"), g("p2")
        self.b1, self.b2 = g("b1"), g("b2")
        proj = r.find("projection")
        if proj is not None and proj.text and proj.text.strip() != "frame":
            raise ValueError(f"only 'frame' calibrations are supported (got {proj.text})")
        if self.f <= 0:
            raise ValueError("calibration without focal length")

    @property
    def pp(self):
        return np.array([self.w / 2 + self.cx, self.h / 2 + self.cy])

    def project_cam(self, Pc):
        """Camera coordinates (N,3) -> pixel (col,row) (N,2); NaN behind the camera."""
        z = Pc[:, 2]
        with np.errstate(divide="ignore", invalid="ignore"):
            x, y = Pc[:, 0] / z, Pc[:, 1] / z
        r2 = x * x + y * y
        k1, k2, k3, k4 = self.k
        rad = 1 + r2 * (k1 + r2 * (k2 + r2 * (k3 + r2 * k4)))
        xd = x * rad + (self.p1 * (r2 + 2 * x * x) + 2 * self.p2 * x * y)
        yd = y * rad + (self.p2 * (r2 + 2 * y * y) + 2 * self.p1 * x * y)
        u = self.w / 2 + self.cx + xd * self.f + xd * self.b1 + yd * self.b2
        v = self.h / 2 + self.cy + yd * self.f
        uv = np.column_stack([u, v])
        uv[~(z > 0)] = np.nan
        return uv


def rodrigues(rv):
    th = np.linalg.norm(rv)
    if th < 1e-12:
        return np.eye(3)
    k = rv / th
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * K @ K


class Pose:
    """World (E, N, H) -> camera: Pc = R (Pw - C)."""

    def __init__(self, R, C):
        self.R, self.C = np.asarray(R, float), np.asarray(C, float)

    def project(self, cam, Pw):
        return cam.project_cam((Pw - self.C) @ self.R.T)

    def as_dict(self):
        R = self.R
        # omega-phi-kappa (photogrammetric, world->camera with z down-looking) for information
        return dict(C=self.C.tolist(), R=R.tolist(),
                    tilt_deg=float(math.degrees(math.acos(np.clip(-R[2, 2], -1, 1)))),
                    height_m=float(self.C[2]))


class DemSampler:
    """Bilinear DEM heights for points in the working CRS."""

    def __init__(self, dem_path, crs, bounds, margin=2000.0):
        import rasterio
        from rasterio.windows import from_bounds
        from pyproj import Transformer
        self.path = str(dem_path)
        self.ds = rasterio.open(dem_path)
        self.to_dem = Transformer.from_crs(crs, self.ds.crs, always_xy=True)
        x0, y0, x1, y1 = bounds
        xs, ys = self.to_dem.transform([x0 - margin, x1 + margin, x0 - margin, x1 + margin],
                                       [y0 - margin, y0 - margin, y1 + margin, y1 + margin])
        win = from_bounds(min(xs), min(ys), max(xs), max(ys), self.ds.transform).round_offsets().round_lengths()
        self.arr = self.ds.read(1, window=win, boundless=True, fill_value=np.nan).astype(np.float64)
        if self.ds.nodata is not None:
            self.arr[self.arr == self.ds.nodata] = np.nan
        self.tr = self.ds.window_transform(win)
        if np.isnan(self.arr).all():
            raise ValueError("DEM has no data over the area")
        self.fill = float(np.nanmedian(self.arr))

    def __call__(self, xy):
        from scipy.ndimage import map_coordinates
        X, Y = self.to_dem.transform(xy[:, 0], xy[:, 1])
        inv = ~self.tr
        c, r = inv * (np.asarray(X), np.asarray(Y))
        a = np.where(np.isnan(self.arr), self.fill, self.arr)
        z = map_coordinates(a, [np.asarray(r) - 0.5, np.asarray(c) - 0.5], order=1, mode="nearest")
        return z


def pose_from_similarity(A, cam, dem, inv_y=True):
    """Nadir camera above the principal point, height from the GSD."""
    pp = cam.pp
    tpl_pp = np.array([[pp[0], -pp[1]]])
    xy = apply(A, tpl_pp)[0]
    gsd = decompose(A)["gsd_mean"]
    # ground height: median over the footprint
    W, H = cam.w, cam.h
    grid = np.array([[c, -r] for c in np.linspace(0, W, 9) for r in np.linspace(0, H, 9)])
    zg = float(np.median(dem(apply(A, grid))))
    C = np.array([xy[0], xy[1], zg + cam.f * gsd])
    xa = np.array([A[0, 0], A[1, 0], 0.0])
    ya = -np.array([A[0, 1], A[1, 1], 0.0])
    xa /= np.linalg.norm(xa)
    ya -= xa * (xa @ ya)
    ya /= np.linalg.norm(ya)
    za = np.cross(xa, ya)
    R = np.vstack([xa, ya, za])
    return Pose(R, C), zg


class CamChannel:
    """A Channel seen in image space: drawn points (col,row) + 3D reference points."""

    def __init__(self, ch, dem, footprint_bounds, margin):
        x0, y0, x1, y1 = footprint_bounds
        m = (ch.ref_dense[:, 0] > x0 - margin) & (ch.ref_dense[:, 0] < x1 + margin) & \
            (ch.ref_dense[:, 1] > y0 - margin) & (ch.ref_dense[:, 1] < y1 + margin)
        xy = ch.ref_dense[m]
        self.P = np.column_stack([xy, dem(xy)]) if len(xy) else np.zeros((0, 3))
        d = ch.ref_dir[m]
        t = np.column_stack([np.cos(d), np.sin(d), np.zeros(len(d))]) * 5.0
        self.P2 = np.column_stack([xy, self.P[:, 2]]) + t if len(xy) else self.P
        self.img = np.column_stack([ch.src[:, 0], -ch.src[:, 1]])                 # (col,row)
        self.img_tan = np.column_stack([ch.src_tan[:, 0], -ch.src_tan[:, 1]])
        self.w, self.inlier_dist, self.name = ch.w, ch.inlier_dist, ch.name

    def match(self, pose, cam, thr_px, max_ang=30.0, k=8):
        if len(self.P) == 0:
            return np.zeros(0, int), np.zeros(0, int), np.zeros(0)
        uv = pose.project(cam, self.P)
        uv2 = pose.project(cam, self.P2)
        ok = np.isfinite(uv).all(1)
        idx_ok = np.nonzero(ok)[0]
        if len(idx_ok) == 0:
            return np.zeros(0, int), np.zeros(0, int), np.zeros(0)
        tree = cKDTree(uv[ok])
        d, ii = tree.query(self.img, k=k, distance_upper_bound=thr_px, workers=-1)
        n = len(idx_ok)
        valid = ii < n
        ref_idx = idx_ok[np.minimum(ii, n - 1)]
        tdir = uv2[ref_idx] - uv[ref_idx]
        phi_r = np.arctan2(tdir[..., 1], tdir[..., 0])
        phi_s = np.arctan2(self.img_tan[:, 1], self.img_tan[:, 0])[:, None]
        dphi = np.abs(((phi_s - phi_r) + np.pi / 2) % np.pi - np.pi / 2)
        okm = valid & (dphi < math.radians(max_ang))
        first = np.argmax(okm, axis=1)
        has = okm[np.arange(len(self.img)), first]
        src_i = np.nonzero(has)[0]
        ref_i = ref_idx[src_i, first[src_i]]
        dist = d[src_i, first[src_i]]
        return src_i, ref_i, dist


def refine_camera(channels, A, cam, dem, inlier_dist, n_outer=25, verbose=True, anchors=None,
                  anchor_weight=1.0):
    """6-parameter exterior orientation by ICP in image space. Returns (pose, report)."""
    from scipy.optimize import least_squares
    pose0, zg = pose_from_similarity(A, cam, dem)
    gsd = decompose(A)["gsd_mean"]
    W, H = cam.w, cam.h
    fp = apply(A, np.array([[0, 0], [W, 0], [W, -H], [0, -H]]))
    bounds = (fp[:, 0].min(), fp[:, 1].min(), fp[:, 0].max(), fp[:, 1].max())
    cchs = [CamChannel(ch, dem, bounds, 1500.0) for ch in channels]
    R0, C0 = pose0.R, pose0.C
    params = np.zeros(6)

    def pose_of(p):
        return Pose(rodrigues(p[:3]) @ R0, C0 + p[3:] * 100.0)    # translation in hm (scaling)

    thr_m = max(4 * inlier_dist, 120.0)
    last_n = -1
    for it in range(n_outer):
        pose = pose_of(params)
        pairs = []
        for cc in cchs:
            s, r, d = cc.match(pose, cam, thr_m * cc.inlier_dist / inlier_dist / gsd)
            if len(s):
                pairs.append((cc.img[s], cc.P[r], cc.P2[r], np.full(len(s), math.sqrt(cc.w))))
        if not pairs and anchors is None:
            break
        img = np.vstack([p[0] for p in pairs]) if pairs else np.zeros((0, 2))
        P = np.vstack([p[1] for p in pairs]) if pairs else np.zeros((0, 3))
        P2 = np.vstack([p[2] for p in pairs]) if pairs else np.zeros((0, 3))
        sw = np.concatenate([p[3] for p in pairs]) if pairs else np.zeros(0)
        if len(img) < 20 and anchors is None:
            break
        if anchors is not None:
            a_img, a_P = anchors["img"], anchors["P"]
            a_w = math.sqrt(anchor_weight * max(len(img), 20) / len(a_img))
        # point-to-line: normals of the projected reference lines (fixed during this step)
        uv, uv2 = pose.project(cam, P), pose.project(cam, P2)
        t = uv2 - uv
        t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
        nrm = np.column_stack([-t[:, 1], t[:, 0]])
        tan_w = 0.1                                  # small along-line term (keeps it well posed)

        def resid(p):
            pz = pose_of(p)
            e = pz.project(cam, P) - img
            e = np.nan_to_num(e, nan=1e4)
            r1 = np.sum(e * nrm, axis=1) * sw
            r2 = np.sum(e * t, axis=1) * sw * tan_w
            if anchors is None:
                return np.concatenate([r1, r2])
            ea = np.nan_to_num(pz.project(cam, a_P) - a_img, nan=1e4) * a_w
            return np.concatenate([r1, r2, ea.ravel()])
        sol = least_squares(resid, params, loss="soft_l1", f_scale=max(2.0, thr_m / gsd / 4), x_scale="jac",
                            max_nfev=200)
        change = np.abs(sol.x - params).max()
        params = sol.x
        if verbose:
            print(f"  [camera] it {it+1}: {len(img)} pairs within {thr_m:.0f} m"
                  + (f" + {len(anchors['img'])} anchors" if anchors is not None else ""))
        if thr_m > inlier_dist:
            thr_m = max(inlier_dist, thr_m * 0.7)
        elif change < 2e-4 and abs(len(img) - last_n) < 0.002 * len(img):
            break
        last_n = len(img)
    pose = pose_of(params)
    rep = camera_report(cchs, pose, cam, gsd, inlier_dist)
    if anchors is not None:
        ra = np.hypot(*(pose.project(cam, anchors["P"]) - anchors["img"]).T) * gsd
        rep["anchor_residuals_m"] = [float(v) for v in ra]
    rep.update(pose.as_dict(), ground_height_m=zg)
    return pose, cchs, rep


def camera_report(cchs, pose, cam, gsd, inlier_dist):
    out = {}
    for cc in cchs:
        s, r, d = cc.match(pose, cam, 1e6)
        dist = np.full(len(cc.img), np.inf)
        dist[s] = d * gsd
        inl = dist < cc.inlier_dist
        out[f"{cc.name}_inlier_frac"] = float(inl.mean()) if len(inl) else 0.0
        out[f"{cc.name}_rmse_m"] = float(np.sqrt(np.mean(dist[inl] ** 2))) if inl.any() else float("inf")
        if cc.name == cchs[0].name:
            out["thirds_median_m"] = thirds(cc.img[:, 0], dist, cam.w)
    return out


def thirds(cols, dist, W):
    res = []
    for lo, hi in ((0, W / 3), (W / 3, 2 * W / 3), (2 * W / 3, W)):
        m = (cols >= lo) & (cols < hi) & np.isfinite(dist)
        res.append(float(np.median(dist[m])) if m.any() else float("nan"))
    return res


def similarity_thirds(A, ch, W):
    d, _ = oriented_match(A, ch.src, ch.src_tan, ch.tree, ch.ref_dir, 1e9)
    return thirds(ch.src[:, 0], d, W)


def fit_quality(channels, A, good_m, pose=None, cam=None, cchs=None, gsd=None, W=None):
    """How well the drawn lines fit OSM with the final model: share of the drawn
    length within good_m of a same-direction OSM feature, median distance, and
    the left/centre/right median of the main feature."""
    per, dists = {}, []
    for k, ch in enumerate(channels):
        if pose is not None:
            cc = cchs[k]
            s_, r_, d_ = cc.match(pose, cam, 1e6)
            d = np.full(len(cc.img), np.inf)
            d[s_] = d_ * gsd
            cols = cc.img[:, 0]
        else:
            d, _ = oriented_match(A, ch.src, ch.src_tan, ch.tree, ch.ref_dir, 1e9)
            cols = ch.src[:, 0]
        per[ch.name] = dict(pct=float(np.mean(d <= good_m) * 100) if len(d) else 0.0,
                            median_m=float(np.median(np.minimum(d, 999))) if len(d) else 999.0)
        if k == 0:
            th = thirds(cols, np.minimum(d, 999), W)
        dists.append(d)
    d = np.concatenate(dists)
    return dict(pct=float(np.mean(d <= good_m) * 100), median_m=float(np.median(np.minimum(d, 999))),
                good_m=good_m, per_feature=per, thirds_median_m=th,
                model="camera" if pose is not None else "flat")


def select_gcps_camera(cc, pose, cam, gsd, n_gcps, bend_window_m):
    """GCPs along a channel, ground coordinates = matched OSM point (3D, DEM height)."""
    s, r, d = cc.match(pose, cam, cc.inlier_dist / gsd)
    if len(s) == 0:
        return []
    img = cc.img[s]
    order = np.arange(len(s))
    # arc length along the (densified, ordered) source points
    step = np.hypot(*np.diff(cc.img, axis=0).T)
    step[step > 50] = 0                                  # jumps between parts
    s_all = np.concatenate([[0], np.cumsum(step)]) * gsd
    gs = s_all[s]
    win = max(2, int(round(bend_window_m / max(step[step > 0].mean() * gsd if (step > 0).any() else 5, 1))))
    ta_all = turning_angle(cc.img, win)
    ta = ta_all[s]
    edges = np.linspace(gs.min(), gs.max() + 1e-6, n_gcps + 1)
    min_sep = 0.5 * (edges[1] - edges[0])
    last = -np.inf
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        m = (gs >= max(a, last + min_sep)) & (gs < b)
        if not m.any():
            continue
        sc = ta[m] - 0.02 * d[m] - 1e-5 * np.abs(gs[m] - 0.5 * (a + b))
        k = np.argmax(sc)
        j = order[m][k]
        last = gs[j]
        P = cc.P[r[j]]
        uvp = pose.project(cam, P[None])[0]
        out.append(dict(col=float(img[j, 0]), row=float(img[j, 1]), x_pred=float(P[0]), y_pred=float(P[1]),
                        x_snap=float(P[0]), y_snap=float(P[1]), z_dem=float(P[2]),
                        residual_m=float(d[j] * gsd), bend_deg=math.degrees(ta[j]),
                        reproj_px=float(np.hypot(*(uvp - img[j])))))
    return out


# --------------------------------------------------------------------------
# reference data
# --------------------------------------------------------------------------
def list_layers(path):
    try:
        import pyogrio
        return [str(l[0]) for l in pyogrio.list_layers(path)]
    except Exception:  # noqa
        return []


def load_ref_lines(path, layers, search_poly, crs, class_col=None, include=None, exclude=None,
                   label="ref"):
    """Read reference features (lines or polygons -> their outlines), clipped to
    the search area *after* taking polygon boundaries (no artificial clip edges)."""
    mask = gpd.GeoSeries([search_poly], crs=crs)
    out = []
    available = list_layers(path)
    for lay in layers:
        if lay is not None and available and lay not in available:
            print(f"[{label}] layer '{lay}' not in {Path(path).name}: skipped")
            continue
        g = gpd.read_file(path, layer=lay, mask=mask)
        if g.crs is None:
            g = g.set_crs(4326)
        g = g.to_crs(crs)
        col = class_col or next((c for c in ("highway", "fclass", "type") if c in g.columns), None)
        if col is not None and col in g.columns:
            n0 = len(g)
            if include:
                g = g[g[col].isin(include)]
            elif exclude:
                g = g[~g[col].isin(exclude)]
            if len(g) != n0:
                print(f"[{label}] layer {lay}: '{col}' filter kept {len(g)}/{n0}")
        geoms = [gg.boundary if gg is not None and gg.geom_type in ("Polygon", "MultiPolygon") else gg
                 for gg in g.geometry if gg is not None and not gg.is_empty]
        if not geoms:
            continue
        clipped = gpd.GeoSeries(geoms, crs=crs).clip(search_poly)
        out += [l for l in iter_lines(clipped) if len(l) > 1]
    n_km = sum(np.hypot(*np.diff(l, axis=0).T).sum() for l in out) / 1000
    print(f"[{label}] {path} layers {layers}: {len(out)} lines, {n_km:.0f} km")
    return out


def load_anchors(path, crs, pixel_scale=1.0):
    """Known GCPs of the image: CSV label, px_col, px_row, lon, lat[, z] (WGS84)."""
    import csv
    from pyproj import Transformer
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r_ in csv.DictReader(f):
            try:
                rows.append((r_.get("label", ""), float(r_["px_col"]), float(r_["px_row"]),
                             float(r_["lon"]), float(r_["lat"]),
                             float(r_["z"]) if r_.get("z") not in (None, "", "nan") else float("nan")))
            except (KeyError, ValueError):
                continue
    if not rows:
        print(f"[anchors] no usable row in {path}")
        return None
    tr = Transformer.from_crs(4326, crs, always_xy=True)
    lon = np.array([r_[3] for r_ in rows])
    lat = np.array([r_[4] for r_ in rows])
    x, y = tr.transform(lon, lat)
    return dict(labels=[r_[0] for r_ in rows],
                img=np.array([[r_[1] * pixel_scale, r_[2] * pixel_scale] for r_ in rows]),
                world=np.column_stack([x, y]), z=np.array([r_[5] for r_ in rows]))


def pick(lst, i):
    if not lst:
        return None
    return lst[i] if i < len(lst) else lst[-1]


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--road", default=None,
                    help="road digitised on the image (shp/gpkg/geojson), pixel space. Optional: "
                         "without it the first --aux feature (e.g. a lake shore) drives the match")
    ap.add_argument("--region", required=True, help="polygon of the search region")
    ap.add_argument("--osm", required=True,
                    help="OSM extract: 'roads' layer (+ 'water'/'waterways' layers used by --aux)")
    ap.add_argument("--image", help="image used in Metashape (for size/geotransform/VRT)")
    ap.add_argument("--osm-layer", default=None)
    ap.add_argument("--out", default=None, help="output directory (default: next to road file)")
    ap.add_argument("--camera-label", default=None, help="Metashape camera label (default: image stem)")
    ap.add_argument("--pixel-mode", default="auto", choices=["auto", "qgis", "raster", "direct"],
                    help="how road coords map to pixels: qgis = (x, -y), direct = (x, y), "
                         "raster = inverse of image geotransform")
    ap.add_argument("--pixel-scale", type=float, default=1.0,
                    help="multiply road pixel coords by this to reach the Metashape image "
                         "(e.g. 2 if digitised on a 2x downsampled copy)")
    ap.add_argument("--gsd-range", nargs=2, type=float, default=[0.5, 4.0], metavar=("MIN", "MAX"),
                    help="ground sampling distance range to search, m/pixel (narrow it if you can!)")
    ap.add_argument("--rotation-range", nargs=2, type=float, default=None, metavar=("CENTER", "HALFWIDTH"),
                    help="restrict rotation search, degrees (default: full 360)")
    ap.add_argument("--rotation-centers", nargs="+", type=float, default=None,
                    help="several rotation windows, e.g. R R-90 R-180 R+90 (with --rotation-halfwidth)")
    ap.add_argument("--rotation-halfwidth", type=float, default=15.0)
    ap.add_argument("--prior-center", nargs=2, type=float, default=None, metavar=("X", "Y"),
                    help="restrict the search to a disc around this point (working CRS, m)")
    ap.add_argument("--prior-radius", type=float, default=15000.0, help="m (with --prior-center)")
    ap.add_argument("--allow-mirror", action="store_true", help="also test mirrored images")
    ap.add_argument("--model", default="similarity", choices=["similarity", "affine"],
                    help="final transform model")
    ap.add_argument("--region-buffer", type=float, default=2000.0, help="m")
    ap.add_argument("--highway-col", default=None, help="OSM class column (auto: highway/fclass)")
    ap.add_argument("--exclude-classes", nargs="*", default=DEFAULT_EXCLUDE)
    ap.add_argument("--include-classes", nargs="*", default=None,
                    help="keep only these OSM classes (overrides exclude)")
    ap.add_argument("--coarse-cell", type=float, default=None, help="m (auto)")
    ap.add_argument("--fine-cell", type=float, default=None, help="m (auto)")
    ap.add_argument("--n-candidates", type=int, default=12, help="coarse candidates refined")
    ap.add_argument("--inlier-dist", type=float, default=30.0, help="m, final inlier threshold")
    ap.add_argument("--n-gcps", type=int, default=6,
                    help="GCPs along the road (fewer when the fit is loose, see --keep-n-gcps)")
    ap.add_argument("--keep-n-gcps", action="store_true",
                    help="do not reduce the number of GCPs when the fit is loose (rmse > 10 m)")
    ap.add_argument("--bend-window", type=float, default=80.0, help="m, for bend detection")
    ap.add_argument("--snap", action=argparse.BooleanOptionalAction, default=True,
                    help="use the nearest OSM point as ground coordinate (default) "
                         "instead of the transformed position")
    ap.add_argument("--dem", default=None, help="DEM to sample GCP heights (e.g. Copernicus GLO-30)")
    ap.add_argument("--fit-dist", type=float, default=15.0,
                    help="m: a drawn point 'fits' OSM when a same-direction OSM feature is this close")
    ap.add_argument("--camera-xml", default=None,
                    help="Metashape camera calibration (frame, XML export). With --dem: the flat "
                         "transform is refined into a full camera model (position, height, tilt) with "
                         "terrain heights, which removes the relief displacement of the photos")
    ap.add_argument("--crs", default=None, help="working metric CRS (default: UTM from region)")
    ap.add_argument("--aux", action="append", default=[],
                    help="extra feature digitised on the image (lake shore, river...), pixel space; "
                         "repeatable")
    ap.add_argument("--aux-ref", action="append", default=[],
                    help="reference file for each --aux (default: the --osm file)")
    ap.add_argument("--aux-ref-layer", action="append", default=[],
                    help="layer of --aux-ref (default: every layer whose name contains 'water')")
    ap.add_argument("--aux-extra-ref", action="append", default=[],
                    help="extra reference lines for each --aux, in the same order (all layers of the file, "
                         "e.g. the DEM river network of GAPPS_Tool_06d); 'none' for an aux without extra reference")
    ap.add_argument("--aux-weight", type=float, default=2.0,
                    help="weight of each --aux point relative to a road point (default 2)")
    ap.add_argument("--aux-inlier-factor", type=float, default=1.5,
                    help="aux inlier distance = factor x --inlier-dist (shorelines are fuzzier)")
    ap.add_argument("--aux-gcps", type=int, default=0,
                    help="also place N GCPs along each aux feature (e.g. lake shore)")
    ap.add_argument("--anchors", default=None,
                    help="CSV of GCPs already known on this image (e.g. Metashape markers): columns "
                         "label, px_col, px_row, lon, lat[, z]. >= 2: no search, the fit starts from them; "
                         "1: search limited around it. They are kept as strong constraints in the fits")
    ap.add_argument("--anchor-tol", type=float, default=250.0,
                    help="m: a candidate whose anchors fall further than this (flat fit) is rejected")
    ap.add_argument("--anchor-weight", type=float, default=1.0,
                    help="total weight of the anchors relative to all the drawn points (1 = same weight)")
    ap.add_argument("--init-from", default=None,
                    help="a previous *_transform.json: skip the search and refine one of its candidates")
    ap.add_argument("--label-prefix", default=None,
                    help="marker labels = <prefix>_<feature>_NN (must be unique per image in Metashape)")
    ap.add_argument("--master-csv", default=None,
                    help="combined GCP table for all images, updated at each run (rows of this camera "
                         "are replaced). Default: osm_gcps_all.csv in the parent of --out")
    ap.add_argument("--no-master", action="store_true", help="do not update the combined table")
    ap.add_argument("--init-candidate", type=int, default=1,
                    help="1-based candidate number in --init-from (as printed / labelled #k in the QA png)")
    return ap


def parse_args(argv=None):
    """Parse a CLI-style argument list (used by the GUI)."""
    return build_parser().parse_args(argv)


def main():
    run(parse_args())


def run(args):
    """Run the whole matching for one image. Returns a dict with the result
    (best candidate, all candidates, GCPs, flags, geotransform, output paths)."""
    t_start = time.time()
    if args.road is None and not args.aux:
        sys.exit("Give --road and/or at least one --aux feature.")
    road_path = Path(args.road) if args.road else Path(args.aux[0])
    stem = road_path.stem
    out = Path(args.out) if args.out else road_path.parent / f"osm_match_{stem}"
    out.mkdir(parents=True, exist_ok=True)
    camera = args.camera_label or (Path(args.image).stem if args.image else stem)

    # ---- features in pixel space
    pmode = args.pixel_mode
    px_lines, img_size = None, None
    if args.road:
        px_lines, pmode, img_size = road_to_pixels(gpd.read_file(args.road), args.image, pmode)
    aux_px = []
    for p in args.aux:
        l, pmode, sz = road_to_pixels(gpd.read_file(p), args.image, pmode, name=Path(p).stem)
        img_size = img_size or sz
        aux_px.append(l)
    if args.pixel_scale != 1.0:
        px_lines = [l * args.pixel_scale for l in px_lines] if px_lines else px_lines
        aux_px = [[l * args.pixel_scale for l in ls] for ls in aux_px]

    # ---- region & reference data
    region = gpd.read_file(args.region)
    if region.crs is None:
        region = region.set_crs(4326)
    crs = args.crs or region.to_crs(4326).estimate_utm_crs()
    region_u = region.to_crs(crs)
    reg_poly = region_u.geometry.union_all() if hasattr(region_u.geometry, "union_all") \
        else region_u.geometry.unary_union
    search_poly = reg_poly.buffer(args.region_buffer)
    anchors = None
    if args.anchors:
        anchors = load_anchors(args.anchors, crs, args.pixel_scale)
        if anchors is not None:
            print(f"[anchors] {len(anchors['labels'])} known GCP(s) on this image: {', '.join(anchors['labels'])}")
            if len(anchors["labels"]) == 1:
                allpx = np.vstack([l for l in px_lines] + [l for ls in aux_px for l in ls]) \
                    if px_lines else np.vstack([l for ls in aux_px for l in ls])
                d_px = np.hypot(*(allpx - anchors["img"][0]).T).max()
                rad = d_px * args.gsd_range[1] * 1.1 + 1500.0
                disc = Point(*anchors["world"][0]).buffer(rad)
                if search_poly.intersects(disc):
                    search_poly = search_poly.intersection(disc)
                print(f"[anchors] one anchor: search limited to {rad/1000:.1f} km around it")
    if args.prior_center:
        disc = Point(*args.prior_center).buffer(args.prior_radius)
        if search_poly.intersects(disc):
            search_poly = search_poly.intersection(disc)
            print(f"[prior] search limited to {args.prior_radius/1000:.0f} km around "
                  f"{args.prior_center[0]:.0f} {args.prior_center[1]:.0f}")
    print(f"[region] working CRS {crs.to_string() if hasattr(crs, 'to_string') else crs}; "
          f"extent {(search_poly.bounds[2]-search_poly.bounds[0])/1000:.1f} x "
          f"{(search_poly.bounds[3]-search_poly.bounds[1])/1000:.1f} km")
    osm_layers_all = list_layers(args.osm)
    osm_layer = args.osm_layer or ("roads" if "roads" in osm_layers_all else
                                   (osm_layers_all[0] if osm_layers_all else None))
    channels = []
    osm_lines = []
    if args.road:
        osm_lines = load_ref_lines(args.osm, [osm_layer], search_poly, crs, args.highway_col,
                                   args.include_classes, args.exclude_classes, label="osm roads")
        if not osm_lines:
            sys.exit("No OSM roads in the region.")
        channels.append(Channel("road", px_lines, osm_lines, 1.0, args.inlier_dist))
    for i, p in enumerate(args.aux):
        ref_path = pick(args.aux_ref, i) or args.osm
        ref_layer = pick(args.aux_ref_layer, i)
        if ref_layer:
            layers = [l for l in ref_layer.split(",") if l]
        else:
            lays = list_layers(ref_path)
            layers = [l for l in lays if "water" in l.lower()] or (lays[:1] if len(lays) == 1 else [])
            has_extra = i < len(args.aux_extra_ref) and args.aux_extra_ref[i] and \
                args.aux_extra_ref[i].lower() != "none"
            if not layers and not has_extra:
                print(f"[warn] no water layer found in {ref_path} for {p}; pass --aux-ref-layer. Skipped.")
                continue
        ref_lines = load_ref_lines(ref_path, layers, search_poly, crs, label=Path(p).stem) if layers else []
        extra = args.aux_extra_ref[i] if i < len(args.aux_extra_ref) else None
        if extra and extra.lower() != "none":
            if Path(extra).exists():
                ex_lines = load_ref_lines(extra, list_layers(extra) or [None], search_poly, crs,
                                          label=Path(p).stem + " + extra")
                ref_lines = ref_lines + ex_lines
            else:
                print(f"[warn] extra reference not found: {extra}")
        if not ref_lines:
            print(f"[warn] no reference lines for {p} in the region; skipped")
            continue
        channels.append(Channel(Path(p).stem, aux_px[i], ref_lines,
                                args.aux_weight if channels else 1.0,
                                args.inlier_dist * args.aux_inlier_factor))
    if not channels:
        sys.exit("No usable feature (no reference data found).")
    if not args.road:
        print(f"[info] no --road: '{channels[0].name}' is the main feature "
              f"(GCPs placed along it: --n-gcps)")

    road_ch = channels[0]          # main feature (road, or first --aux without --road)
    tpl_lines = road_ch.tpl_lines
    tpl_all = np.vstack([l for ch in channels for l in ch.tpl_lines])
    tpl_len_px = sum(np.hypot(*np.diff(l, axis=0).T).sum() for l in tpl_lines)

    gmin, gmax = args.gsd_range
    centroid = tpl_all.mean(0)
    bx = search_poly.bounds
    extent = max(bx[2] - bx[0], bx[3] - bx[1])
    # template radius (m) at max gsd drives angular / scale resolution
    R_px = np.hypot(*(tpl_all - centroid).T).max()
    print(f"[{road_ch.name}] length {tpl_len_px:.0f} px  (= {tpl_len_px*gmin/1000:.1f}-{tpl_len_px*gmax/1000:.1f} km "
          f"for GSD {gmin}-{gmax} m/px)" + (f"; + {len(channels)-1} aux feature(s): "
                                            + ", ".join(ch.name for ch in channels[1:]) if len(channels) > 1 else ""))

    if anchors is not None:
        anchors["tpl"] = np.column_stack([anchors["img"][:, 0], -anchors["img"][:, 1]])
    if anchors is not None and len(anchors["labels"]) >= 2 and not args.init_from:
        A_anchor = fit_similarity(anchors["tpl"], anchors["world"])
        res_a = np.hypot(*(apply(A_anchor, anchors["tpl"]) - anchors["world"]).T)
        pa = decompose(A_anchor)
        print(f"[anchors] start from the {len(res_a)} anchors: GSD {pa['gsd_mean']:.3f} m/px, rotation "
              f"{pa['rotation_deg']:.1f} deg, residuals {', '.join(f'{v:.0f}' for v in res_a)} m (flat fit)")
        cands = [("anchors", None, None, False, None, None)]
        A_init = A_anchor
        rel_c, cell_c, sig_c = 0.0, 0.0, 0.0
    elif args.init_from:
        prev = json.loads(Path(args.init_from).read_text())
        cand_prev = prev["candidates"][args.init_candidate - 1]
        cands = [("init", None, None, bool(cand_prev.get("mirrored", False)), None, None)]
        A_init = np.array(cand_prev["A"])
        if prev.get("crs") and prev["crs"] != crs.to_string():
            sys.exit(f"--init-from was computed in {prev['crs']}, current CRS is {crs.to_string()}; pass --crs")
        print(f"[init] refining candidate {args.init_candidate} from {args.init_from} "
              f"(gsd {cand_prev['gsd_mean']:.3f}, rot {cand_prev['rotation_deg']:.1f})")
        rel_c, cell_c, sig_c = 0.0, 0.0, 0.0
    else:
        cands, A_init = None, None

    # ---- coarse global search
    if cands is None:
        cell_c = args.coarse_cell or max(60.0, extent / 1400.0, R_px * gmin / 60.0)
        sig_c = 2.0 * cell_c
        grid_c = Grid(bx, cell_c)
        P_cs, chans_c = [], []
        for ch in channels:
            d, dr = densify_dirs(ch.ref_lines, cell_c / 3)
            P_cs.append(proximity_raster(d, dr, cell_c / 3, grid_c, sig_c))
            p, pdir = densify_dirs([l - centroid for l in ch.tpl_lines], cell_c / (3 * gmax))
            chans_c.append((p, pdir, ch.w))
        ang_step_c = float(np.clip(math.degrees(sig_c / (R_px * gmax)), 0.5, 4.0))
        rel_c = float(np.clip(sig_c / (R_px * gmax), 0.01, 0.06))
        gsds_c = geometric_steps(gmin, gmax, rel_c)
        if args.rotation_centers:
            angles_c = np.unique(np.round(np.concatenate(
                [angle_steps(c, args.rotation_halfwidth, ang_step_c) for c in args.rotation_centers]), 3))
        elif args.rotation_range:
            angles_c = angle_steps(args.rotation_range[0], args.rotation_range[1], ang_step_c)
        else:
            angles_c = np.arange(0, 360, ang_step_c)
        mirrors = [False, True] if args.allow_mirror else [False]
        print(f"[coarse] cell {cell_c:.0f} m, grid {grid_c.W}x{grid_c.H}, "
              f"{len(gsds_c)} scales x {len(angles_c)} angles x {len(mirrors)} x {len(channels)} channel(s)")
        res_c = fft_search(P_cs, grid_c, chans_c, gsds_c, angles_c, mirrors, n_peaks=2, label="coarse")
        min_d = 0.3 * R_px * gmin
        cands = nms(res_c, min_d, 3 * ang_step_c, args.n_candidates)

    # ---- fine search + ICP for each candidate
    cell_f = args.fine_cell or max(10.0, cell_c / 4)
    sig_f = 2.0 * cell_f
    osm_step = min(5.0, cell_f / 3) if cell_f else 5.0
    for ch in channels:
        ch.prepare(osm_step, max(0.5, 5.0 / gmax))      # ~5-20 m spacing on the image features

    refined = []
    for ci, (score, g, th, mir, tx, ty) in enumerate(cands):
        if A_init is not None:
            best_f = (float("nan"),)
            score = float("nan")
            A = icp(channels, A_init, args.model, mir, f_start=3.0, anchors=anchors,
                    anchor_weight=args.anchor_weight)
        else:
            R_m = R_px * g * (1 + 2 * rel_c)
            margin = R_m + 4 * sig_c + 2 * cell_c
            fb = (tx - margin, ty - margin, tx + margin, ty + margin)
            grid_f = Grid(fb, cell_f)
            P_fs, chans_f = [], []
            for ch in channels:
                P_fs.append(proximity_raster(ch.ref_dense, ch.ref_dir, osm_step, grid_f, sig_f))
                p, pdir = densify_dirs([l - centroid for l in ch.tpl_lines], cell_f / (3 * g))
                chans_f.append((p, pdir, ch.w))
            ang_step_f = float(np.clip(math.degrees(sig_f / (R_px * g)), 0.1, 2.0))
            rel_f = float(np.clip(sig_f / (R_px * g), 0.003, 0.05))
            gsds_f = geometric_steps(g / (1 + 1.5 * rel_c), g * (1 + 1.5 * rel_c), rel_f)
            angles_f = angle_steps(th, 1.5 * ang_step_c, ang_step_f)
            res_f = fft_search(P_fs, grid_f, chans_f, gsds_f, angles_f, [mir], n_peaks=1,
                               label=f"fine #{ci+1}/{len(cands)}")
            best_f = max(res_f, key=lambda r: r[0])
            A0 = make_similarity(best_f[1], best_f[2], mir, centroid, np.array(best_f[4:6]))
            A = icp(channels, A0, args.model, mir, f_start=3 * sig_f / args.inlier_dist, anchors=anchors,
                    anchor_weight=args.anchor_weight)
        met = evaluate(A, channels)
        if anchors is not None:
            ra = np.hypot(*(apply(A, anchors["tpl"]) - anchors["world"]).T)
            met["anchor_max_m"] = float(ra.max())
            met["anchor_ok"] = bool(ra.max() <= args.anchor_tol)
        con, base = contrast(A, channels, met["soft_score"], np.random.default_rng(ci))
        par = decompose(A)
        cw = apply(A, centroid[None])[0]
        refined.append(dict(A=A, coarse_score=score, fine_score=best_f[0], contrast=con,
                            background_frac=base, center_x=float(cw[0]), center_y=float(cw[1]),
                            **met, **par))
        aux_txt = "".join(f"  {ch.name} {met[ch.name + '_inlier_frac']*100:.0f}%" for ch in channels[1:])
        print(f"  cand {ci+1}: contrast {con:.2f} (soft {met['soft_score']:.2f} vs background {base:.2f})  "
              f"{road_ch.name} inliers {met['inlier_frac']*100:.0f}% rmse {met['rmse_inliers_m']:.1f} m{aux_txt}  "
              f"gsd {par['gsd_mean']:.3f}  rot {par['rotation_deg']:.1f}  centre {cw[0]:.0f} {cw[1]:.0f}")

    if anchors is not None:     # candidates consistent with the known GCPs first
        refined.sort(key=lambda r: (not r.get("anchor_ok", True), -r["contrast"]))
    else:
        refined.sort(key=lambda r: -r["contrast"])
    # different starting points often converge to the same fit: keep distinct ones only
    uniq = []
    for r_ in refined:
        if not any(math.hypot(r_["center_x"] - u["center_x"], r_["center_y"] - u["center_y"]) < 3 * args.inlier_dist
                   and abs((r_["rotation_deg"] - u["rotation_deg"] + 180) % 360 - 180) < 2
                   and abs(math.log(r_["gsd_mean"] / u["gsd_mean"])) < 0.02 for u in uniq):
            uniq.append(r_)
    if len(uniq) < len(refined):
        print(f"[candidates] {len(refined)} refined -> {len(uniq)} distinct")
    refined = uniq
    best = refined[0]
    A = best["A"]
    second = None
    for r in refined[1:]:
        c1, c2 = apply(A, centroid[None])[0], apply(r["A"], centroid[None])[0]
        if np.hypot(*(c1 - c2)) > 0.3 * R_px * best["gsd_mean"] or \
                abs((r["rotation_deg"] - best["rotation_deg"] + 180) % 360 - 180) > 10:
            second = r
            break
    ratio = (max(second["contrast"], 0) / best["contrast"]) if second and best["contrast"] > 0 else 0.0
    print(f"\n[result] contrast {best['contrast']:.2f}  {road_ch.name} inliers {best['inlier_frac']*100:.0f}%  "
          f"rmse {best['rmse_inliers_m']:.1f} m  GSD {best['gsd_mean']:.3f} m/px  "
          f"rotation {best['rotation_deg']:.1f} deg  centre {best['center_x']:.0f} {best['center_y']:.0f}")
    flags = []
    if best["inlier_frac"] < 0.4:
        flags.append("LOW_INLIERS")
    if not args.road and len(channels) == 1:
        print("[note] single outline only: a short or straight shore can fit several places; "
              "check the QA figure (a river or second outline helps)")
    if best["contrast"] < 0.25:
        flags.append("LOW_CONTRAST")
    if ratio > 0.85:
        flags.append("AMBIGUOUS")
    if best["gsd_mean"] < gmin * 1.02 or best["gsd_mean"] > gmax / 1.02:
        flags.append("GSD_AT_SEARCH_BOUND")
    if anchors is not None and len(anchors["labels"]) >= 2 and best.get("anchor_ok", False):
        flags = [f_ for f_ in flags if f_ not in ("AMBIGUOUS", "LOW_CONTRAST")]   # location given by the anchors
    if anchors is not None and not best.get("anchor_ok", True):
        flags.append("ANCHOR_MISMATCH")
    if flags:
        print(f"[WARNING] {', '.join(flags)} - check the QA figure before trusting the GCPs "
              f"(2nd-best/best contrast ratio = {ratio:.2f})")

    # ---- camera model refinement (relief + tilt) -------------------------------
    pose, cchs, cam_rep, cam = None, None, None, None
    if args.camera_xml and args.dem:
        try:
            cam = FrameCamera(args.camera_xml)
            if img_size and (abs(cam.w - img_size[0] * args.pixel_scale) > 1 or
                             abs(cam.h - img_size[1] * args.pixel_scale) > 1):
                print(f"[warn] calibration is for {cam.w:.0f}x{cam.h:.0f} px, image is "
                      f"{img_size[0]}x{img_size[1]}: camera model skipped")
                raise RuntimeError("size mismatch")
            fp0 = apply(A, np.array([[0, 0], [cam.w, 0], [cam.w, -cam.h], [0, -cam.h]]))
            dem_s = DemSampler(args.dem, crs, (fp0[:, 0].min(), fp0[:, 1].min(), fp0[:, 0].max(), fp0[:, 1].max()))
            print(f"[camera] refining with {Path(args.camera_xml).name} (f = {cam.f:.0f} px) and "
                  f"{Path(args.dem).name}")
            sim3 = similarity_thirds(A, road_ch, cam.w)
            cam_anchors = None
            if anchors is not None:
                za = anchors["z"].copy()
                miss = ~np.isfinite(za)
                if miss.any():
                    za[miss] = dem_s(anchors["world"][miss])
                cam_anchors = dict(img=anchors["img"], P=np.column_stack([anchors["world"], za]))
            pose, cchs, cam_rep = refine_camera(channels, A, cam, dem_s, args.inlier_dist, anchors=cam_anchors,
                                                anchor_weight=args.anchor_weight)
            if cam_anchors is not None:
                print("[camera] anchors residual: " + ", ".join(
                    f"{l} {v:.1f} m" for l, v in zip(anchors["labels"], cam_rep["anchor_residuals_m"])))
            c3 = cam_rep["thirds_median_m"]
            print(f"[camera] height {cam_rep['height_m']:.0f} m (ground ~{cam_rep['ground_height_m']:.0f} m), "
                  f"tilt {cam_rep['tilt_deg']:.1f} deg")
            print("[camera] median distance of the drawn " + road_ch.name + " to OSM, left / centre / right "
                  f"third of the image:\n         flat transform: {sim3[0]:.0f} / {sim3[1]:.0f} / {sim3[2]:.0f} m"
                  f"\n         camera model  : {c3[0]:.0f} / {c3[1]:.0f} / {c3[2]:.0f} m")
            print(f"[camera] {road_ch.name} inliers {cam_rep[road_ch.name + '_inlier_frac']*100:.0f}% "
                  f"rmse {cam_rep[road_ch.name + '_rmse_m']:.1f} m" +
                  "".join(f"; {c.name} {cam_rep[c.name + '_inlier_frac']*100:.0f}%" for c in cchs[1:]))
        except Exception as e:  # noqa
            if str(e) != "size mismatch":
                print(f"[warn] camera model failed ({e}); using the flat transform")
            pose, cchs, cam_rep = None, None, None

    # ---- fit quality with the final model
    W_img = cam.w if cam is not None else (img_size[0] * args.pixel_scale if img_size else 8100)
    fit = fit_quality(channels, A, args.fit_dist, pose, cam, cchs, best["gsd_mean"], W_img)
    t3 = fit["thirds_median_m"]
    per_txt = ", ".join("%s %.0f%%" % (k, v["pct"]) for k, v in fit["per_feature"].items())
    print(f"[fit] {fit['pct']:.0f}% of the drawn lines within {args.fit_dist:.0f} m of OSM ({per_txt}); "
          f"median {fit['median_m']:.0f} m; {road_ch.name} left/centre/right {t3[0]:.0f}/{t3[1]:.0f}/{t3[2]:.0f} m "
          f"[{fit['model']} model]")

    # ---- GCPs: fewer when the fit is loose (they are then only seeds to be moved by hand; with the
    # projections into the overlapping images, a few per image are enough to georeference the block)
    gsd_b = best["gsd_mean"]
    rm_fit = cam_rep[road_ch.name + "_rmse_m"] if cam_rep else best["rmse_inliers_m"]
    n_fac = 1.0 if (args.keep_n_gcps or rm_fit <= 10) else (0.6 if rm_fit <= 20 else 0.4)
    n_road = max(3, int(round(args.n_gcps * n_fac))) if args.n_gcps > 0 else 0
    n_aux = max(2, int(round(args.aux_gcps * n_fac))) if args.aux_gcps > 0 else 0
    if n_fac < 1:
        print(f"[gcps] fit rmse {rm_fit:.0f} m: {n_road} GCPs along the {road_ch.name}"
              + (f", {n_aux} along each other feature" if n_aux else "") + " (--keep-n-gcps to keep them all)")
    if pose is not None:
        gcps = select_gcps_camera(cchs[0], pose, cam, gsd_b, n_road, args.bend_window)
        for g in gcps:
            g["feature"] = road_ch.name
        if n_aux > 0:
            for cc in cchs[1:]:
                ga = select_gcps_camera(cc, pose, cam, gsd_b, n_aux, args.bend_window)
                for g in ga:
                    g["feature"] = cc.name
                gcps += ga
    else:
        gcps = select_gcps(road_ch.px_lines, A, road_ch.tree, road_ch.ref_dense, n_road,
                           road_ch.inlier_dist, args.bend_window)
        for g in gcps:
            g["feature"] = road_ch.name
        if n_aux > 0:
            for ch in channels[1:]:
                ga = select_gcps(ch.px_lines, A, ch.tree, ch.ref_dense, n_aux,
                                 ch.inlier_dist, args.bend_window)
                for g in ga:
                    g["feature"] = ch.name
                gcps += ga
    from pyproj import Transformer
    to_ll = Transformer.from_crs(crs, 4326, always_xy=True)
    counters = {}
    for g in gcps:
        counters[g["feature"]] = counters.get(g["feature"], 0) + 1
        if args.label_prefix:
            g["label"] = f"{args.label_prefix}_{g['feature']}_{counters[g['feature']]:02d}"
        else:
            tag = "" if g["feature"] == road_ch.name else f"{g['feature']}_"
            g["label"] = f"osm_{stem}_{tag}{counters[g['feature']]:02d}"
        g["x"], g["y"] = (g["x_snap"], g["y_snap"]) if args.snap else (g["x_pred"], g["y_pred"])
        g["lon"], g["lat"] = to_ll.transform(g["x"], g["y"])
        g["z"] = g.get("z_dem", float("nan"))
        rm = cam_rep[road_ch.name + "_rmse_m"] if cam_rep else best["rmse_inliers_m"]
        g["acc_xy_m"] = float(max(rm, g["residual_m"], 5.0))
    if args.dem and gcps and pose is None:
        try:
            import rasterio
            with rasterio.open(args.dem) as dem:
                tdem = Transformer.from_crs(crs, dem.crs, always_xy=True)
                xy = [tdem.transform(g["x"], g["y"]) for g in gcps]
                for g, v in zip(gcps, dem.sample(xy)):
                    val = float(v[0])
                    if dem.nodata is None or val != dem.nodata:
                        g["z"] = val
        except Exception as e:  # noqa
            print(f"[warn] DEM sampling failed: {e}")

    # ---- write outputs
    import csv
    csv_path = out / f"{stem}_gcps.csv"
    with open(csv_path, "w", newline="") as f:
        wr = csv.writer(f)
        # GCP coordinates are exported in WGS84 only (lon, lat; z = DEM height): the UTM working CRS of
        # the matching stays internal (convert older files with GAPPS_Tool_06e_GCPs_UTM2WGS84.py)
        wr.writerow(["label", "camera", "px_col", "px_row", "lon", "lat", "z",
                     "acc_xy_m", "residual_m", "bend_deg", "feature", "crs"])
        for g in gcps:
            wr.writerow([g["label"], camera, f"{g['col']:.2f}", f"{g['row']:.2f}",
                         f"{g['lon']:.8f}", f"{g['lat']:.8f}",
                         "" if math.isnan(g["z"]) else f"{g['z']:.2f}",
                         f"{g['acc_xy_m']:.1f}",
                         f"{g['residual_m']:.1f}", f"{g['bend_deg']:.0f}", g["feature"], WGS84_AUTH])

    # transform in (col,row) -> UTM, i.e. GDAL geotransform
    L, b = A[:, :2], A[:, 2]
    gt = [b[0], L[0, 0], -L[0, 1], b[1], L[1, 0], -L[1, 1]]
    tjson = dict(
        road=str(road_path), image=args.image, camera=camera, crs=crs.to_string(),
        pixel_mode=pmode, pixel_scale=args.pixel_scale, model=args.model,
        gdal_geotransform_col_row_to_crs=gt,
        image_size=([float(cam.w), float(cam.h)] if cam is not None else
                    ([float(v * args.pixel_scale) for v in img_size] if img_size else None)),
        note="X = gt0 + col*gt1 + row*gt2 ; Y = gt3 + col*gt4 + row*gt5 (pixel-corner convention)",
        metrics={k: v for k, v in best.items() if k not in ("A", "gsd_mean", "gsd_x", "gsd_y",
                                                             "rotation_deg", "mirrored", "shear")},
        aux_features=[dict(name=ch.name, weight=ch.w, inlier_dist=ch.inlier_dist) for ch in channels[1:]],
        camera_model=(dict(calibration=args.camera_xml, dem=args.dem, **cam_rep) if cam_rep else None),
        fit=fit,
        anchors=(dict(labels=anchors["labels"],
                      flat_residuals_m=[float(v) for v in np.hypot(*(apply(A, anchors["tpl"]) - anchors["world"]).T)],
                      camera_residuals_m=(cam_rep or {}).get("anchor_residuals_m")) if anchors is not None else None),
        parameters={k: best[k] for k in ("gsd_mean", "gsd_x", "gsd_y", "rotation_deg",
                                         "mirrored", "shear")},
        second_best_contrast_ratio=ratio, flags=flags,
        candidates=[{k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in r.items()}
                    for r in refined],
    )
    (out / f"{stem}_transform.json").write_text(json.dumps(tjson, indent=2, default=float))

    def px2w(col_, row_):
        return gt[0] + col_ * gt[1] + row_ * gt[2], gt[3] + col_ * gt[4] + row_ * gt[5]

    road_w = [LineString(apply(A, l)) for l in tpl_lines if len(l) > 1]
    aux_w = [LineString(apply(A, l)) for ch in channels[1:] for l in ch.tpl_lines if len(l) > 1]
    aux_ref = [l for ch in channels[1:] for l in ch.ref_lines]
    gpkg = out / f"{stem}_match.gpkg"
    # all the layers in WGS84 (EPSG:4326), like the GCP table
    gpd.GeoDataFrame(dict(name=[stem]), geometry=[MultiLineString(road_w)], crs=crs) \
        .to_crs(4326).to_file(gpkg, layer="road_georef", driver="GPKG")
    if aux_w:
        gpd.GeoDataFrame(dict(name=["aux"]), geometry=[MultiLineString(aux_w)], crs=crs) \
            .to_crs(4326).to_file(gpkg, layer="aux_georef", driver="GPKG")
    if gcps:
        utm_keys = {"x", "y", "x_pred", "y_pred", "x_snap", "y_snap"}
        gpd.GeoDataFrame([{k: v for k, v in g.items() if k not in utm_keys} for g in gcps],
                         geometry=[Point(g["x"], g["y"]) for g in gcps], crs=crs) \
            .to_crs(4326).to_file(gpkg, layer="gcps", driver="GPKG")
    if img_size:
        W_, H_ = [s * args.pixel_scale for s in img_size]
        fp = Polygon([px2w(0, 0), px2w(W_, 0), px2w(W_, H_), px2w(0, H_)])
        gpd.GeoDataFrame(dict(name=[camera]), geometry=[fp], crs=crs) \
            .to_crs(4326).to_file(gpkg, layer="footprint", driver="GPKG")

    if args.image:
        try:
            from osgeo import gdal, osr
            if args.pixel_scale != 1.0:
                raise RuntimeError("pixel-scale != 1, VRT skipped")
            srs = osr.SpatialReference()
            srs.SetFromUserInput(crs.to_wkt())
            vrt = gdal.Translate(str(out / f"{stem}_georef.vrt"), args.image, format="VRT")
            vrt.SetGeoTransform(gt)
            vrt.SetProjection(srs.ExportToWkt())
            vrt = None
            print(f"[out] georeferenced VRT: {out / f'{stem}_georef.vrt'}")
        except Exception as e:  # noqa
            # world file fallback
            wld = out / f"{Path(args.image).stem}.wld"
            c0 = px2w(0.5, 0.5)
            wld.write_text("\n".join(f"{v:.10f}" for v in
                                     [gt[1], gt[4], gt[2], gt[5], c0[0], c0[1]]) + "\n")
            print(f"[out] no VRT ({e}); world file written: {wld} (copy next to the image, CRS {crs})")

    # ---- QA figure
    try:
        qa_plot(out / f"{stem}_match_qa.png", osm_lines, reg_poly, road_w, gcps,
                refined, centroid, best, args.image, gt, img_size, args.pixel_scale,
                aux_ref=aux_ref, aux_w=aux_w)
    except Exception as e:  # noqa
        print(f"[warn] QA plot failed: {e}")

    if not args.no_master:
        master = Path(args.master_csv) if args.master_csv else out.resolve().parent / "osm_gcps_all.csv"
        n_kept, n_new = update_master_csv(master, csv_path, camera, flags)
        print(f"[out] {master}  ({n_new} rows for {camera}, {n_kept} rows of other images kept)")

    print(f"[out] {csv_path}\n[out] {gpkg}\n[done] {time.time() - t_start:.0f} s")
    return dict(best=best, candidates=refined, gcps=gcps, flags=flags, gt=gt, crs=crs.to_string(),
                camera_model=(dict(calibration=args.camera_xml, dem=args.dem, **cam_rep) if cam_rep else None),
                fit=fit, n_anchors=(len(anchors["labels"]) if anchors is not None else 0),
                camera=camera, out=str(out), csv=str(csv_path), gpkg=str(gpkg),
                transform_json=str(out / f"{stem}_transform.json"),
                qa_png=str(out / f"{stem}_match_qa.png"), seconds=time.time() - t_start)


WGS84_AUTH = "EPSG::4326"  # CRS of all the GCP coordinates written by the tool


SERIOUS_FLAGS = {"AMBIGUOUS", "LOW_CONTRAST", "GSD_AT_SEARCH_BOUND", "ANCHOR_MISMATCH"}
PROJ_MARGIN = 0.03        # GCPs projected into another image only if inside it (margin: fraction of the size)


def _cam_from_dict(d):
    cam = FrameCamera.__new__(FrameCamera)
    cam.path = d.get("path", "")
    cam.w, cam.h, cam.f, cam.cx, cam.cy = d["w"], d["h"], d["f"], d["cx"], d["cy"]
    cam.k, cam.p1, cam.p2, cam.b1, cam.b2 = list(d["k"]), d["p1"], d["p2"], d["b1"], d["b2"]
    return cam


def pose_record(transform_json, flags, gcp_rows=()):
    """What is needed to project ground points into an image, from its <stem>_transform.json:
    camera model (calibration, R, C) or flat transform (geotransform), image size, flags, accuracy."""
    d = json.loads(Path(transform_json).read_text())
    acc = [float(r["acc_xy_m"]) for r in gcp_rows if r.get("acc_xy_m")]
    rec = dict(crs=d["crs"], gt=d["gdal_geotransform_col_row_to_crs"], size=d.get("image_size"),
               flags=list(flags), acc_m=float(np.median(acc)) if acc else 20.0, model="flat")
    cm = d.get("camera_model") or {}
    if cm.get("C") and cm.get("R") and cm.get("calibration"):
        try:
            c = FrameCamera(str(cm["calibration"]).strip().strip('"'))
            rec.update(model="camera", C=cm["C"], R=cm["R"], ground_h=cm.get("ground_height_m"),
                       calib=dict(path=c.path, w=c.w, h=c.h, f=c.f, cx=c.cx, cy=c.cy, k=c.k,
                                  p1=c.p1, p2=c.p2, b1=c.b1, b2=c.b2))
            rec["size"] = [c.w, c.h]
        except Exception as e:  # noqa
            print(f"[warn] {Path(transform_json).name}: calibration unreadable ({e}): flat transform used "
                  f"for the projections")
    return rec


def project_lonlat(rec, lon, lat, z):
    """Pixel (col, row) of ground points (WGS84 lon/lat, height) in an image (pose_record), NaN if unknown."""
    from pyproj import Transformer
    x, y = Transformer.from_crs(4326, rec["crs"], always_xy=True).transform(np.asarray(lon, float),
                                                                            np.asarray(lat, float))
    z = np.asarray(z, float)
    if rec["model"] == "camera":
        zz = np.where(np.isfinite(z), z, rec.get("ground_h") or 0.0)
        return Pose(rec["R"], rec["C"]).project(_cam_from_dict(rec["calib"]), np.column_stack([x, y, zz]))
    g = rec["gt"]
    M = np.array([[g[1], g[2]], [g[4], g[5]]])
    return np.linalg.solve(M, np.vstack([x - g[0], y - g[3]])).T


def cross_projections(rows, poses):
    """Rows for the GCPs of each image projected into the other matched images that see them (unpinned
    projections in Metashape: one marker is then seen on several images, and can be triangulated).
    Images with a serious flag are neither projected from nor into."""
    ok = {c: p for c, p in poses.items() if p.get("size") and not (SERIOUS_FLAGS & set(p.get("flags", [])))}
    src = [r for r in rows if r.get("camera") in ok and r.get("lon") and r.get("lat")]
    out = []
    if not src:
        return out
    lon = np.array([float(r["lon"]) for r in src])
    lat = np.array([float(r["lat"]) for r in src])
    z = np.array([float(r["z"]) if r.get("z") not in (None, "") else np.nan for r in src])
    for cam_label, rec in ok.items():
        try:
            uv = project_lonlat(rec, lon, lat, z)
        except Exception as e:  # noqa
            print(f"[warn] projection into {cam_label} failed: {e}")
            continue
        W, H = rec["size"]
        inside = (np.isfinite(uv).all(axis=1) & (uv[:, 0] > PROJ_MARGIN * W) & (uv[:, 0] < (1 - PROJ_MARGIN) * W)
                  & (uv[:, 1] > PROJ_MARGIN * H) & (uv[:, 1] < (1 - PROJ_MARGIN) * H))
        for r, (u, v), keep in zip(src, uv, inside):
            if not keep or r["camera"] == cam_label:
                continue
            q = {k: r.get(k, "") for k in ("label", "lon", "lat", "z", "feature", "crs")}
            q.update(camera=cam_label, px_col=f"{u:.2f}", px_row=f"{v:.2f}", residual_m="", bend_deg="",
                     acc_xy_m=f"{max(float(r.get('acc_xy_m') or 0), rec['acc_m']):.1f}",
                     flags=";".join(rec.get("flags", [])), source="projected", run_time=r.get("run_time", ""))
            out.append(q)
    return out


def camera_reference_rows(poses):
    """Camera positions (WGS84 lon/lat, height) of the images with a camera model, for the Metashape
    camera references: alignment then comes out georeferenced, and pairs can be preselected."""
    from pyproj import Transformer
    out = []
    for cam_label, rec in sorted(poses.items()):
        if rec.get("model") != "camera" or SERIOUS_FLAGS & set(rec.get("flags", [])):
            continue
        C = rec["C"]
        lon, lat = Transformer.from_crs(rec["crs"], 4326, always_xy=True).transform(C[0], C[1])
        acc = max(50.0, 5 * rec.get("acc_m", 20.0))
        out.append(dict(camera=cam_label, lon=f"{lon:.8f}", lat=f"{lat:.8f}", alt=f"{C[2]:.1f}",
                        acc_xy_m=f"{acc:.0f}", acc_z_m=f"{2 * acc:.0f}", crs=WGS84_AUTH))
    return out


def master_side_files(master):
    master = Path(master)
    return master.with_name(master.stem + "_poses.json"), master.with_name(master.stem + "_cameras.csv")


def update_master_csv(master, csv_path, camera, flags):
    """Replace the rows of `camera` in the combined table by the new ones (csv_path=None just removes that
    camera's rows), then recompute the projections of all the GCPs into the other images (rows with
    source = projected) and the camera reference table (<master>_cameras.csv)."""
    import csv
    import os
    master = Path(master)
    poses_json, cams_csv = master_side_files(master)
    new_rows = []
    if csv_path is not None:
        with open(csv_path, newline="") as f:
            new_rows = list(csv.DictReader(f))
    for r in new_rows:
        r["flags"] = ";".join(flags)
        r["run_time"] = time.strftime("%Y-%m-%d %H:%M")
        r["source"] = "matched"
        for k in ("x_utm", "y_utm", "utm_crs"):
            r.pop(k, None)
        r["crs"] = WGS84_AUTH
    old_rows = []
    if master.exists():
        with open(master, newline="") as f:
            old_rows = [r for r in csv.DictReader(f)
                        if r.get("camera") != camera and r.get("source", "matched") != "projected"]
        for r in old_rows:   # rows written before Nov. 2026: lon/lat kept, UTM columns dropped
            for k in ("x_utm", "y_utm", "utm_crs"):
                r.pop(k, None)
            r["crs"] = WGS84_AUTH
            r["source"] = r.get("source") or "matched"
    poses = {}
    if poses_json.exists():
        try:
            poses = json.loads(poses_json.read_text())
        except Exception:  # noqa
            poses = {}
    poses.pop(camera, None)
    if csv_path is not None:
        tj = Path(csv_path).with_name(Path(csv_path).name.replace("_gcps.csv", "_transform.json"))
        if tj.exists():
            try:
                poses[camera] = pose_record(tj, flags, new_rows)
            except Exception as e:  # noqa
                print(f"[warn] pose of {camera} not stored ({e}): no projections into this image")
    # images matched before the poses were stored: pose read from their <camera>_transform.json
    for c in sorted({r.get("camera") for r in old_rows} - set(poses) - {camera}):
        found = [p for p in master.parent.rglob(f"{c}_transform.json") if "dem_fallback" not in p.parts]
        if found:
            rows_c = [r for r in old_rows if r.get("camera") == c]
            fl = [f_ for f_ in (rows_c[0].get("flags") or "").split(";") if f_]
            try:
                poses[c] = pose_record(found[0], fl, rows_c)
            except Exception as e:  # noqa
                print(f"[warn] pose of {c} not read from {found[0].name}: {e}")
    poses = {c: p for c, p in poses.items() if c == camera or any(r.get("camera") == c for r in old_rows)}
    tmp = poses_json.with_suffix(".tmp")
    tmp.write_text(json.dumps(poses, indent=1, default=float))
    os.replace(tmp, poses_json)
    proj = cross_projections(old_rows + new_rows, poses)
    if proj:
        n_img = len({r["camera"] for r in proj})
        n_mk = len({r["label"] for r in proj})
        print(f"[out] {n_mk} GCPs also projected into the overlapping images ({len(proj)} projections "
              f"on {n_img} images)")
    cams = camera_reference_rows(poses)
    tmp = cams_csv.with_suffix(".tmp")
    with open(tmp, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["camera", "lon", "lat", "alt", "acc_xy_m", "acc_z_m", "crs"])
        wr.writeheader()
        wr.writerows(cams)
    os.replace(tmp, cams_csv)
    rows = old_rows + new_rows + proj
    fields = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    tmp = master.with_suffix(".tmp")
    with open(tmp, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=fields, restval="")
        wr.writeheader()
        wr.writerows(sorted(rows, key=lambda r: (r.get("camera", ""), r.get("label", ""))))
    os.replace(tmp, master)
    return len(old_rows), len(new_rows)


def qa_plot(path, osm_lines, reg_poly, road_w, gcps, refined, centroid, best,
            image, gt, img_size, pixel_scale, aux_ref=(), aux_w=()):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    fig, axs = plt.subplots(1, 3 if image else 2, figsize=(20 if image else 14, 7))
    for ax, zoom in zip(axs[:2], (False, True)):
        ax.add_collection(LineCollection(osm_lines, colors="0.55", linewidths=0.5))
        if aux_ref:
            ax.add_collection(LineCollection(aux_ref, colors="tab:blue", linewidths=0.8))
        for l in aux_w:
            ax.plot(*l.xy, color="magenta", lw=2 if zoom else 1.2)
        rp = [reg_poly] if reg_poly.geom_type == "Polygon" else list(reg_poly.geoms)
        for p in rp:
            ax.plot(*p.exterior.xy, color="k", lw=0.8, ls="--")
        for k, r in enumerate(refined[1:], start=2):
            c = apply(r["A"], centroid[None])[0]
            ax.plot(*c, "x", color="orange", ms=8)
            if not zoom:
                ax.annotate(f"#{k} ({r['contrast']:.2f})", c, fontsize=7, color="darkorange",
                            xytext=(3, 3), textcoords="offset points")
        for l in road_w:
            ax.plot(*l.xy, color="red", lw=2 if zoom else 1.5)
        for g in gcps:
            ax.plot(g["x"], g["y"], "o", mfc="yellow", mec="k", ms=6)
            if zoom:
                ax.annotate(g["label"].split("_")[-1], (g["x"], g["y"]), fontsize=8,
                            xytext=(4, 4), textcoords="offset points")
        if zoom:
            xs = np.concatenate([np.asarray(l.xy[0]) for l in list(road_w) + list(aux_w)])
            ys = np.concatenate([np.asarray(l.xy[1]) for l in list(road_w) + list(aux_w)])
            m = 0.15 * max(np.ptp(xs), np.ptp(ys)) + 200
            ax.set_xlim(xs.min() - m, xs.max() + m)
            ax.set_ylim(ys.min() - m, ys.max() + m)
            ax.set_title(f"zoom: contrast {best['contrast']:.2f}, inliers {best['inlier_frac']*100:.0f}%, "
                         f"RMSE {best['rmse_inliers_m']:.1f} m, GSD {best['gsd_mean']:.2f} m/px")
        else:
            ax.autoscale()
            ax.set_title("overview (red = road, magenta = aux, blue = water ref, x = other candidates)")
        ax.set_aspect("equal")
        ax.tick_params(labelsize=7)
    if image:
        ax = axs[2]
        try:
            import rasterio
            from rasterio.enums import Resampling
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                with rasterio.open(image) as ds:
                    f = max(1, int(max(ds.width, ds.height) / 1500))
                    arr = ds.read(1, out_shape=(ds.height // f, ds.width // f),
                                  resampling=Resampling.average)
            W_, H_ = img_size[0] * pixel_scale, img_size[1] * pixel_scale
            sx, sy = W_ / arr.shape[1], H_ / arr.shape[0]
            # display image in world space via inverse mapping of grid
            rr, cc = np.mgrid[0:arr.shape[0], 0:arr.shape[1]]
            X = gt[0] + (cc + 0.5) * sx * gt[1] + (rr + 0.5) * sy * gt[2]
            Y = gt[3] + (cc + 0.5) * sx * gt[4] + (rr + 0.5) * sy * gt[5]
            ax.pcolormesh(X, Y, arr, cmap="gray", shading="auto", rasterized=True)
            ax.add_collection(LineCollection(osm_lines, colors="cyan", linewidths=0.7))
            if aux_ref:
                ax.add_collection(LineCollection(aux_ref, colors="deepskyblue", linewidths=1.0))
            for l in road_w:
                ax.plot(*l.xy, color="red", lw=1)
            for l in aux_w:
                ax.plot(*l.xy, color="magenta", lw=1)
            ax.set_xlim(X.min(), X.max())
            ax.set_ylim(Y.min(), Y.max())
            ax.set_aspect("equal")
            ax.set_title("image warped with estimated transform + OSM (cyan)")
            ax.tick_params(labelsize=7)
        except Exception as e:  # noqa
            ax.set_title(f"image overlay unavailable: {e}")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    print(f"[out] {path}")


if __name__ == "__main__":
    main()
