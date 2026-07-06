#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
------------------------------------------------------------------------------
GAPPS TOOL 5 — CREATE ONE CORNER MASK FOR AERIAL PHOTOGRAPHS
------------------------------------------------------------------------------
This module creates a binary mask used to hide fiducial marks located in the
corners of historical aerial photographs.

Main functions
--------------
- read_image_dimensions(image_path)
- create_corner_mask(width, height, mask_size_x, mask_size_y, unit="percent")
- image_masking_from_reference_image(...)
- image_masking_from_dimensions(...)
- image_masking(...), kept for backwards compatibility with the former folder-
  based workflow.
------------------------------------------------------------------------------
"""

import glob
import os
from pathlib import Path
from time import sleep

import numpy as np
from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None


def read_image_dimensions(image_path):
    """Return image dimensions as (width, height) in pixels."""
    image_path = Path(image_path)
    if not image_path.is_file():
        raise FileNotFoundError(f"Reference image does not exist: {image_path}")

    with Image.open(image_path) as img:
        return img.size


def _mask_margins(width, height, mask_size_x, mask_size_y, unit="percent"):
    """Convert user mask dimensions to pixel margins."""
    width = int(width)
    height = int(height)
    mask_size_x = float(mask_size_x)
    mask_size_y = float(mask_size_y)

    if width <= 0 or height <= 0:
        raise ValueError("Image width and height must be strictly positive.")
    if mask_size_x <= 0 or mask_size_y <= 0:
        raise ValueError("Mask dimensions must be strictly positive.")

    if unit == "percent":
        if mask_size_x > 50 or mask_size_y > 50:
            raise ValueError("Percentage-based masks should not exceed 50% in X or Y.")
        margin_x = round((mask_size_x / 100.0) * width)
        margin_y = round((mask_size_y / 100.0) * height)
    elif unit == "pixels":
        margin_x = round(mask_size_x)
        margin_y = round(mask_size_y)
        if margin_x > width / 2 or margin_y > height / 2:
            raise ValueError("Pixel-based masks should not exceed half of the image width or height.")
    else:
        raise ValueError("unit must be either 'percent' or 'pixels'.")

    return margin_x, margin_y


def create_corner_mask(width, height, mask_size_x=12, mask_size_y=12, unit="percent", output_path=None):
    """
    Create a binary PIL mask with black rectangles in the four corners.

    Parameters
    ----------
    width, height : int
        Image dimensions in pixels.
    mask_size_x, mask_size_y : float
        Corner rectangle width and height. Interpreted as percentages when
        unit="percent", and as pixels when unit="pixels".
    unit : {"percent", "pixels"}
        Unit used for mask_size_x and mask_size_y.
    output_path : str or pathlib.Path, optional
        If provided, the mask is saved to this path.

    Returns
    -------
    PIL.Image.Image
        Single-band L-mode mask: white=kept area, black=masked area.
    """
    dim_x = int(width)
    dim_y = int(height)
    margin_x, margin_y = _mask_margins(dim_x, dim_y, mask_size_x, mask_size_y, unit=unit)

    mask = Image.new("L", size=(dim_x, dim_y), color=255)
    draw = ImageDraw.Draw(mask)

    # Top-left
    draw.rectangle([(0, 0), (margin_x, margin_y)], fill=0)
    # Top-right
    draw.rectangle([(dim_x - margin_x, 0), (dim_x, margin_y)], fill=0)
    # Bottom-right
    draw.rectangle([(dim_x - margin_x, dim_y - margin_y), (dim_x, dim_y)], fill=0)
    # Bottom-left
    draw.rectangle([(0, dim_y - margin_y), (margin_x, dim_y)], fill=0)

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        mask.save(output_path)

    return mask


def image_masking_from_dimensions(
    output_mask_folder,
    dataset_name,
    width,
    height,
    mask_size_x=12,
    mask_size_y=12,
    unit="percent",
):
    """Create a mask from manually provided image dimensions."""
    output_path = Path(output_mask_folder) / f"{dataset_name}_mask.png"

    print(" ")
    print("=====================================================================")
    print("=            GAPPS TOOL 5 — CREATE A SINGLE IMAGE MASK              =")
    print("=====================================================================")
    print(" ")
    print(f"Width  = {int(width)} pixels")
    print(f"Height = {int(height)} pixels")
    print(f"Corner mask size X = {mask_size_x} {unit}")
    print(f"Corner mask size Y = {mask_size_y} {unit}")
    print(" ")

    create_corner_mask(width, height, mask_size_x, mask_size_y, unit=unit, output_path=output_path)

    sleep(1)
    print(" ")
    print("======================")
    print(" PROCESSING COMPLETED ")
    print("======================")
    print(f"Mask saved to: {output_path}")

    return output_path


def image_masking_from_reference_image(
    reference_image_path,
    output_mask_folder,
    dataset_name,
    mask_size_x=12,
    mask_size_y=12,
    unit="percent",
):
    """Create a mask using dimensions read from one reference image."""
    width, height = read_image_dimensions(reference_image_path)
    return image_masking_from_dimensions(
        output_mask_folder,
        dataset_name,
        width,
        height,
        mask_size_x=mask_size_x,
        mask_size_y=mask_size_y,
        unit=unit,
    )


def image_masking(
    input_image_folder,
    output_mask_folder,
    dataset_name,
    percent_mask_size_X=12,
    percent_mask_size_Y=12,
    image_format="*.tif",
):
    """
    Backwards-compatible folder-based mask creation.

    The former workflow scanned all images in a folder and used the maximum image
    width and height found in the dataset. This behaviour is preserved here.
    """
    print(" ")
    print("=====================================================================")
    print("=            GAPPS TOOL 5 — CREATE A SINGLE IMAGE MASK              =")
    print("=====================================================================")
    print(" ")

    input_image_folder = Path(input_image_folder)
    if not input_image_folder.is_dir():
        raise NotADirectoryError(f"Input image folder does not exist: {input_image_folder}")

    images_list = sorted(glob.glob(str(input_image_folder / image_format)))
    if not images_list:
        raise FileNotFoundError(f"No image found in {input_image_folder} with pattern {image_format}")

    print("Number of images in dataset: " + str(len(images_list)))
    print(" ")

    sizes = []
    for image_path in images_list:
        with Image.open(image_path) as img:
            sizes.append(img.size)

    sizes_array = np.asarray(sizes)
    widths = sizes_array[:, 0]
    heights = sizes_array[:, 1]
    width_max = int(max(widths))
    height_max = int(max(heights))
    width_min = int(min(widths))
    height_min = int(min(heights))

    print("Width found = " + str(width_max) + " pixels")
    print("Height found = " + str(height_max) + " pixels")
    print(" ")
    print("Double check --> minimum width = " + str(width_min) + " pixels (must be similar)")
    print("Double check --> minimum height = " + str(height_min) + " pixels (must be similar)")
    print(" ")

    output_path = Path(output_mask_folder) / f"{dataset_name}_mask.png"
    create_corner_mask(
        width_max,
        height_max,
        percent_mask_size_X,
        percent_mask_size_Y,
        unit="percent",
        output_path=output_path,
    )

    sleep(1)
    print(" ")
    print("======================")
    print(" PROCESSING COMPLETED ")
    print("======================")
    print(f"Mask saved to: {output_path}")

    return output_path


if __name__ == "__main__":
    # Example direct execution. Adapt paths if this module is used standalone.
    input_image_folder = r"/path/to/input/images"
    output_mask_folder = r"/path/to/output/folder"
    dataset_name = "TestSingleMask"
    image_masking(input_image_folder, output_mask_folder, dataset_name, 12, 12, image_format="*.tif")
