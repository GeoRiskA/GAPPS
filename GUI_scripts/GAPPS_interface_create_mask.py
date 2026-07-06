#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
========================================================================================
                     GAPPS – GeoRiskA Airphoto Pre-Processing Suite
========================================================================================
                             = IMAGE MASK CREATOR MENU =

Description: This interface creates one binary mask used to hide fiducial marks located
in the corners of historical aerial photographs.
The mask can be defined either from the dimensions of a reference image or from
manually entered image dimensions. Corner rectangle sizes can be specified as
percentages of the image dimensions or directly in pixels.

Copyright:
    RMCA — Royal Museum for Central Africa (Tervuren, BELGIUM)
        Natural Hazards and Cartography (GeoRiskA), Dpt. of Earth Sciences
    VUB — Vrije Universiteit Brussel (Brussels, BELGIUM)
        Cartography and GIS research group (CGIS), Dpt. of Geography
    © 2021 – 2026

Software management and coordination:
    - Benoît SMETS (RMCA / VUB)

Software authorship:
    - Benoît SMETS (RMCA / VUB)

The script was developed on MacOS ≥ 14.6 and optimised from the original 2021 script,
using Open AI's ChatGPT 5.3.

Last update: 2026-07-03
========================================================================================
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from PIL import Image, ImageTk

# GAPPS paths
absolute_file_path = os.path.abspath(__file__)  # Extract the path of this GUI
gui_folder = os.path.dirname(absolute_file_path)  # /path/to/GAPPS/GUI_scripts
gapps_main_folder = os.path.dirname(gui_folder)  # /path/to/GAPPS

# Make the GAPPS root folder visible to Python imports
if gapps_main_folder not in sys.path:
    sys.path.insert(0, gapps_main_folder)

# Import useful GAPPS tools
from GAPPS_tools.GAPPS_Tool_05_AirPhoto_CreateSingleMask import (
    create_corner_mask,
    read_image_dimensions,
)

class MaskCreatorGUI:
    """Tkinter GUI used to create one corner mask for a photo dataset."""

    def __init__(self, root: tk.Tk, default_input_folder: str = "", default_output_folder: str = "") -> None:
        self.root = root
        self.root.title("GAPPS – Tool 5 – Corner mask creator")
        self.root.resizable(False, False)

        self.default_input_folder = default_input_folder if os.path.isdir(default_input_folder) else os.getcwd()
        self.default_output_folder = default_output_folder if os.path.isdir(default_output_folder) else os.getcwd()

        self.reference_image = tk.StringVar(value="")
        self.output_folder = tk.StringVar(value=self.default_output_folder)
        self.dataset_name = tk.StringVar(value=Path(self.default_output_folder).name or "GAPPS_dataset")
        self.width_px = tk.StringVar(value="")
        self.height_px = tk.StringVar(value="")
        self.mask_x = tk.StringVar(value="12")
        self.mask_y = tk.StringVar(value="12")
        self.mask_unit = tk.StringVar(value="percent")
        self.status = tk.StringVar(value="Select a reference image or enter image dimensions manually.")

        self.preview_label = None
        self._build_gui()

    def _build_gui(self) -> None:
        padding = {"padx": 8, "pady": 5}

        title = tk.Label(
            self.root,
            text="Tool 5 – Create a fiducial-mark corner mask",
            font=("Arial", 13, "bold"),
            fg="black",
        )
        title.grid(row=0, column=0, columnspan=4, sticky="w", **padding)

        ttk.Separator(self.root, orient="horizontal").grid(row=1, column=0, columnspan=4, sticky="ew", pady=8)

        tk.Label(self.root, text="Reference image", font=("Arial", 10), fg="black").grid(row=2, column=0, sticky="w", **padding)
        tk.Entry(self.root, textvariable=self.reference_image, width=62).grid(row=2, column=1, columnspan=2, sticky="w", **padding)
        tk.Button(self.root, text="Browse", command=self._browse_reference_image, fg="black").grid(row=2, column=3, sticky="e", **padding)

        tk.Button(
            self.root,
            text="Read dimensions from image",
            command=self._read_dimensions_from_reference_image,
            fg="black",
            width=26,
        ).grid(row=3, column=1, sticky="w", **padding)

        ttk.Separator(self.root, orient="horizontal").grid(row=4, column=0, columnspan=4, sticky="ew", pady=8)

        tk.Label(self.root, text="Image width (px)", font=("Arial", 10), fg="black").grid(row=5, column=0, sticky="w", **padding)
        tk.Entry(self.root, textvariable=self.width_px, width=16).grid(row=5, column=1, sticky="w", **padding)

        tk.Label(self.root, text="Image height (px)", font=("Arial", 10), fg="black").grid(row=6, column=0, sticky="w", **padding)
        tk.Entry(self.root, textvariable=self.height_px, width=16).grid(row=6, column=1, sticky="w", **padding)

        tk.Label(self.root, text="Corner rectangle width", font=("Arial", 10), fg="black").grid(row=7, column=0, sticky="w", **padding)
        tk.Entry(self.root, textvariable=self.mask_x, width=16).grid(row=7, column=1, sticky="w", **padding)

        tk.Label(self.root, text="Corner rectangle height", font=("Arial", 10), fg="black").grid(row=8, column=0, sticky="w", **padding)
        tk.Entry(self.root, textvariable=self.mask_y, width=16).grid(row=8, column=1, sticky="w", **padding)

        unit_frame = tk.Frame(self.root)
        unit_frame.grid(row=7, column=2, rowspan=2, sticky="w", **padding)
        ttk.Radiobutton(unit_frame, text="% of image dimensions", variable=self.mask_unit, value="percent").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(unit_frame, text="pixels", variable=self.mask_unit, value="pixels").grid(row=1, column=0, sticky="w")

        ttk.Separator(self.root, orient="horizontal").grid(row=9, column=0, columnspan=4, sticky="ew", pady=8)

        tk.Label(self.root, text="Output folder", font=("Arial", 10), fg="black").grid(row=10, column=0, sticky="w", **padding)
        tk.Entry(self.root, textvariable=self.output_folder, width=62).grid(row=10, column=1, columnspan=2, sticky="w", **padding)
        tk.Button(self.root, text="Browse", command=self._browse_output_folder, fg="black").grid(row=10, column=3, sticky="e", **padding)

        tk.Label(self.root, text="Dataset / mask name", font=("Arial", 10), fg="black").grid(row=11, column=0, sticky="w", **padding)
        tk.Entry(self.root, textvariable=self.dataset_name, width=32).grid(row=11, column=1, sticky="w", **padding)

        tk.Button(
            self.root,
            text="Create mask",
            command=self._create_mask,
            font=("Arial", 12, "bold"),
            fg="black",
            width=18,
        ).grid(row=12, column=1, sticky="w", **padding)

        tk.Label(self.root, textvariable=self.status, font=("Arial", 9, "italic"), fg="gray").grid(
            row=13, column=0, columnspan=4, sticky="w", padx=8, pady=8
        )

        self.preview_label = tk.Label(self.root)
        self.preview_label.grid(row=14, column=0, columnspan=4, padx=8, pady=8)

    def _browse_reference_image(self) -> None:
        path = filedialog.askopenfilename(
            initialdir=self.default_output_folder,
            title="Select a reference aerial photograph",
            filetypes=[
                ("Image files", "*.tif *.tiff *.jpg *.jpeg *.png *.bmp"),
                ("TIFF files", "*.tif *.tiff"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.reference_image.set(path)
            self._read_dimensions_from_reference_image()

    def _browse_output_folder(self) -> None:
        path = filedialog.askdirectory(initialdir=self.default_output_folder, title="Select output folder")
        if path:
            self.output_folder.set(path)
            if not self.dataset_name.get().strip():
                self.dataset_name.set(Path(path).name)

    def _read_dimensions_from_reference_image(self) -> None:
        image_path = self.reference_image.get().strip()
        if not image_path:
            messagebox.showwarning("Missing reference image", "Please select a reference image first.")
            return
        try:
            width, height = read_image_dimensions(image_path)
        except Exception as exc:
            messagebox.showerror("Cannot read image", str(exc))
            return
        self.width_px.set(str(width))
        self.height_px.set(str(height))
        self.status.set(f"Image dimensions read: {width} × {height} pixels.")

    def _validated_parameters(self) -> dict:
        try:
            width = int(self.width_px.get())
            height = int(self.height_px.get())
            mask_x = float(self.mask_x.get())
            mask_y = float(self.mask_y.get())
        except ValueError as exc:
            raise ValueError("Width, height and mask dimensions must be numeric values.") from exc

        if width <= 0 or height <= 0:
            raise ValueError("Image width and height must be strictly positive.")
        if mask_x <= 0 or mask_y <= 0:
            raise ValueError("Corner rectangle dimensions must be strictly positive.")
        if self.mask_unit.get() == "percent" and (mask_x > 50 or mask_y > 50):
            raise ValueError("Percentage-based corner masks should not exceed 50% in X or Y.")
        if self.mask_unit.get() == "pixels" and (mask_x > width / 2 or mask_y > height / 2):
            raise ValueError("Pixel-based corner masks should not exceed half of the image width or height.")

        output_folder = self.output_folder.get().strip()
        dataset_name = self.dataset_name.get().strip()
        if not output_folder:
            raise ValueError("Please define an output folder.")
        if not dataset_name:
            raise ValueError("Please define a dataset / mask name.")

        return {
            "width": width,
            "height": height,
            "mask_x": mask_x,
            "mask_y": mask_y,
            "unit": self.mask_unit.get(),
            "output_folder": output_folder,
            "dataset_name": dataset_name,
        }

    def _create_mask(self) -> None:
        try:
            params = self._validated_parameters()
            output_path = Path(params["output_folder"]) / f"{params['dataset_name']}_mask.png"
            create_corner_mask(
                params["width"],
                params["height"],
                params["mask_x"],
                params["mask_y"],
                unit=params["unit"],
                output_path=output_path,
            )
        except Exception as exc:
            messagebox.showerror("Mask creation failed", str(exc))
            return

        self.status.set(f"Mask created: {output_path}")
        messagebox.showinfo("Mask created", f"Mask saved to:\n{output_path}")


def main() -> None:
    default_input_folder = sys.argv[1] if len(sys.argv) > 1 else ""
    default_output_folder = sys.argv[2] if len(sys.argv) > 2 else ""
    root = tk.Tk()
    MaskCreatorGUI(root, default_input_folder, default_output_folder)
    root.mainloop()


if __name__ == "__main__":
    main()
