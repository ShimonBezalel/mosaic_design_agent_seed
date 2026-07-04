from __future__ import annotations

from typing import Literal

import numpy as np

from mosaic_agent.tile_map_models import PhysicalScale, PhysicalScaleBasis


ScaleAxis = Literal["x", "y", "mean"]


def build_physical_scale(
    image_size: tuple[int, int],
    work_mask: np.ndarray,
    physical_width_mm: float,
    physical_height_mm: float,
    scale_basis: PhysicalScaleBasis,
) -> PhysicalScale:
    width, height = image_size
    work = np.asarray(work_mask, dtype=bool)
    if width < 1 or height < 1 or work.shape != (height, width):
        raise ValueError("image dimensions and work mask must match and be positive")
    if physical_width_mm <= 0 or physical_height_mm <= 0:
        raise ValueError("positive physical dimensions are required")

    if scale_basis == "mask_bbox":
        ys, xs = np.nonzero(work)
        if len(xs) == 0:
            raise ValueError("mask has no work pixels for physical scale")
        scale_width_px = int(xs.max()) - int(xs.min()) + 1
        scale_height_px = int(ys.max()) - int(ys.min()) + 1
    else:
        scale_width_px = width
        scale_height_px = height

    mm_per_px_x = physical_width_mm / scale_width_px
    mm_per_px_y = physical_height_mm / scale_height_px
    return PhysicalScale(
        image_width_px=width,
        image_height_px=height,
        physical_width_mm=physical_width_mm,
        physical_height_mm=physical_height_mm,
        mm_per_px_x=mm_per_px_x,
        mm_per_px_y=mm_per_px_y,
        px_per_mm_x=1.0 / mm_per_px_x,
        px_per_mm_y=1.0 / mm_per_px_y,
        scale_basis=scale_basis,
    )


def length_mm_to_px(scale: PhysicalScale, length_mm: float, *, axis: ScaleAxis) -> float:
    if length_mm < 0:
        raise ValueError("length cannot be negative")
    if axis == "x":
        factor = scale.px_per_mm_x
    elif axis == "y":
        factor = scale.px_per_mm_y
    else:
        factor = (scale.px_per_mm_x * scale.px_per_mm_y) ** 0.5
    return length_mm * factor


def area_mm2_to_px(scale: PhysicalScale, area_mm2: float) -> float:
    if area_mm2 < 0:
        raise ValueError("area cannot be negative")
    return area_mm2 / (scale.mm_per_px_x * scale.mm_per_px_y)


def area_px_to_mm2(scale: PhysicalScale, area_px: float) -> float:
    if area_px < 0:
        raise ValueError("area cannot be negative")
    return area_px * scale.mm_per_px_x * scale.mm_per_px_y
