# -*- coding: utf-8 -*-
"""
========================================================================================
                     GAPPS – GeoRiskA Airphoto Pre-Processing Suite
========================================================================================
                          = FM DETECTION REVIEW / CORRECTION =

Description: Secondary Graphical User Interface (GUI) to review and correct the
    fiducial marks (FM) detected automatically (Tool 2c).
    The corners to review (low matching score, inconsistent geometry, images without
    coordinates — see GAPPS_Tool_02e_FM_Review.py) are shown one by one:
      - left: the corner of the image, for orientation (click to move the FM roughly)
      - middle: zoomable view of the FM for a precise positioning
          mouse wheel (or + / -): zoom · left click: set the FM centre
          right (or middle) button drag: pan · arrows: move 1 pix (Shift: 10 pix)
      - markers: yellow = position to be saved, red x = automatic detection,
          cyan circle = position expected from the three other FMs (geometry)
      - Enter: save and go to the next corner (if the automatic detection is right,
          simply press Enter) · S: skip · Backspace: previous · E: use expected
          position · N: not visible on this image (e.g. no top notch: excluded from
          the reprojection) · R: reset to the automatic detection · A: also review the
          other corners of this image
    "Select images…": review all the FMs of images chosen manually (e.g. badly reprojected
    images), selected in the image folder or among their outputs (B_Reprojected,
    C_Resampled, _preview). "Reload list" goes back to the automatic list.
    Each review is saved immediately in Out_fiducialmarks.csv (backup made before the
    first change) and logged in Out_fiducialmarks_review_log.csv. When run again, the
    reprojection (Tool 3) redoes the images whose FMs have changed.

Copyright:
    RMCA — Royal Museum for Central Africa (Tervuren, BELGIUM)
        Natural Hazards and Cartography (GeoRiskA), Dpt. of Earth Sciences
    VUB — Vrije Universiteit Brussel (Brussels, BELGIUM)
        Physical Geography (FARD), Dpt. of Geography
    © 2026

Software authorship:
    - Antoine DILLE (RMCA)

Usage: python GAPPS_interface_FM_review.py [image_folder]
    image_folder (optional): folder of the images used for the FM detection.
    Default: <output_results_folder_path>/A_CanvasSized_Cropped (or A_CanvasSized).

Last update: 2026-10-26
========================================================================================
"""

# 1. IMPORTS AND PATHS
#######################

import json
import math
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import cv2
import numpy as np
from PIL import Image, ImageTk

absolute_file_path = os.path.abspath(__file__)
gui_folder = os.path.dirname(absolute_file_path)
gapps_main_folder = os.path.dirname(gui_folder)
if gapps_main_folder not in sys.path:
    sys.path.insert(0, gapps_main_folder)

from GAPPS_tools import GAPPS_Tool_02e_FM_Review as fmr

CORNER_LABELS = {'top_left': 'Top-left', 'top_right': 'Top-right',
                 'bot_right': 'Bottom-right', 'bot_left': 'Bottom-left',
                 'top': 'Top (mid-side notch)', 'right': 'Right (mid-side notch)',
                 'bottom': 'Bottom (mid-side notch)', 'left': 'Left (mid-side notch)'}
CONTEXT_SIZE = 360  # screen size of the corner view
CONTEXT_REGION = 2400  # image pixels shown in the corner view
MAX_ZOOM = 16.0
DEFAULT_VIEW = 800  # image pixels visible in the zoom view when a corner is opened


# 2. HELPER FUNCTIONS
######################

def read_gray(path):
    """8-bit grayscale image (unicode-safe path)."""
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise IOError(f'Unable to read {path}')
    return img


def padded_crop(img, x0, y0, x1, y1):
    h, w = img.shape[:2]
    out = np.zeros((y1 - y0, x1 - x0), dtype=img.dtype)
    xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
    if xb > xa and yb > ya:
        out[ya - y0:yb - y0, xa - x0:xb - x0] = img[ya:yb, xa:xb]
    return out


def stretch(a, valid=None):
    """Contrast stretch (1–99 percentiles) to 8 bits."""
    v = a if valid is None else valid
    if v.size == 0:
        return a
    lo, hi = np.percentile(v[::max(1, v.shape[0] // 300), ::max(1, v.shape[1] // 300)], (1, 99))
    if hi <= lo:
        hi = lo + 1
    return np.clip((a.astype(np.float32) - lo) * (255.0 / (hi - lo)), 0, 255).astype(np.uint8)


# 3. GRAPHICAL USER INTERFACE
##############################

class FMReview:

    def __init__(self, root, image_folder):
        self.root = root
        self.image_folder = image_folder
        self.fm_csv = os.path.join(image_folder, fmr.FM_CSV)
        self.queue = []
        self.idx = 0
        self.point = None  # (x, y) position to save, image pixels
        self.cache = {}  # file -> image (current and prefetched)
        self.cache_lock = threading.Lock()
        self.backup_done = False
        self.pending = {}  # images without coordinates: corners reviewed so far
        self.zoom = 1.0
        self.view_c = (0.0, 0.0)
        self.pan_start = None
        self.saved = 0

        layout = fmr.read_layout(image_folder)
        root.title(f"GAPPS – Review of the fiducial mark detection  [{fmr.LAYOUT_LABELS[layout]}]")
        screen_h = root.winfo_screenheight()
        self.zoom_size = int(min(640, max(380, screen_h - 330)))

        # -- Row 0: options
        frame_opt = tk.Frame(root)
        frame_opt.grid(row=0, column=0, columnspan=3, sticky='ew', padx=10, pady=(10, 4))
        tk.Label(frame_opt, text=f"Images: {image_folder}", font=("Arial", 10)).pack(side='left')
        self.opt_reviewed = tk.IntVar(root, value=0)
        self.opt_all = tk.IntVar(root, value=0)
        tk.Button(frame_opt, text="Reload list", command=self.reload).pack(side='right', padx=4)
        tk.Button(frame_opt, text="Select images…", font=("Arial", 10, "bold"),
                  command=self.select_images).pack(side='right', padx=4)
        ttk.Checkbutton(frame_opt, text="Include corners already reviewed",
                        variable=self.opt_reviewed).pack(side='right', padx=8)
        ttk.Checkbutton(frame_opt, text="Review all corners of all images",
                        variable=self.opt_all).pack(side='right', padx=8)

        # -- Row 1: current item
        self.title_var = tk.StringVar(root)
        tk.Label(root, textvariable=self.title_var, font=("Arial", 13, "bold"), anchor='w').grid(
            row=1, column=0, columnspan=3, sticky='ew', padx=10)
        self.reason_var = tk.StringVar(root)
        self.reason_label = tk.Label(root, textvariable=self.reason_var, font=("Arial", 10), anchor='w')
        self.reason_label.grid(row=2, column=0, columnspan=3, sticky='ew', padx=10, pady=(0, 6))

        # -- Row 3, col 0: corner context view
        frame_ctx = tk.Frame(root)
        frame_ctx.grid(row=3, column=0, padx=(10, 5), sticky='n')
        tk.Label(frame_ctx, text="Corner (click: move the FM roughly)", font=("Arial", 9, "bold")).pack(anchor='w')
        self.ctx = tk.Canvas(frame_ctx, width=CONTEXT_SIZE, height=CONTEXT_SIZE, bg='#303030',
                             highlightthickness=0, cursor='crosshair')
        self.ctx.pack()
        self.ctx.bind('<Button-1>', self.on_ctx_click)
        legend = tk.Frame(frame_ctx)
        legend.pack(anchor='w', pady=6)
        for txt, col in (("■ position to save", '#ffd400'), ("✕ automatic detection", '#ff3b30'),
                         ("○ expected from the 3 other FMs", '#00d0ff')):
            tk.Label(legend, text=txt, fg=col, bg='#404040', font=("Arial", 9, "bold")).pack(anchor='w', fill='x')

        # -- Row 3, col 1: zoom view
        frame_zoom = tk.Frame(root)
        frame_zoom.grid(row=3, column=1, padx=5, sticky='n')
        tk.Label(frame_zoom, text="Zoom (wheel: zoom · click: set centre · right drag: pan · arrows: 1 pix)",
                 font=("Arial", 9, "bold")).pack(anchor='w')
        self.zc = tk.Canvas(frame_zoom, width=self.zoom_size, height=self.zoom_size, bg='#303030',
                            highlightthickness=0, cursor='tcross')
        self.zc.pack()
        self.zc.bind('<Button-1>', self.on_zoom_click)
        for b in (2, 3):
            self.zc.bind(f'<ButtonPress-{b}>', self.on_pan_start)
            self.zc.bind(f'<B{b}-Motion>', self.on_pan_move)
        self.zc.bind('<MouseWheel>', lambda e: self.zoom_at(e.x, e.y, 1.25 if e.delta > 0 else 1 / 1.25))
        self.zc.bind('<Button-4>', lambda e: self.zoom_at(e.x, e.y, 1.25))
        self.zc.bind('<Button-5>', lambda e: self.zoom_at(e.x, e.y, 1 / 1.25))
        self.zc.bind('<Motion>', self.on_zoom_motion)
        self.info_var = tk.StringVar(root)
        tk.Label(frame_zoom, textvariable=self.info_var, font=("Consolas", 9), anchor='w').pack(fill='x')

        # -- Row 3, col 2: actions
        frame_act = tk.Frame(root)
        frame_act.grid(row=3, column=2, padx=(5, 10), sticky='n')
        style = ttk.Style()
        style.configure("Save.TButton", font=("Arial", 12, "bold"))
        ttk.Button(frame_act, text="✓  Save & next  (Enter)", style="Save.TButton",
                   command=self.save_next).pack(fill='x', pady=(18, 4), ipady=6)
        for txt, cmd in (("Use expected position  (E)", self.use_expected),
                         ("Not visible on this image  (N)", self.not_visible),
                         ("Reset to automatic detection  (R)", self.reset_point),
                         ("Skip – decide later  (S)", self.skip),
                         ("◀ Previous  (Backspace)", self.previous),
                         ("Review the other corners of this image  (A)", self.add_other_corners)):
            ttk.Button(frame_act, text=txt, command=cmd).pack(fill='x', pady=3)
        self.progress_var = tk.StringVar(root)
        tk.Label(frame_act, textvariable=self.progress_var, font=("Arial", 10), justify='left',
                 wraplength=260).pack(anchor='w', pady=(14, 0))

        # Keyboard shortcuts
        root.bind('<Return>', lambda e: self.save_next())
        root.bind('<KP_Enter>', lambda e: self.save_next())
        root.bind('<BackSpace>', lambda e: self.previous())
        for key, (dx, dy) in {'Left': (-1, 0), 'Right': (1, 0), 'Up': (0, -1), 'Down': (0, 1)}.items():
            root.bind(f'<{key}>', lambda e, d=(dx, dy): self.nudge(*d))
            root.bind(f'<Shift-{key}>', lambda e, d=(dx, dy): self.nudge(10 * d[0], 10 * d[1]))
        root.bind('<KeyPress>', self.on_key)

        self.reload()

    # 3.1. Queue and images
    # ----------------------

    def reload(self):
        self.queue = fmr.build_review_queue(self.image_folder, review_all=bool(self.opt_all.get()),
                                            include_reviewed=bool(self.opt_reviewed.get()))
        self.idx = 0
        print(f'{len(self.queue)} corners to review in {self.image_folder}')
        if not self.queue:
            self.show_done()
        else:
            self.open_item()

    def select_images(self):
        """Review all the FMs of images selected manually (e.g. images badly reprojected). The images can be
        selected in the image folder, or among their outputs (B_Reprojected, C_Resampled, _preview)."""
        output_folder = os.path.dirname(os.path.normpath(self.image_folder))
        initial = next((d for d in (os.path.join(output_folder, 'C_Resampled'),
                                    os.path.join(output_folder, 'B_Reprojected')) if os.path.isdir(d)),
                       self.image_folder)
        files = filedialog.askopenfilenames(
            parent=self.root, initialdir=initial,
            title="Select the images whose fiducial marks you want to review "
                  "(cropped, reprojected or resampled images)",
            filetypes=[("Images", "*.tif *.tiff *.TIF *.TIFF *.jpg *.jpeg"), ("All files", "*.*")])
        if not files:
            return
        available = fmr.list_images(self.image_folder)
        names = list(dict.fromkeys(fmr.source_name(f) for f in files))
        found = [n for n in names if n in available]
        missing = [n for n in names if n not in available]
        if missing:
            messagebox.showwarning(
                "GAPPS – FM review",
                f"{len(missing)} selected image(s) not found in\n{self.image_folder}:\n\n"
                + '\n'.join(missing[:15]) + ('\n…' if len(missing) > 15 else ''), parent=self.root)
        if not found:
            return
        queue = fmr.build_review_queue(self.image_folder, include_score=False, include_geometry=False,
                                       include_missing=False, review_all=True, include_reviewed=True, only=found)
        for q in queue:
            q['reasons'] = ['selected manually']
        self.queue = queue
        self.idx = 0
        print(f'{len(found)} image(s) selected manually: {len(queue)} fiducial marks to review')
        self.open_item()

    def get_image(self, file):
        with self.cache_lock:
            if file in self.cache:
                return self.cache[file]
        img = read_gray(os.path.join(self.image_folder, file))
        with self.cache_lock:
            self.cache[file] = img
        return img

    def prefetch(self):
        """Load the next image of the list in the background (and drop the others from memory)."""
        files = [it['file'] for it in self.queue[self.idx:self.idx + 8]]
        keep = list(dict.fromkeys(files))[:2]
        with self.cache_lock:
            for f in list(self.cache):
                if f not in keep:
                    del self.cache[f]
        if len(keep) > 1 and keep[1] not in self.cache:
            threading.Thread(target=self._load_quietly, args=(keep[1],), daemon=True).start()

    def _load_quietly(self, file):
        try:
            self.get_image(file)
        except Exception:
            pass

    @property
    def item(self):
        return self.queue[self.idx] if 0 <= self.idx < len(self.queue) else None

    def open_item(self):
        it = self.item
        if it is None:
            self.show_done()
            return
        self.title_var.set(f"{it['name']}  –  {CORNER_LABELS[it['corner']]} fiducial mark"
                           f"      [{self.idx + 1} / {len(self.queue)}]")
        reasons = ', '.join(it['reasons'])
        geo = ''
        if it.get('geometry_ok') is True:
            geo = f"   ·   geometry of the 4 FMs OK (closure {it['closure']:.0f} px): the detection is probably right"
        self.reason_var.set(f"To check: {reasons}{geo}")
        self.reason_label.config(fg='#1a7f37' if it.get('geometry_ok') is True else '#b42318')
        self.root.config(cursor='watch')
        self.root.update_idletasks()
        try:
            self.img = self.get_image(it['file'])
        except Exception as e:
            self.root.config(cursor='')
            messagebox.showerror("GAPPS – FM review", str(e), parent=self.root)
            return
        self.root.config(cursor='')
        start = it['auto'] or it.get('expected') or it.get('usual')
        if start is None:
            h, w = self.img.shape
            c = it['corner']
            if c in fmr.SIDES:  # middle of the side
                start = ({'left': 0.05, 'right': 0.95}.get(c, 0.5) * w, {'top': 0.05, 'bottom': 0.95}.get(c, 0.5) * h)
            else:
                start = ((0.07 if 'left' in c else 0.93) * w, (0.07 if 'top' in c else 0.93) * h)
        self.point = (int(round(start[0])), int(round(start[1])))
        self.zoom = self.zoom_size / DEFAULT_VIEW
        self.view_c = (self.point[0] + 0.5, self.point[1] + 0.5)
        self.redraw()
        self.prefetch()

    def show_done(self):
        self.title_var.set("Nothing (left) to review")
        self.reason_var.set(f"{self.saved} corner(s) saved in this session in {self.fm_csv}. "
                            "Use the options above, or 'Select images…', to review more corners.")
        self.reason_label.config(fg='#1a7f37')
        self.ctx.delete('all')
        self.zc.delete('all')
        self.info_var.set('')
        self.progress_var.set('')

    # 3.2. Actions
    # -------------

    def save_next(self):
        it = self.item
        if it is None:
            return
        if not self.backup_done:
            backup = fmr.backup_fm(self.fm_csv)
            if backup:
                print(f'Backup of the FM coordinates: {backup}')
            self.backup_done = True
        x, y = self.point
        action = 'confirmed' if it['auto'] is not None and (x, y) == tuple(it['auto']) else 'corrected'
        written = fmr.set_corner(self.fm_csv, it['name'], it['corner'], x, y, pending=self.pending)
        fmr.log_review(self.image_folder, it['name'], it['corner'], '; '.join(it['reasons']),
                       it['auto'], (x, y), action)
        self.saved += 1
        print(f" > {it['name']} {it['corner']}: {action} ({x}, {y})"
              + ('' if written else '  [saved when the 4 corners of this image are set]'))
        self.idx += 1
        self.open_item()

    def not_visible(self):
        """The FM is not visible (e.g. no top notch: frame edge outside the scan). Its expected position is
        saved with accuracy -1: it is not used by the reprojection (which then needs the three other FMs)."""
        it = self.item
        if it is None:
            return
        if not self.backup_done:
            fmr.backup_fm(self.fm_csv)
            self.backup_done = True
        xy = it.get('expected')
        if xy is None or xy[0] != xy[0]:  # no expected position (None or NaN)
            xy = it['auto'] or self.point
        x, y = int(round(xy[0])), int(round(xy[1]))
        fmr.set_corner(self.fm_csv, it['name'], it['corner'], x, y, accuracy=-1.0, pending=self.pending)
        fmr.log_review(self.image_folder, it['name'], it['corner'], '; '.join(it['reasons']), it['auto'], (x, y),
                       'not_visible')
        self.saved += 1
        print(f" > {it['name']} {it['corner']}: not visible (excluded from the reprojection)")
        self.idx += 1
        self.open_item()

    def skip(self):
        if self.item is not None:
            self.idx += 1
            self.open_item()

    def previous(self):
        if self.idx > 0:
            self.idx -= 1
            self.open_item()

    def use_expected(self):
        it = self.item
        if it is not None and it.get('expected') is not None:
            self.point = (int(round(it['expected'][0])), int(round(it['expected'][1])))
            self.view_c = (self.point[0] + 0.5, self.point[1] + 0.5)
            self.redraw()

    def reset_point(self):
        it = self.item
        if it is not None and it['auto'] is not None:
            self.point = tuple(it['auto'])
            self.view_c = (self.point[0] + 0.5, self.point[1] + 0.5)
            self.redraw()

    def add_other_corners(self):
        it = self.item
        if it is None:
            return
        present = {(q['name'], q['corner']) for q in self.queue}
        others = fmr.build_review_queue(self.image_folder, include_score=False, include_geometry=False,
                                        include_missing=False, review_all=True, include_reviewed=True)
        new = [q for q in others if q['name'] == it['name'] and (q['name'], q['corner']) not in present]
        for q in new:
            q['reasons'] = ['added manually']
        self.queue[self.idx + 1:self.idx + 1] = new
        self.open_item()

    def nudge(self, dx, dy):
        if self.point is None:
            return
        self.point = self.clamp(self.point[0] + dx, self.point[1] + dy)
        self.redraw()

    def on_key(self, event):
        c = event.char.lower() if event.char else ''
        if c == 's':
            self.skip()
        elif c == 'e':
            self.use_expected()
        elif c == 'n':
            self.not_visible()
        elif c == 'r':
            self.reset_point()
        elif c == 'a':
            self.add_other_corners()
        elif c in ('+', '='):
            self.zoom_at(self.zoom_size / 2, self.zoom_size / 2, 1.25)
        elif c in ('-', '_'):
            self.zoom_at(self.zoom_size / 2, self.zoom_size / 2, 1 / 1.25)

    def clamp(self, x, y):
        h, w = self.img.shape
        return int(min(max(x, 0), w - 1)), int(min(max(y, 0), h - 1))

    # 3.3. Views
    # -----------

    def ctx_window(self):
        """Image window (x0, y0) shown in the corner view, around the current point."""
        h, w = self.img.shape
        R = min(CONTEXT_REGION, w, h)
        x0 = int(min(max(self.point[0] - R / 2, 0), w - R))
        y0 = int(min(max(self.point[1] - R / 2, 0), h - R))
        return x0, y0, R

    def on_ctx_click(self, event):
        if self.item is None:
            return
        x0, y0, R = self.ctx_window()
        s = R / CONTEXT_SIZE
        self.point = self.clamp(x0 + event.x * s, y0 + event.y * s)
        self.view_c = (self.point[0] + 0.5, self.point[1] + 0.5)
        self.redraw()

    def screen_to_image(self, u, v):
        half = self.zoom_size / 2
        return self.view_c[0] + (u - half) / self.zoom, self.view_c[1] + (v - half) / self.zoom

    def image_to_screen(self, x, y):
        half = self.zoom_size / 2
        return (x - self.view_c[0]) * self.zoom + half, (y - self.view_c[1]) * self.zoom + half

    def on_zoom_click(self, event):
        if self.item is None:
            return
        x, y = self.screen_to_image(event.x + 0.5, event.y + 0.5)
        self.point = self.clamp(math.floor(x), math.floor(y))
        self.redraw()

    def on_pan_start(self, event):
        self.pan_start = (event.x, event.y, self.view_c)

    def on_pan_move(self, event):
        if self.pan_start is None or self.item is None:
            return
        x0, y0, (cx, cy) = self.pan_start
        self.view_c = (cx - (event.x - x0) / self.zoom, cy - (event.y - y0) / self.zoom)
        self.draw_zoom()

    def zoom_at(self, u, v, factor):
        if self.item is None:
            return
        new_zoom = min(MAX_ZOOM, max(self.zoom_size / 4000, self.zoom * factor))
        x, y = self.screen_to_image(u, v)
        half = self.zoom_size / 2
        self.zoom = new_zoom
        self.view_c = (x - (u - half) / new_zoom, y - (v - half) / new_zoom)
        self.draw_zoom()

    def on_zoom_motion(self, event):
        if self.item is None:
            return
        x, y = self.screen_to_image(event.x + 0.5, event.y + 0.5)
        self.update_info((math.floor(x), math.floor(y)))

    def update_info(self, cursor=None):
        it = self.item
        if it is None:
            return
        txt = f"×{self.zoom:.2f}  FM to save: ({self.point[0]}, {self.point[1]})"
        if it['auto'] is not None:
            d = math.hypot(self.point[0] - it['auto'][0], self.point[1] - it['auto'][1])
            txt += f"  moved {d:.0f} px"
        if cursor is not None:
            txt += f"  cursor ({cursor[0]}, {cursor[1]})"
        self.info_var.set(txt)

    def redraw(self):
        self.draw_ctx()
        self.draw_zoom()
        it = self.item
        if it is not None:
            remaining = len(self.queue) - self.idx
            self.progress_var.set(f"{remaining} corner(s) left in the list.\n{self.saved} saved in this session.\n\n"
                                  "If the yellow cross is on the FM centre, just press Enter.")

    def draw_markers(self, canvas, to_screen, size):
        """Draw the automatic, expected and current positions on a view."""
        it = self.item
        if it.get('expected') is not None:
            ex, ey = to_screen(it['expected'][0] + 0.5, it['expected'][1] + 0.5)
            canvas.create_oval(ex - size, ey - size, ex + size, ey + size, outline='black', width=4)
            canvas.create_oval(ex - size, ey - size, ex + size, ey + size, outline='#00d0ff', width=2)
        if it['auto'] is not None:
            ax, ay = to_screen(it['auto'][0] + 0.5, it['auto'][1] + 0.5)
            r = size * 0.7
            for w, col in ((4, 'black'), (2, '#ff3b30')):
                canvas.create_line(ax - r, ay - r, ax + r, ay + r, fill=col, width=w)
                canvas.create_line(ax - r, ay + r, ax + r, ay - r, fill=col, width=w)

    def draw_ctx(self):
        self.ctx.delete('all')
        if self.item is None:
            return
        x0, y0, R = self.ctx_window()
        crop = self.img[y0:y0 + R, x0:x0 + R]
        small = cv2.resize(crop, (CONTEXT_SIZE, CONTEXT_SIZE), interpolation=cv2.INTER_AREA)
        self.photo_ctx = ImageTk.PhotoImage(Image.fromarray(stretch(small)))
        self.ctx.create_image(0, 0, anchor='nw', image=self.photo_ctx)
        s = CONTEXT_SIZE / R
        to_screen = lambda x, y: ((x - x0) * s, (y - y0) * s)
        self.draw_markers(self.ctx, to_screen, 9)
        # zoom window extent and current point
        zx0, zy0 = self.screen_to_image(0, 0)
        zx1, zy1 = self.screen_to_image(self.zoom_size, self.zoom_size)
        self.ctx.create_rectangle((zx0 - x0) * s, (zy0 - y0) * s, (zx1 - x0) * s, (zy1 - y0) * s,
                                  outline='white', dash=(2, 2), tags='zoomwin')
        px, py = to_screen(self.point[0] + 0.5, self.point[1] + 0.5)
        for w, col in ((4, 'black'), (2, '#ffd400')):
            self.ctx.create_line(px - 10, py, px + 11, py, fill=col, width=w)
            self.ctx.create_line(px, py - 10, px, py + 11, fill=col, width=w)

    def draw_zoom(self):
        zc = self.zc
        zc.delete('all')
        if self.item is None:
            return
        L, z = self.zoom_size, self.zoom
        x0, y0 = self.screen_to_image(0, 0)
        ix0, iy0 = math.floor(x0), math.floor(y0)
        n = int(math.ceil(L / z)) + 2
        sub = padded_crop(self.img, ix0, iy0, ix0 + n, iy0 + n)
        h, w = self.img.shape
        valid = self.img[max(iy0, 0):min(iy0 + n, h), max(ix0, 0):min(ix0 + n, w)]
        sub = stretch(sub, valid)
        off_x, off_y = (ix0 - x0) * z, (iy0 - y0) * z
        if z >= 1:
            m = np.float32([[z, 0, off_x + (z - 1) / 2], [0, z, off_y + (z - 1) / 2]])
            view = cv2.warpAffine(sub, m, (L, L), flags=cv2.INTER_NEAREST, borderValue=0)
        else:
            small = cv2.resize(sub, (max(1, int(round(n * z))),) * 2, interpolation=cv2.INTER_AREA)
            m = np.float32([[1, 0, off_x], [0, 1, off_y]])
            view = cv2.warpAffine(small, m, (L, L), flags=cv2.INTER_LINEAR, borderValue=0)
        self.photo_zoom = ImageTk.PhotoImage(Image.fromarray(view))
        zc.create_image(0, 0, anchor='nw', image=self.photo_zoom)
        self.draw_markers(zc, self.image_to_screen, 12)

        # position to save: crosshair leaving the centre pixel visible
        cx0, cy0 = self.image_to_screen(*self.point)
        cx1, cy1 = self.image_to_screen(self.point[0] + 1, self.point[1] + 1)
        cx, cy = (cx0 + cx1) / 2, (cy0 + cy1) / 2
        gap = max(6, (cx1 - cx0) / 2 + 3)
        for (a, b, c, d) in ((0, cy, cx - gap, cy), (cx + gap, cy, L, cy),
                             (cx, 0, cx, cy - gap), (cx, cy + gap, cx, L)):
            zc.create_line(a, b, c, d, fill='black', width=3)
            zc.create_line(a, b, c, d, fill='#ffd400', width=1)
        if z >= 4:
            zc.create_rectangle(cx0 - 1, cy0 - 1, cx1 + 1, cy1 + 1, outline='black', width=1)
            zc.create_rectangle(cx0, cy0, cx1, cy1, outline='#ffd400', width=2)
        self.update_info()

        # keep the zoom window outline of the corner view up to date
        if self.ctx.find_withtag('zoomwin'):
            cx_0, cy_0, R = self.ctx_window()
            s = CONTEXT_SIZE / R
            x1, y1 = self.screen_to_image(L, L)
            self.ctx.coords('zoomwin', (x0 - cx_0) * s, (y0 - cy_0) * s, (x1 - cx_0) * s, (y1 - cy_0) * s)


def interface_fm_review(image_folder=None):
    if image_folder is None:
        with open(os.path.join(gapps_main_folder, 'GAPPS_config.json'), 'r') as f:
            output_results_folder = json.load(f)['output_results_folder_path']
        candidates = [os.path.join(output_results_folder, n) for n in ("A_CanvasSized_Cropped", "A_CanvasSized")]
        image_folder = next((c for c in candidates if os.path.isfile(os.path.join(c, fmr.FM_CSV))), candidates[0])
    root = tk.Tk()
    if not os.path.isdir(image_folder):
        messagebox.showerror("GAPPS – FM review", f"Image folder not found:\n{image_folder}")
        return
    FMReview(root, image_folder)
    root.mainloop()


if __name__ == '__main__':
    interface_fm_review(sys.argv[1] if len(sys.argv) > 1 else None)

# ------------------------------------------------------------------------------
# END OF SECONDARY GUI
# ------------------------------------------------------------------------------
