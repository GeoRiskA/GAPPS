#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
========================================================================================
                     GAPPS – GeoRiskA Airphoto Pre-Processing Suite
========================================================================================
                          = SHAPE2GCPs – OSM MATCHING MENU =

Description: Draw roads, lake shores and rivers on historical aerial photographs, match
them against OpenStreetMap to locate each photo, and export approximate GCPs for
Agisoft Metashape (combined table osm_gcps_all.csv, imported in Metashape with
GAPPS_tools/GAPPS_Tool_06c_Metashape_ImportGCPs.py).

With a DEM and the Metashape camera calibration (optional project settings), the
flat fit is refined into a full camera model (position, height, tilt) with terrain
heights, which removes the relief displacement (typically tens of metres at the
edges of the photos in hilly areas).

Each matched image teaches the next ones: the GSD, the rotation (same, -90, -180,
+90 degrees) and the location of the nearest already-matched image are used as priors,
which makes the search a few seconds instead of minutes. If a prior-based match looks
doubtful, the search is automatically widened.

Usage:
    python GAPPS_interface_Shape2GCPs.py [image_folder] [output_results_folder]
    (or from the GAPPS main menu, Tool 6)

Mouse:  left click = add point | double-click / Enter = finish line
        wheel = zoom | right or middle drag = pan
Keys:   1 road  2 lake shore  3 river | D draw  X delete | Backspace undo point
        Esc cancel line | M match | A accept & next | S skip & next
        PageDown / PageUp next / previous | O OSM overlay | F fit image

Outputs (in <output_results_folder>/F_Shape2GCPs):
    shape2gcps_project.json   settings + status of every image
    features/<image>.geojson  drawn lines (pixel coords, QGIS convention x=col, y=-row)
    match/<image>/            matching outputs (GCP csv, transform, QA png, gpkg)
    osm_gcps_all.csv          combined GCP table for Metashape

Copyright:
    RMCA — Royal Museum for Central Africa (Tervuren, BELGIUM)
        Natural Hazards and Cartography (GeoRiskA), Dpt. of Earth Sciences
    © 2026

Software authorship:
    - Antoine DILLE (RMCA), developed with Anthropic's Claude

Last update: 2026-11-06
========================================================================================
"""

import io
import json
import math
import os
import queue
import re
import shutil
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

import numpy as np
from PIL import Image, ImageTk

# GAPPS paths
absolute_file_path = os.path.abspath(__file__)
gui_folder = os.path.dirname(absolute_file_path)
gapps_main_folder = os.path.dirname(gui_folder)
if gapps_main_folder not in sys.path:
    sys.path.insert(0, gapps_main_folder)

# heavy geo imports are done lazily (in the worker thread) to keep start-up fast
s2g = None


def _core():
    global s2g
    if s2g is None:
        from GAPPS_tools import GAPPS_Tool_06_Shape2GCPs as mod
        s2g = mod
    return s2g


# 1. CONSTANTS
##############

OUT_SUBFOLDER = "F_Shape2GCPs"
IMG_EXT = (".tif", ".tiff", ".jpg", ".jpeg", ".png")

FEATURES = {  # kind: label, key, colour, OSM reference layers (for aux features)
    "road": dict(label="Road", key="1", color="#ff3b30", ref=None),
    "lake": dict(label="Lake shore", key="2", color="#2f7cff", ref="water"),
    "river": dict(label="River", key="3", color="#00c8d7", ref="waterways,water"),
}
STATUS_STYLE = {  # status: (text, tree tag colour)
    "todo": ("to draw", "#000000"),
    "drawn": ("drawn", "#7a5a00"),
    "matched": ("matched", "#1b6e1b"),
    "flagged": ("CHECK", "#c0392b"),
    "checked": ("accepted", "#0a5fb4"),
    "skipped": ("skipped", "#9a9a9a"),
}
SERIOUS_FLAGS = {"AMBIGUOUS", "LOW_CONTRAST", "GSD_AT_SEARCH_BOUND", "ANCHOR_MISMATCH"}
MAX_ZOOM = 8.0


# 2. HELPERS
############

def read_image_8bit(path):
    """Grayscale image stretched to 8 bits (1-99 percentiles); unicode-safe."""
    arr = None
    try:
        import cv2
        arr = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        if arr is not None and arr.ndim == 3:
            arr = cv2.cvtColor(arr[..., :3], cv2.COLOR_BGR2GRAY)
    except Exception:  # noqa
        arr = None
    if arr is None:
        Image.MAX_IMAGE_PIXELS = None
        im = Image.open(path)
        arr = np.asarray(im.convert("I") if im.mode not in ("L", "I;16", "I") else im)
        if arr.ndim == 3:
            arr = arr.mean(2)
    if arr.dtype != np.uint8:
        sub = arr[::max(1, arr.shape[0] // 500), ::max(1, arr.shape[1] // 500)]
        valid = sub[sub > 0] if (sub > 0).any() else sub
        lo, hi = np.percentile(valid, (1, 99))
        hi = hi if hi > lo else lo + 1
        arr = np.clip((arr.astype(np.float32) - lo) * (255.0 / (hi - lo)), 0, 255).astype(np.uint8)
    return arr


def build_pyramid(arr, min_size=768):
    levels = [arr]
    while max(levels[-1].shape) > min_size:
        a = levels[-1]
        h, w = a.shape[0] // 2 * 2, a.shape[1] // 2 * 2
        a = a[:h, :w].reshape(h // 2, 2, w // 2, 2).mean((1, 3)).astype(np.uint8)
        levels.append(a)
    return levels


def short_id(stem):
    """'5828_170_Cropped_standardized_DownSharp' -> '5828_170'."""
    m = re.match(r"^\D*(\d+)[_\-](\d+)", stem)
    return f"{m.group(1)}_{m.group(2)}" if m else stem


def strip_frame(stem):
    m = re.match(r"^\D*(\d+)[_\-](\d+)", stem)
    return (m.group(1), int(m.group(2))) if m else (None, None)


def seg_dist(p, a, b):
    ab = b - a
    t = np.clip(((p - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
    return float(np.hypot(*(a + t * ab - p)))


def clip_polyline(xy, rect):
    """Clip a polyline to a rectangle (Liang-Barsky per segment); returns parts."""
    x0, y0, x1, y1 = rect
    parts, cur = [], []
    for a, b in zip(xy[:-1], xy[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        t0, t1, ok = 0.0, 1.0, True
        for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
            if p == 0:
                if q < 0:
                    ok = False
                    break
            else:
                t = q / p
                if p < 0:
                    t0 = max(t0, t)
                else:
                    t1 = min(t1, t)
                if t0 > t1:
                    ok = False
                    break
        if not ok:
            if len(cur) >= 2:
                parts.append(np.array(cur))
            cur = []
            continue
        pa = (a[0] + t0 * dx, a[1] + t0 * dy)
        pb = (a[0] + t1 * dx, a[1] + t1 * dy)
        if not cur:
            cur = [pa, pb]
        else:
            if t0 > 0:                       # re-entered: new part
                if len(cur) >= 2:
                    parts.append(np.array(cur))
                cur = [pa, pb]
            else:
                cur.append(pb)
        if t1 < 1:
            parts.append(np.array(cur))
            cur = []
    if len(cur) >= 2:
        parts.append(np.array(cur))
    return parts


def read_metashape_markers(path):
    """Markers of a Metashape XML export (File > Export > Markers, or a .xml project
    document): {camera label: [dict(label, col, row, lon, lat, z, pinned)]}, plus the
    number of markers without reference coordinates."""
    import xml.etree.ElementTree as ET
    root = ET.parse(path).getroot()
    chunk = root.find("chunk") if root.tag == "document" else root
    if chunk is None:
        chunk = root
    cams = {c.get("id"): c.get("label") for c in chunk.iter("camera")}
    refs, no_ref = {}, 0
    mk = chunk.find("markers")
    for m in (mk.findall("marker") if mk is not None else []):
        rf = m.find("reference")
        if rf is None or rf.get("x") is None or rf.get("y") is None:
            no_ref += 1
            continue
        refs[m.get("id")] = dict(label=m.get("label") or f"marker {m.get('id')}",
                                 x=float(rf.get("x")), y=float(rf.get("y")),
                                 z=float(rf.get("z")) if rf.get("z") not in (None, "") else float("nan"))
    if not refs:
        raise ValueError("no marker with reference coordinates in this file")
    xs = np.array([v["x"] for v in refs.values()])
    ys = np.array([v["y"] for v in refs.values()])
    if not (np.abs(xs).max() <= 180 and np.abs(ys).max() <= 90):
        # projected coordinates: use the chunk CRS
        wkt = (chunk.findtext("reference") or "").strip()
        if not wkt or wkt.startswith("LOCAL_CS"):
            raise ValueError("marker coordinates are not lon/lat and the chunk CRS is local: "
                             "export the markers with a geographic or projected CRS")
        from pyproj import CRS, Transformer
        tr = Transformer.from_crs(CRS.from_wkt(wkt), 4326, always_xy=True)
        for v in refs.values():
            v["x"], v["y"] = tr.transform(v["x"], v["y"])
    out = {}
    fr = chunk.find("frames")
    for frame in (fr.findall("frame") if fr is not None else []):
        fm = frame.find("markers")
        for m in (fm.findall("marker") if fm is not None else []):
            ref = refs.get(m.get("marker_id"))
            if ref is None:
                continue
            for loc in m.findall("location"):
                lab = cams.get(loc.get("camera_id"))
                if lab is None or loc.get("x") is None:
                    continue
                out.setdefault(lab, []).append(dict(label=ref["label"], col=float(loc.get("x")),
                                                    row=float(loc.get("y")), lon=ref["x"], lat=ref["y"],
                                                    z=ref["z"], pinned=loc.get("pinned") == "true"))
    return out, no_ref


class QueueWriter(io.TextIOBase):
    """stdout replacement used while the worker runs (lines -> GUI log)."""

    def __init__(self, q):
        self.q = q

    def write(self, s):
        if s:
            self.q.put(("log", s))
        return len(s)

    def flush(self):
        pass


# 3. PROJECT (settings + per-image status, saved as JSON)
#########################################################

class Project:
    DEFAULTS = dict(image_folder="", aoi="", osm="", dem="", camera_xml="", gsd_min=0.5, gsd_max=2.0,
                    rot_halfwidth=15.0, prior_radius_km=15.0, n_gcps=12, aux_gcps=4)

    def __init__(self, root_dir):
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "features").mkdir(exist_ok=True)
        (self.root / "match").mkdir(exist_ok=True)
        self.path = self.root / "shape2gcps_project.json"
        self.settings = dict(self.DEFAULTS)
        self.images = {}
        if self.path.exists():
            try:
                d = json.loads(self.path.read_text())
                self.settings.update(d.get("settings", {}))
                for k, v in self.settings.items():
                    if isinstance(v, str):
                        self.settings[k] = v.strip().strip('"').strip("'").strip()
                self.images = d.get("images", {})
            except Exception as e:  # noqa
                print("could not read project file:", e)

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(dict(settings=self.settings, images=self.images), indent=1))
        os.replace(tmp, self.path)

    def info(self, stem):
        return self.images.setdefault(stem, dict(status="todo"))

    @property
    def master_csv(self):
        return self.root / "osm_gcps_all.csv"

    def features_path(self, stem):
        return self.root / "features" / f"{stem}.geojson"

    def match_dir(self, stem):
        return self.root / "match" / stem

    def matched(self):
        return {k: v for k, v in self.images.items()
                if v.get("status") in ("matched", "checked", "flagged") and v.get("gsd")}


# 4. IMAGE VIEW (zoom / pan / draw)
###################################

class ImageView:
    def __init__(self, app, parent):
        self.app = app
        self.c = tk.Canvas(parent, bg="#262626", highlightthickness=0, cursor="crosshair")
        self.c.pack(fill="both", expand=True)
        self.levels = None
        self.iw = self.ih = 1
        self.scale, self.ox, self.oy = 1.0, 0.0, 0.0
        self._photo = None
        self._pan = None
        self._render_pending = False
        self.c.bind("<Configure>", lambda e: self.request_render())
        self.c.bind("<Button-1>", self.on_click)
        self.c.bind("<Double-Button-1>", self.on_double)
        for b in (2, 3):
            self.c.bind(f"<ButtonPress-{b}>", self.pan_start)
            self.c.bind(f"<B{b}-Motion>", self.pan_move)
        self.c.bind("<MouseWheel>", lambda e: self.zoom_at(e.x, e.y, 1.25 if e.delta > 0 else 0.8))
        self.c.bind("<Button-4>", lambda e: self.zoom_at(e.x, e.y, 1.25))
        self.c.bind("<Button-5>", lambda e: self.zoom_at(e.x, e.y, 0.8))
        self.c.bind("<Motion>", self.on_motion)

    # --- image & view
    def set_image(self, levels):
        self.levels = levels
        self.ih, self.iw = levels[0].shape[:2]
        self.fit()

    def clear(self):
        self.levels = None
        self.c.delete("all")

    def fit(self):
        W, H = max(self.c.winfo_width(), 100), max(self.c.winfo_height(), 100)
        self.scale = min(W / self.iw, H / self.ih)
        self.ox = (self.iw - W / self.scale) / 2
        self.oy = (self.ih - H / self.scale) / 2
        self.request_render()

    def img2scr(self, pts):
        return (np.asarray(pts, float) - [self.ox, self.oy]) * self.scale

    def scr2img(self, x, y):
        return np.array([self.ox + x / self.scale, self.oy + y / self.scale])

    def zoom_at(self, x, y, f):
        if self.levels is None:
            return
        fit = min(max(self.c.winfo_width(), 100) / self.iw, max(self.c.winfo_height(), 100) / self.ih)
        new = float(np.clip(self.scale * f, fit * 0.5, MAX_ZOOM))
        p = self.scr2img(x, y)
        self.scale = new
        self.ox, self.oy = p[0] - x / new, p[1] - y / new
        self.request_render()

    def pan_start(self, e):
        self._pan = (e.x, e.y, self.ox, self.oy)

    def pan_move(self, e):
        if self._pan:
            x0, y0, ox, oy = self._pan
            self.ox = ox - (e.x - x0) / self.scale
            self.oy = oy - (e.y - y0) / self.scale
            self.request_render()

    def request_render(self):
        if not self._render_pending:
            self._render_pending = True
            self.c.after_idle(self.render)

    def render(self):
        self._render_pending = False
        self.c.delete("all")
        if self.levels is None:
            return
        W, H = self.c.winfo_width(), self.c.winfo_height()
        s = self.scale
        f = 1.0 / s
        L = 0
        while L + 1 < len(self.levels) and 2 ** (L + 1) <= f:
            L += 1
        lev, d = self.levels[L], 2 ** L
        x0, y0 = max(0.0, self.ox), max(0.0, self.oy)
        x1, y1 = min(self.iw, self.ox + W * f), min(self.ih, self.oy + H * f)
        if x1 > x0 and y1 > y0:
            lx0, ly0 = int(x0 // d), int(y0 // d)
            lx1 = min(lev.shape[1], int(math.ceil(x1 / d)))
            ly1 = min(lev.shape[0], int(math.ceil(y1 / d)))
            crop = lev[ly0:ly1, lx0:lx1]
            if crop.size:
                tw = max(1, int(round((lx1 - lx0) * d * s)))
                th = max(1, int(round((ly1 - ly0) * d * s)))
                im = Image.fromarray(crop).resize((tw, th), Image.NEAREST if s * d >= 1 else Image.BILINEAR)
                self._photo = ImageTk.PhotoImage(im)
                sx, sy = (lx0 * d - self.ox) * s, (ly0 * d - self.oy) * s
                self.c.create_image(sx, sy, image=self._photo, anchor="nw")
        self.draw_overlays()

    # --- overlays
    def _line(self, pts, **kw):
        """Draw a polyline clipped to the visible window: Tk canvases use 16-bit
        coordinates, lines reaching far outside (e.g. the whole Lake Kivu shore)
        are otherwise silently not drawn."""
        if len(pts) < 2:
            return
        scr = self.img2scr(pts)
        W, H = self.c.winfo_width(), self.c.winfo_height()
        m = 50.0
        inside = (scr[:, 0] > -m) & (scr[:, 0] < W + m) & (scr[:, 1] > -m) & (scr[:, 1] < H + m)
        if inside.all():
            self.c.create_line(*scr.ravel().tolist(), **kw)
            return
        for part in clip_polyline(scr, (-m, -m, W + m, H + m)):
            if len(part) >= 2:
                self.c.create_line(*part.ravel().tolist(), **kw)

    def draw_overlays(self):
        app = self.app
        W, H = self.c.winfo_width(), self.c.winfo_height()
        vb = (self.ox, self.oy, self.ox + W / self.scale, self.oy + H / self.scale)
        if app.show_osm.get() and app.osm_overlay:
            for kind, pts in app.osm_overlay:
                if pts[:, 0].max() < vb[0] or pts[:, 0].min() > vb[2] or \
                        pts[:, 1].max() < vb[1] or pts[:, 1].min() > vb[3]:
                    continue
                if kind == "road":
                    self._line(pts, fill="#ffd400", width=1)
                else:
                    self._line(pts, fill="#00e5ff", width=2, dash=(6, 3))
        for ln in app.lines:
            col = FEATURES[ln["kind"]]["color"]
            self._line(ln["pts"], fill=col, width=3 if ln is not app.hover_line else 6,
                       capstyle="round", joinstyle="round")
        if app.current and len(app.current["pts"]):
            col = FEATURES[app.current["kind"]]["color"]
            pts = np.asarray(app.current["pts"])
            self._line(pts, fill=col, width=2, dash=(6, 3))
            for x, y in self.img2scr(pts):
                self.c.create_rectangle(x - 3, y - 3, x + 3, y + 3, outline=col)
        if app.show_osm.get():
            for g in app.gcps_overlay:
                x, y = self.img2scr([[g["col"], g["row"]]])[0]
                self.c.create_oval(x - 5, y - 5, x + 5, y + 5, outline="black", fill="#ffef3a")
                parts = g["label"].split("_")
                tag = {"road": "R", "lake": "L", "river": "Ri"}.get(parts[-2] if len(parts) > 1 else "", "")
                short = tag + parts[-1]                                                   # e.g. R03, L01, Ri02
                self.c.create_text(x + 8, y - 8, text=short, fill="#ffef3a",
                                   anchor="w", font=("Arial", 9, "bold"))
        for a in app.anchors_overlay:
            x, y = self.img2scr([[a["col"], a["row"]]])[0]
            self.c.create_polygon(x, y - 9, x + 9, y, x, y + 9, x - 9, y, outline="black", fill="#ff3df2", width=1)
            self.c.create_text(x + 11, y + 9, text=a["label"], fill="#ff3df2", anchor="w", font=("Arial", 9, "bold"))
        mode = "DELETE (click a line)" if app.mode.get() == "delete" else \
            f"DRAW {FEATURES[app.kind.get()]['label'].upper()}"
        self.c.create_text(10, 10, anchor="nw", text=mode, font=("Arial", 11, "bold"),
                           fill="#ff8080" if app.mode.get() == "delete" else FEATURES[app.kind.get()]["color"])

    # --- mouse actions
    def on_motion(self, e):
        if self.levels is None:
            return
        p = self.scr2img(e.x, e.y)
        self.app.coord_var.set(f"col {p[0]:.0f}  row {p[1]:.0f}   zoom {self.scale:.2f}")
        if self.app.mode.get() == "delete":
            hit = self.hit_line(p)
            if hit is not self.app.hover_line:
                self.app.hover_line = hit
                self.request_render()

    def hit_line(self, p):
        tol = 8.0 / self.scale
        best, bd = None, tol
        for ln in self.app.lines:
            pts = ln["pts"]
            for a, b in zip(pts[:-1], pts[1:]):
                d = seg_dist(p, a, b)
                if d < bd:
                    best, bd = ln, d
        return best

    def on_click(self, e):
        if self.levels is None:
            return
        self.c.focus_set()
        p = self.scr2img(e.x, e.y)
        if self.app.mode.get() == "delete":
            hit = self.hit_line(p)
            if hit is not None:
                self.app.delete_line(hit)
            return
        self.app.add_point(p)

    def on_double(self, e):
        if self.app.mode.get() == "draw":
            cur = self.app.current
            if cur and len(cur["pts"]) >= 2:
                a, b = np.asarray(cur["pts"][-2]), np.asarray(cur["pts"][-1])
                if np.hypot(*(a - b)) * self.scale < 4:
                    cur["pts"].pop()        # the 2nd click of the double-click
            self.app.finish_line()


# 5. MAIN APPLICATION
#####################

class Shape2GCPsApp:
    def __init__(self, root, image_folder="", output_folder=""):
        self.root = root
        root.title("GAPPS – Shape2GCPs: match roads / lakes / rivers to OpenStreetMap")
        root.geometry("1500x930")
        out = Path(output_folder) if output_folder else Path(image_folder or ".").resolve().parent
        self.project = Project(out / OUT_SUBFOLDER)
        if image_folder:
            self.project.settings["image_folder"] = str(image_folder)

        self.q = queue.Queue()
        self.busy = False
        self.images = []
        self.stem = None
        self.lines, self.current, self.hover_line = [], None, None
        self.osm_overlay, self.gcps_overlay = [], []
        self.anchors_overlay = []
        self._osm_cache = None
        self._levels_cache = {}

        self.kind = tk.StringVar(value="road")
        self.mode = tk.StringVar(value="draw")
        self.show_osm = tk.BooleanVar(value=True)
        self.coord_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Set the project paths, then pick an image.")
        self.cand_var = tk.StringVar()
        self.svars = {}

        self._build()
        self._bind_keys()
        self.refresh_images()
        self.root.after(100, self._poll)

    # ---------------- layout
    def _build(self):
        st = self.project.settings
        top = ttk.LabelFrame(self.root, text=" Project ")
        top.pack(fill="x", padx=6, pady=4)
        rows = [("image_folder", "Image folder", "dir"), ("aoi", "AOI polygon", "file"),
                ("osm", "OSM extract (gpkg)", "file"), ("dem", "DEM (optional)", "file"),
                ("camera_xml", "Camera calib. (Metashape XML, optional)", "file")]
        for i, (key, lab, kind) in enumerate(rows):
            r, c = divmod(i, 2)
            ttk.Label(top, text=lab).grid(row=r, column=c * 3, sticky="e", padx=3)
            v = tk.StringVar(value=st.get(key, ""))
            self.svars[key] = v
            ttk.Entry(top, textvariable=v, width=55).grid(row=r, column=c * 3 + 1, sticky="we", pady=2)
            ttk.Button(top, text="…", width=3,
                       command=lambda k=key, t=kind: self.browse(k, t)).grid(row=r, column=c * 3 + 2)
        ttk.Button(top, text="Clip country OSM to AOI…", command=self.clip_osm).grid(row=0, column=6, padx=8)
        ttk.Button(top, text="Import Metashape markers…", command=self.import_markers).grid(row=1, column=6, padx=8)
        num = ttk.Frame(top)
        num.grid(row=3, column=0, columnspan=7, sticky="w", pady=2)
        ttk.Label(top, text="DEM + camera calibration: relief/tilt corrected (camera model) instead of a flat fit",
                  foreground="#555").grid(row=2, column=3, columnspan=4, sticky="w", padx=6)
        for key, lab, w in [("gsd_min", "GSD start range (m/px)  min", 6), ("gsd_max", "max", 6),
                            ("rot_halfwidth", "   rotation window ±°", 5),
                            ("prior_radius_km", "   search radius around neighbour (km)", 5),
                            ("n_gcps", "   GCPs / image", 4), ("aux_gcps", "+ along lake/river", 4)]:
            ttk.Label(num, text=lab).pack(side="left", padx=(4, 2))
            v = tk.StringVar(value=str(st.get(key)))
            self.svars[key] = v
            ttk.Entry(num, textvariable=v, width=w).pack(side="left")
        ttk.Button(num, text="Save settings / reload images", command=self.apply_settings).pack(side="left", padx=12)
        ttk.Label(num, text=f"Output: {self.project.root}", foreground="#555").pack(side="left", padx=8)

        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=6)

        # left: image list
        left = ttk.Frame(body, width=300)
        left.pack(side="left", fill="y")
        tree_box = ttk.Frame(left)
        tree_box.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tree_box, columns=("mk", "status", "gsd", "rot", "fit"), show="tree headings",
                                 height=28, selectmode="browse")
        tree_sb = ttk.Scrollbar(tree_box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_sb.set)
        tree_sb.pack(side="right", fill="y")
        self.tree.heading("#0", text="image")
        self.tree.heading("mk", text="mk")
        self.tree.column("mk", width=30, anchor="center")
        for c, t, w in (("status", "status", 64), ("gsd", "GSD", 44), ("rot", "rot°", 40), ("fit", "fit %", 40)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="center")
        self.tree.column("#0", width=110)
        for stt, (_, col) in STATUS_STYLE.items():
            self.tree.tag_configure(stt, foreground=col)
        self.tree.tag_configure("markers", background="#fff1b8")      # images with known GCPs
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        def _tree_wheel(e):
            step = -1 if (getattr(e, "num", None) == 4 or getattr(e, "delta", 0) > 0) else 1
            self.tree.yview_scroll(3 * step, "units")
            return "break"
        for w_ in (self.tree, tree_sb):
            w_.bind("<MouseWheel>", _tree_wheel)
            w_.bind("<Button-4>", _tree_wheel)
            w_.bind("<Button-5>", _tree_wheel)
        nav = ttk.Frame(left)
        nav.pack(fill="x", pady=3)
        ttk.Button(nav, text="◀ Prev (PgUp)", command=lambda: self.goto(-1)).pack(side="left", expand=True, fill="x")
        ttk.Button(nav, text="Next (PgDn) ▶", command=lambda: self.goto(+1)).pack(side="left", expand=True, fill="x")
        self.count_var = tk.StringVar()
        ttk.Label(left, textvariable=self.count_var, foreground="#555").pack(anchor="w")

        # right: tools
        right = ttk.Frame(body, width=290)
        right.pack(side="right", fill="y", padx=(6, 0))
        fk = ttk.LabelFrame(right, text=" 1. Draw ")
        fk.pack(fill="x", pady=3)
        for kind, f in FEATURES.items():
            tk.Radiobutton(fk, text=f"  {f['label']}   [{f['key']}]", variable=self.kind, value=kind,
                           indicatoron=False, selectcolor=f["color"], fg="black", font=("Arial", 11, "bold"),
                           width=20, pady=4, command=self.on_kind).pack(fill="x", padx=4, pady=2)
        mf = ttk.Frame(fk)
        mf.pack(fill="x", pady=3)
        ttk.Radiobutton(mf, text="Draw [D]", variable=self.mode, value="draw",
                        command=self.view_refresh).pack(side="left", padx=4)
        ttk.Radiobutton(mf, text="Delete line [X]", variable=self.mode, value="delete",
                        command=self.view_refresh).pack(side="left", padx=4)
        bf = ttk.Frame(fk)
        bf.pack(fill="x")
        ttk.Button(bf, text="Undo point ⌫", command=self.undo_point).pack(side="left", expand=True, fill="x")
        ttk.Button(bf, text="Finish line ⏎", command=self.finish_line).pack(side="left", expand=True, fill="x")
        bf2 = ttk.Frame(fk)
        bf2.pack(fill="x", pady=(2, 4))
        ttk.Button(bf2, text="Import lines…", command=self.import_lines).pack(side="left", expand=True, fill="x")
        ttk.Button(bf2, text="Clear all", command=self.clear_lines).pack(side="left", expand=True, fill="x")
        self.lines_var = tk.StringVar()
        ttk.Label(fk, textvariable=self.lines_var, foreground="#555").pack(anchor="w", padx=4)

        mm = ttk.LabelFrame(right, text=" 2. Match ")
        mm.pack(fill="x", pady=3)
        self.match_btn = tk.Button(mm, text="MATCH with OSM  [M]", font=("Arial", 11, "bold"),
                                   bg="#d9ead3", command=self.match)
        self.match_btn.pack(fill="x", padx=4, pady=4)
        self.prior_var = tk.StringVar()
        ttk.Label(mm, textvariable=self.prior_var, foreground="#555", wraplength=270).pack(anchor="w", padx=4)
        self.fit_var = tk.StringVar()
        self.fit_label = tk.Label(mm, textvariable=self.fit_var, font=("Arial", 11, "bold"), justify="left",
                                  wraplength=270)
        self.fit_label.pack(anchor="w", padx=4, pady=(4, 0))
        self.result_var = tk.StringVar()
        tk.Label(mm, textvariable=self.result_var, font=("Arial", 9), justify="left",
                 wraplength=270).pack(anchor="w", padx=4)
        cf = ttk.Frame(mm)
        cf.pack(fill="x", padx=4, pady=2)
        self.cand_box = ttk.Combobox(cf, textvariable=self.cand_var, state="readonly", width=28)
        self.cand_box.pack(side="left", fill="x", expand=True)
        ttk.Button(cf, text="Use", width=5, command=self.use_candidate).pack(side="left")
        ttk.Checkbutton(mm, text="Show OSM + GCPs on image [O]", variable=self.show_osm,
                        command=self.view_refresh).pack(anchor="w", padx=4)
        ttk.Button(mm, text="Open QA figure", command=self.open_qa).pack(fill="x", padx=4, pady=(2, 4))

        dd = ttk.LabelFrame(right, text=" 3. Decide ")
        dd.pack(fill="x", pady=3)
        tk.Button(dd, text="ACCEPT & next  [A]", font=("Arial", 11, "bold"), bg="#cfe2f3",
                  command=self.accept).pack(fill="x", padx=4, pady=3)
        tk.Button(dd, text="SKIP image & next  [S]", font=("Arial", 11, "bold"), bg="#eeeeee",
                  command=self.skip).pack(fill="x", padx=4, pady=(0, 4))

        lg = ttk.LabelFrame(right, text=" Log ")
        lg.pack(fill="both", expand=True, pady=3)
        self.log = tk.Text(lg, width=38, height=12, font=("Consolas", 8), wrap="word")
        self.log.pack(fill="both", expand=True)

        # centre: image
        mid = ttk.Frame(body)
        mid.pack(side="left", fill="both", expand=True, padx=6)
        self.view = ImageView(self, mid)

        sb = ttk.Frame(self.root)
        sb.pack(fill="x", padx=6, pady=2)
        ttk.Label(sb, textvariable=self.status_var).pack(side="left")
        ttk.Label(sb, textvariable=self.coord_var, foreground="#555").pack(side="right")
        ttk.Label(sb, text="wheel zoom · right/middle-drag pan · F fit   ", foreground="#777").pack(side="right")

    def _bind_keys(self):
        def guard(fn):
            def h(e):
                if isinstance(e.widget, (tk.Entry, ttk.Entry, ttk.Combobox, tk.Text)):
                    return
                fn()
            return h
        for kind, f in FEATURES.items():
            self.root.bind(f["key"], guard(lambda k=kind: (self.kind.set(k), self.on_kind())))
        keys = {"d": lambda: (self.mode.set("draw"), self.view_refresh()),
                "x": lambda: (self.mode.set("delete"), self.view_refresh()),
                "m": self.match, "a": self.accept, "s": self.skip, "f": self.view.fit,
                "o": lambda: (self.show_osm.set(not self.show_osm.get()), self.view_refresh())}
        for k, fn in keys.items():
            self.root.bind(k, guard(fn))
            self.root.bind(k.upper(), guard(fn))
        self.root.bind("<Return>", guard(self.finish_line))
        self.root.bind("<KP_Enter>", guard(self.finish_line))
        self.root.bind("<BackSpace>", guard(self.undo_point))
        self.root.bind("<Escape>", guard(self.cancel_line))
        self.root.bind("<Next>", guard(lambda: self.goto(+1)))
        self.root.bind("<Prior>", guard(lambda: self.goto(-1)))

    # ---------------- settings / images
    def browse(self, key, kind):
        if kind == "dir":
            p = filedialog.askdirectory(initialdir=self.svars[key].get() or None)
        else:
            p = filedialog.askopenfilename(initialdir=os.path.dirname(self.svars[key].get()) or None)
        if p:
            self.svars[key].set(p)
            self.apply_settings()

    def apply_settings(self):
        st = self.project.settings
        for k, v in self.svars.items():
            val = v.get().strip().strip('"').strip("'").strip()     # pasted "C:\...\file" paths
            if val != v.get():
                v.set(val)
            if k in Project.DEFAULTS and isinstance(Project.DEFAULTS[k], (int, float)) and \
                    not isinstance(Project.DEFAULTS[k], bool):
                try:
                    val = type(Project.DEFAULTS[k])(float(val))
                except ValueError:
                    val = Project.DEFAULTS[k]
            st[k] = val
        self.project.save()
        self._osm_cache = None
        self.refresh_images()

    def refresh_images(self):
        folder = self.project.settings.get("image_folder", "")
        self.images = sorted(p for p in Path(folder).glob("*") if p.suffix.lower() in IMG_EXT) \
            if folder and Path(folder).is_dir() else []
        ids = [short_id(p.stem) for p in self.images]
        self.labels = {p.stem: (short_id(p.stem) if ids.count(short_id(p.stem)) == 1 else p.stem)
                       for p in self.images}
        self.tree.delete(*self.tree.get_children())
        for p in self.images:
            self.tree.insert("", "end", iid=p.stem, text=self.labels[p.stem])
            self.update_row(p.stem)
        self.update_counts()
        if not self.images:
            self.status_var.set("No images: set the image folder.")

    def update_row(self, stem):
        if not self.tree.exists(stem):
            return
        inf = self.project.info(stem)
        stt = inf.get("status", "todo")
        nmk = len(inf.get("anchors") or [])
        self.tree.item(stem, values=(nmk if nmk else "", STATUS_STYLE[stt][0],
                                     f"{inf['gsd']:.2f}" if inf.get("gsd") else "",
                                     f"{inf['rot']:.0f}" if inf.get("rot") is not None and inf.get("gsd") else "",
                                     f"{inf['fit']['pct']:.0f}" if inf.get("fit") else ""),
                       tags=(stt, "markers") if nmk else (stt,))

    def update_counts(self):
        c = {}
        for p in self.images:
            s = self.project.info(p.stem).get("status", "todo")
            c[s] = c.get(s, 0) + 1
        nm = sum(1 for p in self.images if self.project.info(p.stem).get("anchors"))
        self.count_var.set("  ".join(f"{STATUS_STYLE[k][0]}: {v}" for k, v in c.items())
                           + (f"   |  with markers: {nm}" if nm else ""))

    def goto(self, step):
        if not self.images:
            return
        stems = [p.stem for p in self.images]
        i = stems.index(self.stem) if self.stem in stems else -1
        j = min(max(i + step, 0), len(stems) - 1)
        self.tree.selection_set(stems[j])
        self.tree.see(stems[j])

    def on_select(self, _e=None):
        sel = self.tree.selection()
        if not sel or sel[0] == self.stem:
            return
        self.save_lines()
        self.open_image(sel[0])

    # ---------------- image loading
    def open_image(self, stem):
        self.stem = stem
        self.current, self.hover_line = None, None
        path = next(p for p in self.images if p.stem == stem)
        self.status_var.set(f"Loading {path.name} …")
        self.root.config(cursor="watch")
        self.root.update_idletasks()
        try:
            if stem not in self._levels_cache:
                levels = build_pyramid(read_image_8bit(str(path)))
                self._levels_cache = {stem: levels}         # keep one image in memory
            self.view.set_image(self._levels_cache[stem])
        except Exception as e:  # noqa
            self.view.clear()
            messagebox.showerror("Image", f"Cannot read {path}:\n{e}")
        finally:
            self.root.config(cursor="")
        self.load_lines()
        self.anchors_overlay = self.project.info(stem).get("anchors") or []
        self.load_match_state()
        inf = self.project.info(stem)
        self.status_var.set(f"{path.name}   {self.view.iw}×{self.view.ih} px   status: "
                            f"{STATUS_STYLE[inf.get('status', 'todo')][0]}")
        self.prior_var.set(self.describe_priors(stem))
        self.view.request_render()

    # ---------------- drawing
    def on_kind(self):
        self.mode.set("draw")
        if self.current and self.current["pts"]:
            self.current["kind"] = self.kind.get()
        self.view_refresh()

    def view_refresh(self):
        self.hover_line = None
        self.view.request_render()

    def add_point(self, p):
        if self.current is None:
            self.current = dict(kind=self.kind.get(), pts=[])
        self.current["pts"].append([float(p[0]), float(p[1])])
        self.view.request_render()

    def undo_point(self):
        if self.current and self.current["pts"]:
            self.current["pts"].pop()
            self.view.request_render()

    def cancel_line(self):
        self.current = None
        self.view.request_render()

    def finish_line(self):
        if self.current and len(self.current["pts"]) >= 2:
            self.lines.append(dict(kind=self.current["kind"], pts=np.asarray(self.current["pts"])))
            self.save_lines()
        self.current = None
        self.view.request_render()

    def delete_line(self, ln):
        self.lines = [l for l in self.lines if l is not ln]
        self.hover_line = None
        self.save_lines()
        self.view.request_render()

    def clear_lines(self):
        if self.lines and messagebox.askyesno("Clear", "Delete all lines of this image?"):
            self.lines = []
            self.save_lines()
            self.view.request_render()

    def import_lines(self):
        if not self.stem:
            return
        p = filedialog.askopenfilename(title=f"Lines for '{FEATURES[self.kind.get()]['label']}' "
                                             f"(pixel coords, e.g. digitised in QGIS)",
                                       filetypes=[("Vector", "*.geojson *.json *.shp *.gpkg"), ("All", "*.*")])
        if not p:
            return
        try:
            import geopandas as gpd
            g = gpd.read_file(p)
            core = _core()
            n = 0
            for l in core.iter_lines(g.geometry):
                pts = np.column_stack([l[:, 0], -l[:, 1]]) if np.median(l[:, 1]) <= 0 else l[:, :2]
                self.lines.append(dict(kind=self.kind.get(), pts=pts))
                n += 1
            self.save_lines()
            self.view.request_render()
            self.status_var.set(f"Imported {n} line(s) as {FEATURES[self.kind.get()]['label']}")
        except Exception as e:  # noqa
            messagebox.showerror("Import", str(e))

    def save_lines(self):
        if not self.stem:
            return
        feats = [dict(type="Feature", properties=dict(kind=l["kind"]),
                      geometry=dict(type="LineString",
                                    coordinates=[[float(x), -float(y)] for x, y in l["pts"]]))
                 for l in self.lines]
        fp = self.project.features_path(self.stem)
        if feats or fp.exists():
            fp.write_text(json.dumps(dict(type="FeatureCollection", name=self.stem, features=feats)))
        inf = self.project.info(self.stem)
        if inf.get("status", "todo") in ("todo", "drawn"):
            inf["status"] = "drawn" if feats else "todo"
        self.project.save()
        self.update_row(self.stem)
        self.update_counts()
        n = {k: sum(1 for l in self.lines if l["kind"] == k) for k in FEATURES}
        self.lines_var.set("  ".join(f"{FEATURES[k]['label']}: {v}" for k, v in n.items()))

    def load_lines(self):
        self.lines = []
        fp = self.project.features_path(self.stem)
        if fp.exists():
            try:
                d = json.loads(fp.read_text())
                for f in d.get("features", []):
                    c = np.asarray(f["geometry"]["coordinates"], float)
                    kind = f.get("properties", {}).get("kind", "road")
                    self.lines.append(dict(kind=kind if kind in FEATURES else "road",
                                           pts=np.column_stack([c[:, 0], -c[:, 1]])))
            except Exception as e:  # noqa
                self.write_log(f"could not read {fp}: {e}\n")
        n = {k: sum(1 for l in self.lines if l["kind"] == k) for k in FEATURES}
        self.lines_var.set("  ".join(f"{FEATURES[k]['label']}: {v}" for k, v in n.items()))

    # ---------------- priors
    def neighbour(self, stem):
        """Nearest already-matched image (same strip & closest frame first)."""
        done = {k: v for k, v in self.project.matched().items() if k != stem and v.get("status") != "flagged"}
        if not done:
            done = {k: v for k, v in self.project.matched().items() if k != stem}
        if not done:
            return None, None
        s0, f0 = strip_frame(stem)

        def key(k):
            s, f = strip_frame(k)
            if s0 is not None and s == s0:
                return (0, abs(f - f0))
            return (1, -done[k].get("time", 0))
        k = min(done, key=key)
        return k, done[k]

    def priors(self, stem):
        st = self.project.settings
        done = self.project.matched()
        good = [v for k, v in done.items() if k != stem and v.get("status") != "flagged"] or \
               [v for k, v in done.items() if k != stem]
        pri = dict(gsd=(st["gsd_min"], st["gsd_max"]), rot=None, center=None, neighbour=None)
        if good:
            g = float(np.median([v["gsd"] for v in good]))
            pri["gsd"] = (round(g / 1.25, 3), round(g * 1.25, 3))
        nb, inf = self.neighbour(stem)
        if inf:
            r = inf["rot"]
            pri["rot"] = [r, r - 90, r - 180, r + 90]
            pri["center"] = inf.get("center")
            pri["neighbour"] = self.labels.get(nb, nb)
        return pri

    def describe_priors(self, stem):
        na = len(self.project.info(stem).get("anchors") or [])
        if na >= 2:
            return (f"Known markers: {na} (magenta) -> no search needed: the fit starts from them, "
                    f"they stay as constraints")
        p = self.priors(stem)
        txt = f"GSD {p['gsd'][0]:.2f}–{p['gsd'][1]:.2f} m/px"
        if p["rot"]:
            txt += f"; rotation {p['rot'][0]:.0f}° (+0/−90/−180/+90 ±{self.project.settings['rot_halfwidth']:.0f}°)"
        if p["center"]:
            txt += f"; near {p['neighbour']} ({self.project.settings['prior_radius_km']:.0f} km)"
        if na == 1:
            txt += "; 1 known marker: search limited around it"
        elif not p["rot"]:
            txt += "; first image: full search (can take a few minutes)"
        return "Priors: " + txt

    # ---------------- matching
    def check_ready(self):
        st = self.project.settings
        for k, lab in (("aoi", "AOI polygon"), ("osm", "OSM extract")):
            if not st.get(k) or not Path(st[k]).exists():
                messagebox.showwarning("Project", f"Set the {lab} first.")
                return False
        return True

    def build_inputs(self):
        """Write per-kind input files and return (road_path or None, [(aux_path, ref_layers)])."""
        d = self.project.match_dir(self.stem) / "inputs"
        d.mkdir(parents=True, exist_ok=True)
        out = {}
        for kind in FEATURES:
            ls = [l for l in self.lines if l["kind"] == kind]
            p = d / f"{kind}.geojson"
            if not ls:
                if p.exists():
                    p.unlink()
                continue
            feats = [dict(type="Feature", properties={},
                          geometry=dict(type="LineString", coordinates=[[float(x), -float(y)] for x, y in l["pts"]]))
                     for l in ls]
            p.write_text(json.dumps(dict(type="FeatureCollection", features=feats)))
            out[kind] = p
        ap_ = d / "anchors.csv"
        anchors = self.project.info(self.stem).get("anchors") or []
        if anchors:
            import csv
            with open(ap_, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["label", "px_col", "px_row", "lon", "lat", "z"])
                for a in anchors:
                    w.writerow([a["label"], a["col"], a["row"], a["lon"], a["lat"],
                                "" if a.get("z") is None or a["z"] != a["z"] else a["z"]])
        elif ap_.exists():
            ap_.unlink()
        self._anchors_file = ap_ if anchors else None
        road = out.get("road")
        aux = [(out[k], FEATURES[k]["ref"]) for k in ("lake", "river") if k in out]
        return road, aux

    def base_argv(self, road, aux):
        st = self.project.settings
        path = next(p for p in self.images if p.stem == self.stem)
        argv = ["--osm", st["osm"], "--region", st["aoi"], "--image", str(path),
                "--pixel-mode", "qgis", "--out", str(self.project.match_dir(self.stem)),
                "--camera-label", self.stem, "--label-prefix", f"osm_{self.labels[self.stem]}",
                "--master-csv", str(self.project.master_csv),
                "--n-gcps", str(int(st["n_gcps"])), "--aux-gcps", str(int(st["aux_gcps"]))]
        if road:
            argv += ["--road", str(road)]
        for p, ref in aux:
            argv += ["--aux", str(p), "--aux-ref-layer", ref]
        if getattr(self, "_anchors_file", None):
            argv += ["--anchors", str(self._anchors_file)]
        dem_ok = bool(st.get("dem")) and Path(st["dem"]).is_file()
        cam_ok = bool(st.get("camera_xml")) and Path(st["camera_xml"]).is_file()
        if dem_ok:
            argv += ["--dem", st["dem"]]
            if cam_ok:
                argv += ["--camera-xml", st["camera_xml"]]
        if st.get("dem") and not dem_ok:
            self.write_log(f"\n⚠ DEM not found: {st['dem']}  -> camera model OFF\n")
        if st.get("camera_xml") and not cam_ok:
            self.write_log(f"\n⚠ camera calibration not found: {st['camera_xml']}  -> camera model OFF\n")
        if dem_ok and cam_ok:
            self.write_log("\n(camera model ON: DEM + calibration)\n")
        elif not (st.get("dem") and st.get("camera_xml")):
            self.write_log("\n(camera model OFF: set DEM + camera calibration for relief/tilt correction)\n")
        return argv

    def match(self):
        if self.busy or not self.stem or not self.check_ready():
            return
        if self.current and len(self.current["pts"]) >= 2:
            self.finish_line()
        if not self.lines:
            messagebox.showinfo("Match", "Draw at least one road, lake shore or river first.")
            return
        self.save_lines()
        road, aux = self.build_inputs()
        base = self.base_argv(road, aux)
        pri = self.priors(self.stem)
        st = self.project.settings
        attempts = []
        na = len(self.project.info(self.stem).get("anchors") or [])
        if na >= 2:
            attempts.append((f"{na} known markers", base + ["--gsd-range", str(st["gsd_min"]), str(st["gsd_max"])]))
            self.start_worker(self._match_job, self.stem, attempts)
            return
        if na == 1:
            pri["center"] = None            # the marker gives a tighter location prior
        if pri["rot"]:
            a = base + ["--gsd-range", str(pri["gsd"][0]), str(pri["gsd"][1]),
                        "--rotation-centers", *[f"{r:.2f}" for r in pri["rot"]],
                        "--rotation-halfwidth", str(st["rot_halfwidth"])]
            if pri["center"]:
                attempts.append(("priors (GSD, rotation, location)",
                                 a + ["--prior-center", f"{pri['center'][0]:.1f}", f"{pri['center'][1]:.1f}",
                                      "--prior-radius", str(st["prior_radius_km"] * 1000)]))
            attempts.append(("priors (GSD, rotation), whole AOI", a))
        attempts.append(("full search", base + ["--gsd-range", str(st["gsd_min"]), str(st["gsd_max"])]))
        self.start_worker(self._match_job, self.stem, attempts)

    def use_candidate(self):
        if self.busy or not self.stem:
            return
        k = self.cand_box.current()
        cj = self.project.match_dir(self.stem) / "candidates.json"
        if k < 0 or not cj.exists():
            return
        road, aux = self.build_inputs()
        argv = self.base_argv(road, aux) + ["--init-from", str(cj), "--init-candidate", str(k + 1)]
        self.start_worker(self._match_job, self.stem, [(f"candidate #{k + 1}", argv)], True)

    def start_worker(self, fn, *a):
        self.busy = True
        self.match_btn.config(state="disabled", text="matching …")
        self.result_var.set("")
        threading.Thread(target=fn, args=a, daemon=True).start()

    def _match_job(self, stem, attempts, from_candidate=False):
        old = sys.stdout
        sys.stdout = QueueWriter(self.q)
        res, used = None, None
        try:
            core = _core()
            for i, (name, argv) in enumerate(attempts):
                print(f"\n=== {self.labels.get(stem, stem)}: {name} ===")
                r = core.run(core.parse_args(argv))
                res, used = r, name
                serious = SERIOUS_FLAGS & set(r["flags"])
                if not serious or i == len(attempts) - 1:
                    break
                print(f"--> flags {sorted(serious)}: widening the search")
            if not from_candidate and res is not None:
                shutil.copy(res["transform_json"], Path(res["out"]) / "candidates.json")
            self.q.put(("done", (stem, res, used, from_candidate)))
        except Exception as e:  # noqa
            import traceback
            self.q.put(("error", f"{e}\n{traceback.format_exc()}"))
        finally:
            sys.stdout = old

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self.write_log(payload)
                elif kind == "done":
                    self.on_match_done(*payload)
                elif kind == "error":
                    self.busy = False
                    self.match_btn.config(state="normal", text="MATCH with OSM  [M]")
                    self.write_log("\nERROR: " + payload)
                    messagebox.showerror("Matching failed", payload.splitlines()[0])
                elif kind == "msg":
                    self.status_var.set(payload)
                elif kind == "osm_ready":
                    self.svars["osm"].set(payload)
                    self.apply_settings()
                    self.status_var.set(f"OSM extract written: {payload}")
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def write_log(self, s):
        if "\r" in s:   # progress lines: keep only the last state
            s = s.split("\r")[-1]
            self.log.delete("end-1l linestart", "end-1c")
        self.log.insert("end", s)
        self.log.see("end")

    def on_match_done(self, stem, res, used, from_candidate):
        self.busy = False
        self.match_btn.config(state="normal", text="MATCH with OSM  [M]")
        b = res["best"]
        inf = self.project.info(stem)
        serious = SERIOUS_FLAGS & set(res["flags"])
        inf.update(status="flagged" if serious else "matched", gsd=float(b["gsd_mean"]),
                   rot=float(b["rotation_deg"]), contrast=float(b["contrast"]),
                   center=[float(b["center_x"]), float(b["center_y"])], flags=res["flags"],
                   gt=[float(v) for v in res["gt"]], crs=res["crs"], n_gcps=len(res["gcps"]),
                   search=used, time=time.time(), camera_model=res.get("camera_model"), fit=res.get("fit"),
                   candidate=int(used.split("#")[1]) if used.startswith("candidate #") else 1)
        self.project.save()
        self.update_row(stem)
        self.update_counts()
        if stem == self.stem:
            self.load_match_state()
            self.view.request_render()
        self.status_var.set(f"{self.labels.get(stem, stem)}: {len(res['gcps'])} GCPs written "
                            f"({res['seconds']:.0f} s)")

    def load_match_state(self):
        """Result text, candidate list, OSM overlay + GCPs for the current image."""
        inf = self.project.info(self.stem)
        self.osm_overlay, self.gcps_overlay = [], []
        self.cand_box["values"] = []
        self.cand_var.set("")
        self.fit_var.set("")
        if not inf.get("gt"):
            self.result_var.set("")
            return
        ft = inf.get("fit")
        if ft:
            col = "#1b7a1b" if ft["pct"] >= 70 and ft["median_m"] <= 10 else (
                "#c77700" if ft["pct"] >= 40 else "#c0392b")
            per = ", ".join(f"{k} {v['pct']:.0f}%" for k, v in ft["per_feature"].items())
            t3 = ft["thirds_median_m"]
            self.fit_var.set(f"Fit to OSM: {ft['pct']:.0f}% within {ft['good_m']:.0f} m · median {ft['median_m']:.0f} m\n"
                             f"({per}; left/centre/right {t3[0]:.0f}/{t3[1]:.0f}/{t3[2]:.0f} m, {ft['model']} model)")
            self.fit_label.config(fg=col)
        fl = inf.get("flags") or []
        cm = inf.get("camera_model")
        cam_txt = ""
        if cm:
            t3 = cm.get("thirds_median_m", [float("nan")] * 3)
            cam_txt = f"\ncamera: {cm['height_m']:.0f} m a.s.l., tilt {cm['tilt_deg']:.1f}°"
        self.result_var.set(f"distinctness {inf['contrast']:.2f}   GSD {inf['gsd']:.3f} m/px   rot {inf['rot']:.1f}°\n"
                            f"{inf.get('n_gcps', 0)} GCPs ({inf.get('search', '')})" + cam_txt
                            + (f"\n⚠ {', '.join(fl)}" if fl else "\n✓ no warning"))
        cj = self.project.match_dir(self.stem) / "candidates.json"
        if cj.exists():
            try:
                cands = json.loads(cj.read_text())["candidates"]
                self.cand_box["values"] = [f"#{i + 1}  distinct. {c['contrast']:.2f}  GSD {c['gsd_mean']:.2f}  "
                                           f"rot {c['rotation_deg']:.0f}°" for i, c in enumerate(cands)]
                used = inf.get("candidate", 1) - 1
                if 0 <= used < len(cands):
                    self.cand_box.current(used)
            except Exception:  # noqa
                pass
        csvs = list(self.project.match_dir(self.stem).glob("*_gcps.csv"))
        if csvs:
            import csv
            with open(csvs[0], newline="") as f:
                self.gcps_overlay = [dict(label=r["label"], col=float(r["px_col"]), row=float(r["px_row"]))
                                     for r in csv.DictReader(f)]
        try:
            self.osm_overlay = self.project_osm(inf["gt"], inf["crs"], inf.get("camera_model"))
        except Exception as e:  # noqa
            self.write_log(f"(overlay unavailable: {e})\n")

    def osm_layers(self, crs):
        """OSM roads/water of the extract, in the working CRS (cached)."""
        if self._osm_cache and self._osm_cache[0] == crs:
            return self._osm_cache[1]
        import geopandas as gpd
        import pyogrio
        st = self.project.settings
        out = []
        layers = [str(l[0]) for l in pyogrio.list_layers(st["osm"])]
        aoi = gpd.read_file(st["aoi"])
        for lay in layers:
            kind = "road" if "road" in lay else ("water" if "water" in lay else None)
            if kind is None:
                continue
            g = gpd.read_file(st["osm"], layer=lay, mask=aoi.to_crs(4326) if aoi.crs else aoi)
            if g.crs is None:
                g = g.set_crs(4326)
            g = g.to_crs(crs)
            core = _core()
            for geom in g.geometry:
                if geom is None:
                    continue
                if geom.geom_type in ("Polygon", "MultiPolygon"):
                    geom = geom.boundary
                for l in core.iter_lines([geom]):
                    out.append((kind, l))
        self._osm_cache = (crs, out)
        return out

    def project_osm(self, gt, crs, camera_model=None):
        """OSM lines that fall on the image, in image (col,row) coordinates
        (through the camera model + DEM when available, else the flat transform)."""
        A = np.array([[gt[1], gt[2]], [gt[4], gt[5]]])
        Ai = np.linalg.inv(A)
        t = np.array([gt[0], gt[3]])
        W, H = self.view.iw, self.view.ih
        proj = None
        if camera_model and camera_model.get("calibration") and camera_model.get("dem") and \
                Path(camera_model["calibration"]).exists() and Path(camera_model["dem"]).exists():
            try:
                core = _core()
                cam = core.FrameCamera(camera_model["calibration"])
                fp = np.array([[0, 0], [W, 0], [W, H], [0, H]], float)
                fpw = (fp @ A.T) + t
                dem = core.DemSampler(camera_model["dem"], crs, (fpw[:, 0].min(), fpw[:, 1].min(),
                                                                  fpw[:, 0].max(), fpw[:, 1].max()))
                pose = core.Pose(camera_model["R"], camera_model["C"])

                def proj(l):
                    return pose.project(cam, np.column_stack([l, dem(l)]))
            except Exception as e:  # noqa
                self.write_log(f"(camera overlay unavailable, flat overlay used: {e})\n")
                proj = None
        out = []
        for kind, l in self.osm_layers(crs):
            cr = (l - t) @ Ai.T          # flat transform, also used to pre-select
            if cr[:, 0].max() < -300 or cr[:, 0].min() > W + 300 or cr[:, 1].max() < -300 or cr[:, 1].min() > H + 300:
                continue
            if proj is not None:
                cr = proj(l)
                if not np.isfinite(cr).all():
                    continue
            out.append((kind, cr))
        return out

    def open_qa(self):
        if not self.stem:
            return
        pngs = list(self.project.match_dir(self.stem).glob("*_match_qa.png"))
        if not pngs:
            return
        p = str(pngs[0])
        try:
            if sys.platform.startswith("win"):
                os.startfile(p)  # noqa
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", p])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", p])
        except Exception as e:  # noqa
            messagebox.showinfo("QA figure", f"{p}\n({e})")

    # ---------------- decisions
    def accept(self):
        if not self.stem or self.busy:
            return
        inf = self.project.info(self.stem)
        if not inf.get("gt"):
            messagebox.showinfo("Accept", "Nothing to accept yet: match the image first (M) or skip it (S).")
            return
        inf["status"] = "checked"
        self.project.save()
        self.update_row(self.stem)
        self.update_counts()
        self.goto_next_open()

    def skip(self):
        if not self.stem or self.busy:
            return
        inf = self.project.info(self.stem)
        if inf.get("gt") and self.project.master_csv.exists():
            if messagebox.askyesno("Skip", "This image has GCPs in osm_gcps_all.csv.\nRemove them from the table?"):
                _core().update_master_csv(self.project.master_csv, None, self.stem, [])
        inf["status"] = "skipped"
        self.project.save()
        self.update_row(self.stem)
        self.update_counts()
        self.goto_next_open()

    def goto_next_open(self):
        stems = [p.stem for p in self.images]
        i = stems.index(self.stem)
        for s in stems[i + 1:] + stems[:i]:
            if self.project.info(s).get("status", "todo") in ("todo", "drawn"):
                self.tree.selection_set(s)
                self.tree.see(s)
                return
        self.goto(+1)

    # ---------------- known GCPs (Metashape markers)
    def import_markers(self):
        p = filedialog.askopenfilename(title="Metashape markers (File > Export > Export Markers, XML)",
                                       filetypes=[("Metashape XML", "*.xml"), ("All", "*.*")])
        if not p:
            return
        try:
            per_cam, no_ref = read_metashape_markers(p)
        except Exception as e:  # noqa
            messagebox.showerror("Markers", f"Cannot read {p}:\n{e}")
            return
        stems = {im.stem: im.stem for im in self.images}
        stems.update({im.name: im.stem for im in self.images})
        found = {}
        for lab, lst in per_cam.items():
            stem = stems.get(lab) or stems.get(Path(lab).stem)
            if stem:
                found[stem] = lst
        for stem in [im.stem for im in self.images]:          # replace previous imports
            inf = self.project.info(stem)
            if found.get(stem):
                inf["anchors"] = found[stem]
            else:
                inf.pop("anchors", None)
        self.project.settings["markers_file"] = p
        self.project.save()
        for im in self.images:
            self.update_row(im.stem)
        self.update_counts()
        if not found:
            messagebox.showinfo("Markers", f"{len(per_cam)} image(s) with markers in the file, but none matches "
                                           f"the images of the folder (labels must be the image names).")
            return
        n_mk = len({a["label"] for lst in found.values() for a in lst})
        order = sorted(found, key=lambda s_: (-len(found[s_]), s_))
        best = order[0]
        top = ", ".join(f"{self.labels.get(s_, s_)} ({len(found[s_])})" for s_ in order[:6])
        msg = (f"{n_mk} markers on {len(found)} of your images (highlighted, column 'mk').\n"
               f"Images with the most markers: {top}.\n\n"
               f"Start with {self.labels.get(best, best)}: with 2 or more markers no search is needed, "
               f"and the next images then get their priors from it."
               + (f"\n({no_ref} marker(s) without coordinates ignored.)" if no_ref else ""))
        self.write_log("\n" + msg + "\n")
        messagebox.showinfo("Markers imported", msg)
        self.tree.selection_set(best)
        self.tree.see(best)

    # ---------------- OSM clipping helper
    def clip_osm(self):
        st = self.project.settings
        if not st.get("aoi") or not Path(st["aoi"]).exists():
            messagebox.showwarning("Clip", "Set the AOI polygon first.")
            return
        src = filedialog.askopenfilename(title="Country OSM GeoPackage (Geofabrik *-free.gpkg)",
                                         filetypes=[("GeoPackage", "*.gpkg")])
        if not src:
            return
        dst = self.project.root / f"OSM_{Path(st['aoi']).stem}.gpkg"

        def job():
            old = sys.stdout
            sys.stdout = QueueWriter(self.q)
            try:
                from GAPPS_tools.GAPPS_Tool_06b_Shape2GCPs_ClipOSM import clip_osm_to_aoi
                clip_osm_to_aoi(src, st["aoi"], dst)
                self.q.put(("osm_ready", str(dst)))
            except Exception as e:  # noqa
                self.q.put(("error", str(e)))
            finally:
                sys.stdout = old
        self.status_var.set("Clipping OSM … (a minute for a country file)")
        threading.Thread(target=job, daemon=True).start()


def main():
    image_folder = sys.argv[1] if len(sys.argv) > 1 else ""
    output_folder = sys.argv[2] if len(sys.argv) > 2 else ""
    root = tk.Tk()
    Shape2GCPsApp(root, image_folder, output_folder)
    root.mainloop()


if __name__ == "__main__":
    main()
