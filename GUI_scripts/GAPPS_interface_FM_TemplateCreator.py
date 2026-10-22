# -*- coding: utf-8 -*-
"""
========================================================================================
                     GAPPS – GeoRiskA Airphoto Pre-Processing Suite
========================================================================================
                             = FM TEMPLATE CREATOR MENU =

Description: Secondary Graphical User Interface (GUI) to create fiducial mark (FM)
    templates for airphoto pre-processing.
    The GUI loads the first image found in the canvas-sized output folder
    (output_results/A_CanvasSized_Cropped, or A_CanvasSized), or any image chosen by
    the user, and displays it.

    1. Overview (left): click near each of the four fiducial marks. A click is
       assigned to the corner (top left, top right, bottom right, bottom left) of the
       image quadrant it falls in, so the order does not matter; clicking again in a
       quadrant replaces its point and a right click removes it.
    2. Zoom (middle): the active fiducial mark is shown in a zoomable view for a
       pixel-precise positioning.
         - mouse wheel (or + / -): zoom in / out around the cursor
         - left click: set the FM centre on the clicked pixel
         - right (or middle) button drag: pan
         - arrow keys: move the FM centre by 1 pixel (Shift + arrow: 10 pixels)
         - Tab: next fiducial mark; F: fit the view to the template
    3. Templates (right): previews of the four templates as they will be saved;
       click a preview to make it the active fiducial mark.

    The templates are saved directly in output_results/_FM_templates with the FM
    template creator tool.

Copyright:
    RMCA — Royal Museum for Central Africa (Tervuren, BELGIUM)
        Natural Hazards and Cartography (GeoRiskA), Dpt. of Earth Sciences
    VUB — Vrije Universiteit Brussel (Brussels, BELGIUM)
        Physical Geography (FARD), Dpt. of Geography
    © 2022 – 2026

Software management and coordination:
    - Benoît SMETS (RMCA / VUB)

Software authorship:
    - Amélie MAGINOT (ENSG, France)
    - Benoît SMETS (RMCA / VUB)
    - Antoine DILLE (RMCA)

The script was developed on Windows 10 and MacOS ≥ 14.6.

Usage: python GAPPS_interface_FM_TemplateCreator.py [image_folder]
    image_folder (optional): folder in which the first image is searched.
    Default: <output_results_folder_path>/A_CanvasSized_Cropped (from GAPPS_config.json).

Last update: 2026-10-14
========================================================================================
"""

# 1. IMPORTS AND PATHS
#######################

import json
import math
import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageTk

# GAPPS paths
absolute_file_path = os.path.abspath(__file__)  # Extract the path of the GUI
gui_folder = os.path.dirname(absolute_file_path)  # /path/to/GAPPS/GUI_scripts
gapps_main_folder = os.path.dirname(gui_folder)  # /path/to/GAPPS

# Make the GAPPS root folder visible to Python imports
if gapps_main_folder not in sys.path:
    sys.path.insert(0, gapps_main_folder)

# Import useful GAPPS tool
from GAPPS_tools.GAPPS_Tool_02b_Tool_FiducialTemplateCreator import fiducialTemplateCreator, read_image

# Settings
IMAGE_EXTENSIONS = ('.tif', '.tiff', '.png', '.jpg', '.jpeg', '.bmp')
CANVAS_SIZED_FOLDERS = ["A_CanvasSized_Cropped", "A_CanvasSized"]  # images used by the FM detection first
OUT_FM_TEMPLATE_NAME = "_FM_templates"
CORNERS = ['top_left', 'top_right', 'bot_right', 'bot_left']
SIDES = ['top', 'right', 'bottom', 'left']  # layout 'midpoints': notches in the middle of the sides
CORNER_LABELS = {'top': 'Top', 'right': 'Right', 'bottom': 'Bottom', 'left': 'Left',
                 'top_left': 'Top-left', 'top_right': 'Top-right',
                 'bot_right': 'Bottom-right', 'bot_left': 'Bottom-left'}
CORNER_COLOURS = {'top': '#e6194b', 'right': '#3cb44b', 'bottom': '#4363d8', 'left': '#f58231',
                  'top_left': '#e6194b', 'top_right': '#3cb44b',
                  'bot_right': '#4363d8', 'bot_left': '#f58231'}
THUMB_SIZE = 140  # Size (screen pixels) of the template previews
MAX_ZOOM = 24.0  # Maximum zoom (screen pixels per image pixel)
DEFAULT_HALFWIDTH = 240  # Default template half width (image pixels)
DEFAULT_HALFWIDTH_NOTCHES = 250  # Default half width for mid-side notches (mostly the notch shape)


# 2. HELPER FUNCTIONS
######################

def find_first_image(folder):
    """Return the first image (alphabetical order, subfolders included) found in a folder.

    Subfolders starting with '_' (e.g. GAPPS working folders) are skipped.
    Returns None if the folder does not exist or contains no image.
    """
    if not folder or not os.path.isdir(folder):
        return None
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith('_'))
        for name in sorted(filenames):
            if name.lower().endswith(IMAGE_EXTENSIONS):
                return os.path.join(dirpath, name)
    return None


def contrast_limits(img):
    """Display contrast limits (0.5–99.5 percentiles), computed on a subsample of the image."""
    step = max(1, int(max(img.shape[:2]) / 2000))
    lo, hi = np.percentile(img[::step, ::step], (0.5, 99.5))
    if hi <= lo:
        hi = lo + 1
    return float(lo), float(hi)


def to_display(img, lo, hi):
    """Convert an image (any bit depth, gray or BGR/BGRA) to an 8-bit array for display."""
    img = np.clip((img.astype(np.float32) - lo) * (255.0 / (hi - lo)), 0, 255).astype(np.uint8)
    if img.ndim == 3:
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
        elif img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            img = img[:, :, 0]
    return img


def padded_crop(img, x0, y0, x1, y1):
    """Crop img[y0:y1, x0:x1], padding with zeros where the window exceeds the image."""
    h, w = img.shape[:2]
    out = np.zeros((y1 - y0, x1 - x0) + img.shape[2:], dtype=img.dtype)
    xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
    if xb > xa and yb > ya:
        out[ya - y0:yb - y0, xa - x0:xb - x0] = img[ya:yb, xa:xb]
    return out


# 3. GRAPHICAL USER INTERFACE
##############################

class FMTemplateCreator:

    def __init__(self, root, image_folder, output_FM_templates, default_dataset, layout='corners'):
        self.root = root
        self.layout = layout
        self.marks = SIDES if layout == 'midpoints' else CORNERS  # FM 1, 2, 3, 4
        self.image_folder = image_folder
        self.output_FM_templates = output_FM_templates

        self.img = None  # Full resolution image (as read by OpenCV)
        self.img_path = None
        self.scale = 1.0  # Display scale of the overview
        self.lo, self.hi = 0.0, 255.0  # Global display contrast limits
        self.points = {}  # corner -> (x, y), full resolution pixel of the FM centre
        self.active = None  # Corner shown in the zoom view
        self.zoom = 1.0  # Zoom view scale (screen pixels per image pixel)
        self.view_c = (0.0, 0.0)  # Image coordinates of the zoom view centre
        self.pan_start = None
        self.photo_main = None
        self.photo_zoom = None
        self.photo_thumbs = {}

        root.title("GAPPS – Fiducial Template creator" +
                   ("  [mid-side notches]" if layout == 'midpoints' else "  [corner fiducials]"))

        # Widget sizes adapted to the screen
        screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
        self.zoom_size = int(min(560, max(320, screen_h - 300)))
        self.max_canvas_w = max(300, screen_w - self.zoom_size - 2 * THUMB_SIZE - 120)
        self.max_canvas_h = max(300, screen_h - 260)

        # -- Row 0: image selection
        frame_img = tk.Frame(root)
        frame_img.grid(row=0, column=0, columnspan=3, sticky='ew', padx=10, pady=(10, 5))
        tk.Label(frame_img, text="Image:", font=("Arial", 12)).pack(side='left')
        self.image_path_var = tk.StringVar(root)
        tk.Entry(frame_img, textvariable=self.image_path_var, width=90,
                 state='readonly').pack(side='left', padx=5, fill='x', expand=True)
        tk.Button(frame_img, text="Browse…", font=("Arial", 10, "bold"),
                  command=self.browse_image).pack(side='left')

        # -- Row 1: settings and actions
        frame_set = tk.Frame(root)
        frame_set.grid(row=1, column=0, columnspan=3, sticky='ew', padx=10, pady=5)
        tk.Label(frame_set, text="Template dataset name (without space):",
                 font=("Arial", 12)).pack(side='left')
        self.dataset_var = tk.StringVar(root, value=default_dataset)
        tk.Entry(frame_set, textvariable=self.dataset_var, width=25).pack(side='left', padx=(5, 20))

        tk.Label(frame_set, text="Template half width (pix):", font=("Arial", 12)).pack(side='left')
        self.halfwidth_var = tk.StringVar(root, value=str(DEFAULT_HALFWIDTH_NOTCHES if layout == 'midpoints'
                                                          else DEFAULT_HALFWIDTH))
        spin = tk.Spinbox(frame_set, from_=10, to=5000, increment=10, width=7,
                          textvariable=self.halfwidth_var, command=self.redraw)
        spin.pack(side='left', padx=(5, 20))
        spin.bind('<Return>', lambda e: self.redraw())
        spin.bind('<FocusOut>', lambda e: self.redraw())

        self.local_contrast = tk.IntVar(root, value=1)
        ttk.Checkbutton(frame_set, text="Local contrast in zoom", variable=self.local_contrast,
                        command=self.draw_zoom).pack(side='left', padx=(0, 20))

        tk.Button(frame_set, text="Reset points", font=("Arial", 10),
                  command=self.reset_points).pack(side='left', padx=5)
        style = ttk.Style()
        style.configure("Create.TButton", font=("Arial", 12, "bold"), foreground='black')
        ttk.Button(frame_set, text="Create fiducial templates", style="Create.TButton",
                   command=self.create_templates).pack(side='left', padx=5)

        # -- Row 2, column 0: overview
        frame_ov = tk.Frame(root)
        frame_ov.grid(row=2, column=0, padx=(10, 5), pady=5, sticky='nw')
        tk.Label(frame_ov, text="Overview – click near each fiducial mark (right click: remove)",
                 font=("Arial", 10, "bold")).pack(anchor='w')
        self.canvas = tk.Canvas(frame_ov, width=self.max_canvas_w, height=self.max_canvas_h,
                                bg='#303030', highlightthickness=0, cursor='crosshair')
        self.canvas.pack()
        self.canvas.bind('<Button-1>', self.on_main_click)
        self.canvas.bind('<Button-3>', self.on_main_right_click)  # Windows / Linux
        self.canvas.bind('<Button-2>', self.on_main_right_click)  # MacOS right click

        # -- Row 2, column 1: zoom view
        frame_zoom = tk.Frame(root)
        frame_zoom.grid(row=2, column=1, padx=5, pady=5, sticky='n')
        self.zoom_title = tk.Label(frame_zoom, text="Zoom", font=("Arial", 10, "bold"))
        self.zoom_title.pack(anchor='w')
        self.zcanvas = tk.Canvas(frame_zoom, width=self.zoom_size, height=self.zoom_size, bg='#303030',
                                 highlightthickness=2, highlightbackground='#303030', cursor='tcross')
        self.zcanvas.pack()
        self.zcanvas.bind('<Button-1>', self.on_zoom_click)
        for b in (2, 3):  # Pan with the right or middle button
            self.zcanvas.bind(f'<ButtonPress-{b}>', self.on_pan_start)
            self.zcanvas.bind(f'<B{b}-Motion>', self.on_pan_move)
        self.zcanvas.bind('<MouseWheel>', self.on_wheel)  # Windows / MacOS
        self.zcanvas.bind('<Button-4>', lambda e: self.zoom_at(e.x, e.y, 1.25))  # Linux
        self.zcanvas.bind('<Button-5>', lambda e: self.zoom_at(e.x, e.y, 1 / 1.25))  # Linux
        self.zcanvas.bind('<Motion>', self.on_zoom_motion)
        self.zcanvas.bind('<Enter>', lambda e: self.zcanvas.focus_set())
        self.zoom_info = tk.StringVar(root)
        tk.Label(frame_zoom, textvariable=self.zoom_info, font=("Consolas", 9), anchor='w').pack(fill='x')
        tk.Label(frame_zoom, justify='left', anchor='w', fg='gray', font=("Arial", 9, "italic"),
                 text="Wheel or +/-: zoom · left click: set centre · right drag: pan\n"
                      "Arrows: move 1 pix (Shift: 10 pix) · Tab: next FM · F: fit view").pack(fill='x')

        # -- Row 2, column 2: template previews
        frame_prev = tk.Frame(root)
        frame_prev.grid(row=2, column=2, padx=(5, 10), pady=5, sticky='n')
        tk.Label(frame_prev, text="Templates", font=("Arial", 10, "bold")).grid(row=0, column=0,
                                                                               columnspan=2, sticky='w')
        self.thumb_canvases = {}
        self.thumb_titles = {}
        for corner in self.marks:
            r, c = {'top_left': (1, 0), 'top_right': (1, 1), 'bot_left': (2, 0), 'bot_right': (2, 1),
                    'top': (1, 0), 'right': (1, 1), 'left': (2, 0), 'bottom': (2, 1)}[corner]
            cell = tk.Frame(frame_prev)
            cell.grid(row=r, column=c, padx=3, pady=3)
            title = tk.Label(cell, text=CORNER_LABELS[corner], font=("Arial", 9, "bold"),
                             fg=CORNER_COLOURS[corner])
            title.pack()
            tc = tk.Canvas(cell, width=THUMB_SIZE, height=THUMB_SIZE, bg='#505050', highlightthickness=3,
                           highlightbackground='#d9d9d9', cursor='hand2')
            tc.pack()
            tc.bind('<Button-1>', lambda e, cn=corner: self.activate(cn))
            self.thumb_canvases[corner] = tc
            self.thumb_titles[corner] = title

        # -- Row 3: status bar
        self.status_var = tk.StringVar(root)
        tk.Label(root, textvariable=self.status_var, font=("Arial", 10), anchor='w',
                 justify='left').grid(row=3, column=0, columnspan=3, sticky='ew', padx=10, pady=(0, 10))

        # Keyboard shortcuts (inactive while typing in an entry field)
        for key, (dx, dy) in {'Left': (-1, 0), 'Right': (1, 0), 'Up': (0, -1), 'Down': (0, 1)}.items():
            root.bind(f'<{key}>', lambda e, d=(dx, dy): self.nudge(e, d[0], d[1]))
            root.bind(f'<Shift-{key}>', lambda e, d=(dx, dy): self.nudge(e, 10 * d[0], 10 * d[1]))
        root.bind('<Tab>', self.next_corner)
        root.bind('<KeyPress>', self.on_key)

        # Load the first image of the canvas-sized folder
        first_image = find_first_image(image_folder)
        if first_image:
            self.load_image(first_image)
        else:
            self.status_var.set(f"No image found in {image_folder}. "
                                "Use 'Browse…' to select the image used to create the templates.")
            self.redraw()

    # 3.1. Image loading
    # -------------------

    def browse_image(self):
        initial_dir = os.path.dirname(self.img_path) if self.img_path else self.image_folder
        if not initial_dir or not os.path.isdir(initial_dir):
            initial_dir = os.path.expanduser('~')
        path = filedialog.askopenfilename(
            parent=self.root, initialdir=initial_dir, title="Select image",
            filetypes=[("Images", " ".join(f"*{e}" for e in IMAGE_EXTENSIONS)), ("All files", "*.*")])
        if path:
            self.load_image(path)

    def load_image(self, path):
        self.status_var.set(f"Loading {path} …")
        self.root.update_idletasks()
        try:
            img = read_image(path)
        except Exception as e:
            messagebox.showerror("GAPPS – Image loading", f"Could not read the image:\n{path}\n\n{e}",
                                 parent=self.root)
            self.status_var.set("Image loading failed. Use 'Browse…' to select another image.")
            return

        self.img = img
        self.img_path = path
        self.image_path_var.set(path)
        self.points = {}
        self.active = None
        self.lo, self.hi = contrast_limits(img)

        # Downsampled overview for display
        h, w = img.shape[:2]
        self.scale = min(self.max_canvas_w / w, self.max_canvas_h / h, 1.0)
        disp_w, disp_h = max(1, int(round(w * self.scale))), max(1, int(round(h * self.scale)))
        overview = cv2.resize(img, (disp_w, disp_h), interpolation=cv2.INTER_AREA)
        self.photo_main = ImageTk.PhotoImage(Image.fromarray(to_display(overview, self.lo, self.hi)))
        self.canvas.config(width=disp_w, height=disp_h)
        self.canvas.delete('all')
        self.canvas.create_image(0, 0, anchor='nw', image=self.photo_main, tags='image')

        print(f"Image loaded for FM templates: {path} ({w} x {h} pix)")
        self.redraw()

    # 3.2. Point picking
    # -------------------

    def get_halfwidth(self, warn=False):
        try:
            hw = int(float(self.halfwidth_var.get()))
            if hw <= 0:
                raise ValueError
            return hw
        except ValueError:
            if warn:
                messagebox.showerror("GAPPS – Half width",
                                     "The template half width must be a positive integer.", parent=self.root)
            return None

    def corner_of(self, x, y):
        """FM of a click: corner of the image quadrant (corners), or nearest side (mid-side notches)."""
        h, w = self.img.shape[:2]
        if self.layout == 'midpoints':
            dx, dy = x / w - 0.5, y / h - 0.5
            if abs(dx) > abs(dy):
                return 'right' if dx > 0 else 'left'
            return 'bottom' if dy > 0 else 'top'
        return ('top' if y < h / 2 else 'bot') + '_' + ('left' if x < w / 2 else 'right')

    def clamp(self, x, y):
        h, w = self.img.shape[:2]
        return int(min(max(x, 0), w - 1)), int(min(max(y, 0), h - 1))

    def on_main_click(self, event):
        if self.img is None:
            return
        x, y = self.clamp(event.x / self.scale, event.y / self.scale)
        corner = self.corner_of(x, y)
        self.points[corner] = (x, y)
        self.activate(corner)

    def on_main_right_click(self, event):
        if self.img is None:
            return
        corner = self.corner_of(event.x / self.scale, event.y / self.scale)
        self.points.pop(corner, None)
        if self.active == corner:
            self.active = None
        self.redraw()

    def activate(self, corner, fit=True):
        """Show a fiducial mark in the zoom view (fitted to the template box)."""
        if self.img is None or corner not in self.points:
            return
        self.active = corner
        if fit:
            self.fit_view()
        self.redraw()

    def fit_view(self):
        hw = self.get_halfwidth() or DEFAULT_HALFWIDTH
        if self.active in self.points:
            x, y = self.points[self.active]
            self.view_c = (x + 0.5, y + 0.5)
        self.zoom = min(MAX_ZOOM, self.zoom_size / (2.4 * hw))

    def next_corner(self, event=None):
        if isinstance(self.root.focus_get(), (tk.Entry, tk.Spinbox)):
            return None
        available = [c for c in self.marks if c in self.points]
        if available:
            k = (available.index(self.active) + 1) % len(available) if self.active in available else 0
            self.activate(available[k])
        return 'break'

    def nudge(self, event, dx, dy):
        if isinstance(self.root.focus_get(), (tk.Entry, tk.Spinbox)):
            return None
        if self.img is None or self.active not in self.points:
            return 'break'
        x, y = self.points[self.active]
        self.points[self.active] = self.clamp(x + dx, y + dy)
        self.redraw()
        return 'break'

    def on_key(self, event):
        if isinstance(self.root.focus_get(), (tk.Entry, tk.Spinbox)) or self.img is None:
            return
        c = self.zoom_size / 2
        if event.char in ('+', '='):
            self.zoom_at(c, c, 1.25)
        elif event.char in ('-', '_'):
            self.zoom_at(c, c, 1 / 1.25)
        elif event.char in ('f', 'F') and self.active:
            self.fit_view()
            self.redraw()

    # 3.3. Zoom view interactions
    # ----------------------------

    def screen_to_image(self, u, v):
        """Continuous image coordinates of a zoom view location (pixel i covers [i, i+1))."""
        half = self.zoom_size / 2
        return self.view_c[0] + (u - half) / self.zoom, self.view_c[1] + (v - half) / self.zoom

    def image_to_screen(self, x, y):
        half = self.zoom_size / 2
        return (x - self.view_c[0]) * self.zoom + half, (y - self.view_c[1]) * self.zoom + half

    def on_zoom_click(self, event):
        self.zcanvas.focus_set()
        if self.img is None or self.active is None:
            return
        x, y = self.screen_to_image(event.x + 0.5, event.y + 0.5)
        self.points[self.active] = self.clamp(math.floor(x), math.floor(y))
        self.redraw()

    def on_pan_start(self, event):
        self.pan_start = (event.x, event.y, self.view_c)

    def on_pan_move(self, event):
        if self.pan_start is None or self.active is None:
            return
        x0, y0, (cx, cy) = self.pan_start
        self.view_c = (cx - (event.x - x0) / self.zoom, cy - (event.y - y0) / self.zoom)
        self.draw_zoom()

    def on_wheel(self, event):
        self.zoom_at(event.x, event.y, 1.25 if event.delta > 0 else 1 / 1.25)

    def zoom_at(self, u, v, factor):
        """Zoom by a factor while keeping the image location under (u, v) fixed."""
        if self.img is None or self.active is None:
            return
        hw = self.get_halfwidth() or DEFAULT_HALFWIDTH
        min_zoom = self.zoom_size / (8 * hw)
        new_zoom = min(MAX_ZOOM, max(min_zoom, self.zoom * factor))
        x, y = self.screen_to_image(u, v)
        half = self.zoom_size / 2
        self.zoom = new_zoom
        self.view_c = (x - (u - half) / new_zoom, y - (v - half) / new_zoom)
        self.draw_zoom()

    def on_zoom_motion(self, event):
        if self.img is None or self.active is None:
            return
        x, y = self.screen_to_image(event.x + 0.5, event.y + 0.5)
        self.update_zoom_info((math.floor(x), math.floor(y)))

    def update_zoom_info(self, cursor=None):
        if self.active is None or self.active not in self.points:
            self.zoom_info.set("")
            return
        px, py = self.points[self.active]
        txt = f"Zoom ×{self.zoom:.2f}   FM centre x={px}, y={py}"
        if cursor is not None:
            txt += f"   cursor x={cursor[0]}, y={cursor[1]}"
        self.zoom_info.set(txt)

    # 3.4. Drawing
    # -------------

    def box_inside(self, corner, hw):
        h, w = self.img.shape[:2]
        x, y = self.points[corner]
        return x - hw >= 0 and y - hw >= 0 and x + hw <= w and y + hw <= h

    def redraw(self):
        hw = self.get_halfwidth()
        self.draw_overview(hw)
        self.draw_zoom()
        for corner in self.marks:
            self.draw_thumb(corner, hw)
        self.update_status(hw)

    def draw_overview(self, hw):
        self.canvas.delete('overlay')
        if self.img is None or hw is None:
            return
        s = self.scale
        for corner, (x, y) in self.points.items():
            col = CORNER_COLOURS[corner]
            width = 3 if corner == self.active else 1
            self.canvas.create_rectangle((x - hw) * s, (y - hw) * s, (x + hw) * s, (y + hw) * s,
                                         outline=col, width=width, tags='overlay')
            self.canvas.create_line(x * s - 6, y * s, x * s + 7, y * s, fill=col, width=2, tags='overlay')
            self.canvas.create_line(x * s, y * s - 6, x * s, y * s + 7, fill=col, width=2, tags='overlay')
            # Label under the box for top corners, above it for bottom corners
            tx = (x - hw) * s if 'left' in corner else (x + hw) * s
            ty = (y + hw) * s + 2 if 'top' in corner else (y - hw) * s - 2
            anchor = ('n' if 'top' in corner else 's') + ('w' if 'left' in corner else 'e')
            self.canvas.create_text(tx, ty, text=CORNER_LABELS[corner], fill=col, anchor=anchor,
                                    font=("Arial", 9, "bold"), tags='overlay')

    def draw_zoom(self):
        zc = self.zcanvas
        zc.delete('all')
        L = self.zoom_size
        if self.img is None or self.active is None or self.active not in self.points:
            zc.config(highlightbackground='#303030')
            self.zoom_title.config(text="Zoom", fg='black')
            zc.create_text(L / 2, L / 2, fill='white', font=("Arial", 10), justify='center',
                           text="Click near a fiducial mark on the overview\nto inspect it here")
            self.update_zoom_info()
            return

        col = CORNER_COLOURS[self.active]
        zc.config(highlightbackground=col)
        self.zoom_title.config(text=f"Zoom – {CORNER_LABELS[self.active]} fiducial mark", fg=col)

        # Visible image window (integer pixels) and its rendering in the zoom view
        z = self.zoom
        x0, y0 = self.screen_to_image(0, 0)
        ix0, iy0 = math.floor(x0), math.floor(y0)
        n = int(math.ceil(L / z)) + 2
        sub = padded_crop(self.img, ix0, iy0, ix0 + n, iy0 + n)
        if self.local_contrast.get():
            h, w = self.img.shape[:2]
            valid = self.img[max(iy0, 0):min(iy0 + n, h), max(ix0, 0):min(ix0 + n, w)]
            lo, hi = contrast_limits(valid) if valid.size else (self.lo, self.hi)
        else:
            lo, hi = self.lo, self.hi
        sub = to_display(sub, lo, hi)
        off_x, off_y = (ix0 - x0) * z, (iy0 - y0) * z  # Screen position of the window origin
        if z >= 1:
            # Nearest neighbour: every image pixel becomes a z × z block
            m = np.float32([[z, 0, off_x + (z - 1) / 2], [0, z, off_y + (z - 1) / 2]])
            view = cv2.warpAffine(sub, m, (L, L), flags=cv2.INTER_NEAREST, borderValue=0)
        else:
            small = cv2.resize(sub, (max(1, int(round(n * z))),) * 2, interpolation=cv2.INTER_AREA)
            m = np.float32([[1, 0, off_x], [0, 1, off_y]])
            view = cv2.warpAffine(small, m, (L, L), flags=cv2.INTER_LINEAR, borderValue=0)
        self.photo_zoom = ImageTk.PhotoImage(Image.fromarray(view))
        zc.create_image(0, 0, anchor='nw', image=self.photo_zoom)

        # Template box, FM centre pixel and crosshair
        hw = self.get_halfwidth()
        px, py = self.points[self.active]
        if hw is not None:
            bx0, by0 = self.image_to_screen(px - hw, py - hw)
            bx1, by1 = self.image_to_screen(px + hw, py + hw)
            zc.create_rectangle(bx0, by0, bx1, by1, outline=col, width=2, dash=(6, 4))
        cx0, cy0 = self.image_to_screen(px, py)
        cx1, cy1 = self.image_to_screen(px + 1, py + 1)
        cx, cy = (cx0 + cx1) / 2, (cy0 + cy1) / 2
        gap = max(6, (cx1 - cx0) / 2 + 3)  # Leave the centre pixel visible
        for (a, b, c, d) in ((0, cy, cx - gap, cy), (cx + gap, cy, L, cy),
                             (cx, 0, cx, cy - gap), (cx, cy + gap, cx, L)):
            zc.create_line(a, b, c, d, fill=col, width=1)
        if z >= 4:
            zc.create_rectangle(cx0, cy0, cx1, cy1, outline=col, width=2)
        self.update_zoom_info()

        # Show the zoom window extent on the overview
        self.canvas.delete('zoomwin')
        s = self.scale
        x1, y1 = self.screen_to_image(L, L)
        self.canvas.create_rectangle(x0 * s, y0 * s, x1 * s, y1 * s, outline='white', dash=(2, 2),
                                     tags=('overlay', 'zoomwin'))

    def draw_thumb(self, corner, hw):
        tc = self.thumb_canvases[corner]
        tc.delete('all')
        tc.config(highlightbackground=CORNER_COLOURS[corner] if corner == self.active else '#d9d9d9')
        if self.img is None or hw is None or corner not in self.points:
            tc.create_text(THUMB_SIZE / 2, THUMB_SIZE / 2, fill='white', font=("Arial", 8), justify='center',
                           text="not set")
            self.thumb_titles[corner].config(text=CORNER_LABELS[corner])
            return

        # Template exactly as it will be cropped (padded with black where it exceeds the image)
        x, y = self.points[corner]
        crop = padded_crop(self.img, x - hw, y - hw, x + hw, y + hw)
        interp = cv2.INTER_AREA if 2 * hw > THUMB_SIZE else cv2.INTER_NEAREST
        crop = cv2.resize(crop, (THUMB_SIZE, THUMB_SIZE), interpolation=interp)
        photo = ImageTk.PhotoImage(Image.fromarray(to_display(crop, self.lo, self.hi)))
        self.photo_thumbs[corner] = photo  # Keep a reference (avoid garbage collection)
        tc.create_image(0, 0, anchor='nw', image=photo)
        col = CORNER_COLOURS[corner]
        c = THUMB_SIZE / 2
        tc.create_line(c - 10, c, c + 11, c, fill=col, width=2)
        tc.create_line(c, c - 10, c, c + 11, fill=col, width=2)

        warn = "" if self.box_inside(corner, hw) else " ⚠"
        self.thumb_titles[corner].config(text=f"{CORNER_LABELS[corner]} ({x}, {y}){warn}")

    def update_status(self, hw):
        if self.img is None:
            return
        missing = [CORNER_LABELS[c] for c in self.marks if c not in self.points]
        if hw is None:
            self.status_var.set("Invalid half width: enter a positive integer.")
        elif missing:
            self.status_var.set("Click near each fiducial mark on the overview (any order), then refine its "
                                "centre in the zoom view. Missing: " + ", ".join(missing) + ".")
        else:
            outside = [CORNER_LABELS[c] for c in self.marks if not self.box_inside(c, hw)]
            if outside:
                self.status_var.set("Template box exceeds the image for: " + ", ".join(outside)
                                    + ". Reduce the half width or move the point(s).")
            else:
                self.status_var.set("All four fiducial marks set. Check each one in the zoom view (Tab), "
                                    f"then click 'Create fiducial templates' (saved in {self.output_FM_templates}).")

    def reset_points(self):
        self.points = {}
        self.active = None
        self.redraw()

    # 3.5. Template creation
    # -----------------------

    def create_templates(self):
        if self.img is None:
            messagebox.showerror("GAPPS – FM templates", "Please load an image first.", parent=self.root)
            return
        hw = self.get_halfwidth(warn=True)
        if hw is None:
            return
        missing = [CORNER_LABELS[c] for c in self.marks if c not in self.points]
        if missing:
            messagebox.showerror("GAPPS – FM templates",
                                 "Please pick the following fiducial mark(s): " + ", ".join(missing) + ".",
                                 parent=self.root)
            return
        outside = [CORNER_LABELS[c] for c in self.marks if not self.box_inside(c, hw)]
        if outside:
            messagebox.showerror("GAPPS – FM templates",
                                 "The template box exceeds the image for: " + ", ".join(outside)
                                 + ".\nReduce the half width or move the point(s).", parent=self.root)
            return
        dataset = self.dataset_var.get().strip().replace(" ", "_")
        if not dataset:
            messagebox.showerror("GAPPS – FM templates", "Please enter a template dataset name.",
                                 parent=self.root)
            return
        self.dataset_var.set(dataset)

        fiducialCenters = {c: [int(self.points[c][0]), int(self.points[c][1])] for c in self.marks}
        try:
            i = fiducialTemplateCreator(self.img_path, self.output_FM_templates, fiducialCenters, hw, dataset)
        except Exception as e:
            messagebox.showerror("GAPPS – FM templates", f"Template creation failed:\n{e}", parent=self.root)
            return

        print(f"FM templates #{i} created in {self.output_FM_templates}")
        messagebox.showinfo("GAPPS – FM templates",
                            f"Fiducial mark templates (set #{i}) created in:\n{self.output_FM_templates}\n\n"
                            "Select this folder as 'Template folder' for the FM detection.\n"
                            "You can create additional templates (e.g. from another image) "
                            "or close this window.", parent=self.root)


def interface_fiducial_template(image_folder=None, layout='corners'):
    # Get the main output data folder from the GAPPS configuration file
    config_path = os.path.join(gapps_main_folder, 'GAPPS_config.json')
    with open(config_path, 'r') as f:
        user_config = json.load(f)
    output_results_folder = user_config['output_results_folder_path']

    # Folder in which the image is searched: argument, or the canvas-sized output folders
    if image_folder is None:
        candidates = [os.path.join(output_results_folder, name) for name in CANVAS_SIZED_FOLDERS]
        image_folder = next((c for c in candidates if find_first_image(c)), candidates[0])

    # Folder where the FM templates are saved
    output_FM_templates = os.path.join(output_results_folder, OUT_FM_TEMPLATE_NAME)
    os.makedirs(output_FM_templates, exist_ok=True)

    default_dataset = Path(output_results_folder).name

    root = tk.Tk()
    FMTemplateCreator(root, image_folder, output_FM_templates, default_dataset, layout)
    root.mainloop()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='GAPPS fiducial template creator')
    parser.add_argument('image_folder', nargs='?', default=None)
    parser.add_argument('--layout', choices=['corners', 'midpoints'], default='corners',
                        help="'corners': fiducial targets in the corners; 'midpoints': notches in the middle of the sides")
    a = parser.parse_args()
    interface_fiducial_template(a.image_folder, a.layout)

# ------------------------------------------------------------------------------
# END OF SECONDARY GUI
# ------------------------------------------------------------------------------
