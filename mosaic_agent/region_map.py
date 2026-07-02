from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.color import deltaE_ciede2000, rgb2lab

from mosaic_agent.models import PaletteDB, Tile
from mosaic_agent.palette import validate_tile_ids


HEX_RGB_PATTERN = re.compile(r"^#?([0-9a-fA-F]{6})$")


@dataclass(frozen=True)
class PaletteArrays:
    tiles: tuple[Tile, ...]
    rgb: np.ndarray
    lab: np.ndarray


@dataclass(frozen=True)
class NormalizedSource:
    rgb: np.ndarray
    original_size: tuple[int, int]
    working_size: tuple[int, int]
    scale: float


def parse_hex_rgb(value: str) -> tuple[int, int, int]:
    match = HEX_RGB_PATTERN.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"tile hex must be a six-digit RGB value: {value!r}")
    digits = match.group(1)
    return tuple(int(digits[index : index + 2], 16) for index in (0, 2, 4))


def build_palette_arrays(palette: PaletteDB, selected_ids: list[str]) -> PaletteArrays:
    validate_tile_ids(selected_ids, palette)
    selected = set(selected_ids)
    tiles = tuple(
        sorted(
            (tile for tile in palette.tiles if not selected or tile.tile_id in selected),
            key=lambda tile: tile.tile_id,
        )
    )
    if not tiles:
        raise ValueError("select at least one palette color")
    rgb = np.asarray([parse_hex_rgb(tile.hex) for tile in tiles], dtype=np.uint8)
    return PaletteArrays(tiles=tiles, rgb=rgb, lab=rgb_to_lab(rgb))


def load_source_rgb(
    path: str | Path,
    max_working_size: int = 1400,
) -> NormalizedSource:
    if max_working_size < 1:
        raise ValueError("max working size must be positive")
    with Image.open(path) as source_image:
        source = source_image.convert("RGB")
        original_size = source.size
        longest_side = max(original_size)
        scale = min(1.0, max_working_size / longest_side)
        if scale < 1.0:
            working_size = (
                max(1, round(original_size[0] * scale)),
                max(1, round(original_size[1] * scale)),
            )
            source = source.resize(working_size, Image.Resampling.LANCZOS)
        else:
            working_size = original_size
        rgb = np.asarray(source, dtype=np.uint8).copy()
    return NormalizedSource(
        rgb=rgb,
        original_size=original_size,
        working_size=working_size,
        scale=scale,
    )


def load_work_area(
    path: str | Path | None,
    size: tuple[int, int],
) -> np.ndarray:
    width, height = size
    if width < 1 or height < 1:
        raise ValueError("work area dimensions must be positive")
    if path is None:
        return np.ones((height, width), dtype=bool)

    with Image.open(path) as source:
        source.load()
        has_alpha = "A" in source.getbands()
        meaningful_alpha = has_alpha and source.getchannel("A").getextrema() != (255, 255)
        resized = source.resize(size, Image.Resampling.NEAREST)
        if meaningful_alpha:
            values = np.asarray(resized.getchannel("A"), dtype=np.uint8)
            return values < 128
        values = np.asarray(resized.convert("L"), dtype=np.uint8)
        return values >= 128


def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    values = np.asarray(rgb)
    if values.shape[-1] != 3:
        raise ValueError("RGB input must have exactly three channels")
    normalized = values.astype(np.float64)
    if np.issubdtype(values.dtype, np.integer) or normalized.max(initial=0.0) > 1.0:
        normalized /= 255.0
    return np.asarray(rgb2lab(normalized, channel_axis=-1), dtype=np.float64)


def nearest_palette_indices(
    colors_lab: np.ndarray,
    palette_lab: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    colors = np.asarray(colors_lab, dtype=np.float64)
    palette = np.asarray(palette_lab, dtype=np.float64)
    if colors.ndim != 2 or colors.shape[1] != 3:
        raise ValueError("source Lab colors must have shape (N, 3)")
    if palette.ndim != 2 or palette.shape[1] != 3 or len(palette) == 0:
        raise ValueError("palette Lab colors must have shape (N, 3) and cannot be empty")

    distance_columns = [
        deltaE_ciede2000(colors, np.broadcast_to(tile_lab, colors.shape))
        for tile_lab in palette
    ]
    distances = np.column_stack(distance_columns)
    indices = np.argmin(distances, axis=1)
    nearest = distances[np.arange(len(colors)), indices]
    return indices.astype(np.int32), nearest.astype(np.float64)
