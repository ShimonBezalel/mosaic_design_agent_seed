from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.color import deltaE_ciede2000, rgb2lab
from skimage.filters import gaussian
from skimage.measure import label
from skimage.segmentation import slic

from mosaic_agent.models import PaletteDB, Tile
from mosaic_agent.palette import validate_tile_ids
from mosaic_agent.tile_map_models import BoundarySmoothing, Granularity, RegionRecord


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


@dataclass(frozen=True)
class InitialTileMap:
    segment_labels: np.ndarray
    tile_indices: np.ndarray
    segment_delta_e: dict[int, float]
    fallback_used: bool
    target_count: int


@dataclass(frozen=True)
class CleanupResult:
    tile_indices: np.ndarray
    region_ids: np.ndarray
    warnings: tuple[str, ...]
    iterations: int

    @property
    def region_count(self) -> int:
        return int(self.region_ids.max(initial=0))


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
        resized = source.resize(size, Image.Resampling.NEAREST)
        if has_alpha:
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


def derive_segment_target(
    granularity: Granularity,
    area_px: int,
    target_region_count: int | None = None,
) -> int:
    if area_px < 1:
        raise ValueError("mask has no editable pixels")
    if target_region_count is not None:
        requested = target_region_count
    else:
        base = {"coarse": 120, "medium": 300, "fine": 650}[granularity]
        requested = round(base * np.sqrt(area_px / 1_000_000))
    bounded = max(20, min(1200, int(requested)))
    return min(area_px, bounded)


def smooth_source_lab(
    source_rgb: np.ndarray,
    mode: BoundarySmoothing,
) -> np.ndarray:
    sigma = {"none": 0.0, "light": 0.8, "medium": 1.5}[mode]
    if sigma == 0:
        values = np.asarray(source_rgb)
    else:
        values = gaussian(
            np.asarray(source_rgb),
            sigma=sigma,
            channel_axis=-1,
            preserve_range=True,
        )
    return rgb_to_lab(values)


def segment_work_area(
    source_lab: np.ndarray,
    work_mask: np.ndarray,
    target_count: int,
    compactness: float = 5.0,
) -> tuple[np.ndarray, bool]:
    if compactness <= 0:
        raise ValueError("SLIC compactness must be positive")
    try:
        labels = slic(
            source_lab,
            n_segments=target_count,
            compactness=compactness,
            start_label=1,
            mask=work_mask,
            convert2lab=False,
            channel_axis=-1,
            enforce_connectivity=True,
            sigma=0,
        ).astype(np.int32)
        if not np.any(labels[work_mask] > 0):
            raise ValueError("SLIC produced no labels inside the mask")
        labels[~work_mask] = 0
        return labels, False
    except (ValueError, RuntimeError, FloatingPointError):
        return _grid_segment(work_mask, target_count), True


def create_initial_tile_map(
    source_rgb: np.ndarray,
    work_mask: np.ndarray,
    palette: PaletteArrays,
    *,
    granularity: Granularity,
    target_region_count: int | None = None,
    boundary_smoothing: BoundarySmoothing = "light",
    compactness: float = 5.0,
) -> InitialTileMap:
    source = np.asarray(source_rgb)
    work = np.asarray(work_mask, dtype=bool)
    if source.shape[:2] != work.shape or source.shape[-1] != 3:
        raise ValueError("source image and work mask dimensions must match")
    work_count = int(work.sum())
    target = derive_segment_target(granularity, work_count, target_region_count)
    source_lab = smooth_source_lab(source, boundary_smoothing)
    segment_labels, fallback_used = segment_work_area(
        source_lab,
        work,
        target,
        compactness=compactness,
    )
    tile_indices = np.full(work.shape, -1, dtype=np.int32)
    segment_delta_e: dict[int, float] = {}

    segment_ids = np.unique(segment_labels[work])
    means = np.asarray(
        [source_lab[segment_labels == segment_id].mean(axis=0) for segment_id in segment_ids]
    )
    assigned, distances = nearest_palette_indices(means, palette.lab)
    for segment_id, tile_index, distance in zip(segment_ids, assigned, distances, strict=True):
        tile_indices[segment_labels == segment_id] = int(tile_index)
        segment_delta_e[int(segment_id)] = float(distance)

    return InitialTileMap(
        segment_labels=segment_labels,
        tile_indices=tile_indices,
        segment_delta_e=segment_delta_e,
        fallback_used=fallback_used,
        target_count=target,
    )


def label_tile_components(tile_indices: np.ndarray, work_mask: np.ndarray) -> np.ndarray:
    tiles = np.asarray(tile_indices, dtype=np.int32)
    work = np.asarray(work_mask, dtype=bool)
    if tiles.shape != work.shape:
        raise ValueError("tile map and work mask dimensions must match")

    components: list[tuple[tuple[float | int | str, ...], np.ndarray]] = []
    for tile_index in sorted(int(value) for value in np.unique(tiles[work])):
        if tile_index < 0:
            continue
        tile_components = label((tiles == tile_index) & work, connectivity=1)
        for component_id in range(1, int(tile_components.max(initial=0)) + 1):
            component = tile_components == component_id
            ys, xs = np.nonzero(component)
            if len(xs) == 0:
                continue
            key = (
                int(ys.min()),
                int(xs.min()),
                float(ys.mean()),
                float(xs.mean()),
                tile_index,
            )
            components.append((key, component))

    region_ids = np.zeros(work.shape, dtype=np.int32)
    for region_id, (_, component) in enumerate(sorted(components, key=lambda item: item[0]), start=1):
        region_ids[component] = region_id
    return region_ids


def merge_tiny_tile_regions(
    tile_indices: np.ndarray,
    work_mask: np.ndarray,
    source_lab: np.ndarray,
    palette_lab: np.ndarray,
    min_region_area_px: int,
) -> CleanupResult:
    if min_region_area_px < 1:
        raise ValueError("minimum region area must be positive")
    tiles = np.asarray(tile_indices, dtype=np.int32).copy()
    work = np.asarray(work_mask, dtype=bool)
    lab_values = np.asarray(source_lab, dtype=np.float64)
    palette_values = np.asarray(palette_lab, dtype=np.float64)
    if tiles.shape != work.shape or lab_values.shape[:2] != work.shape:
        raise ValueError("tile map, source Lab image, and work mask dimensions must match")
    tiles[~work] = -1
    warnings: list[str] = []
    iterations = 0

    for pass_index in range(1, 101):
        region_ids = label_tile_components(tiles, work)
        stats = _region_stats(region_ids, tiles, lab_values)
        tiny_ids = sorted(
            (region_id for region_id, stat in stats.items() if stat["area"] < min_region_area_px),
            key=lambda region_id: (stats[region_id]["area"], region_id),
        )
        if not tiny_ids:
            break
        shared = _shared_boundaries(region_ids)
        merged_any = False

        for region_id in tiny_ids:
            region_pixels = region_ids == region_id
            if not np.any(region_pixels):
                continue
            neighbor_ids = sorted(
                other
                for pair in shared
                if region_id in pair
                for other in pair
                if other != region_id
            )
            if not neighbor_ids:
                warning = f"Region {region_id} is below the minimum area but has no adjacent region."
                if warning not in warnings:
                    warnings.append(warning)
                continue

            source_mean = lab_values[region_pixels].mean(axis=0)
            candidates: list[tuple[tuple[float | int, ...], int]] = []
            for neighbor_id in neighbor_ids:
                neighbor_pixels = region_ids == neighbor_id
                current_neighbor_tiles = tiles[neighbor_pixels]
                current_neighbor_tiles = current_neighbor_tiles[current_neighbor_tiles >= 0]
                if len(current_neighbor_tiles) == 0:
                    continue
                counts = np.bincount(current_neighbor_tiles, minlength=len(palette_values))
                neighbor_tile = int(np.argmax(counts))
                penalty = float(
                    deltaE_ciede2000(
                        source_mean[np.newaxis, :],
                        palette_values[neighbor_tile][np.newaxis, :],
                    )[0]
                )
                pair = tuple(sorted((region_id, neighbor_id)))
                key = (
                    penalty,
                    -shared[pair],
                    -int(stats[neighbor_id]["area"]),
                    neighbor_id,
                )
                candidates.append((key, neighbor_tile))
            if not candidates:
                continue
            _, replacement_tile = min(candidates, key=lambda item: item[0])
            if not np.all(tiles[region_pixels] == replacement_tile):
                tiles[region_pixels] = replacement_tile
                merged_any = True

        iterations = pass_index
        if not merged_any:
            break

    final_regions = label_tile_components(tiles, work)
    if iterations == 100:
        warnings.append("Tiny-region cleanup reached its 100-pass safety limit.")
    return CleanupResult(
        tile_indices=tiles,
        region_ids=final_regions,
        warnings=tuple(warnings),
        iterations=iterations,
    )


def build_region_records(
    region_map: np.ndarray,
    tile_indices: np.ndarray,
    source_rgb: np.ndarray,
    source_lab: np.ndarray,
    palette: PaletteArrays,
    pixel_area_cm2: float | None,
) -> list[RegionRecord]:
    regions = np.asarray(region_map, dtype=np.int32)
    tiles = np.asarray(tile_indices, dtype=np.int32)
    rgb = np.asarray(source_rgb, dtype=np.float64)
    lab_values = np.asarray(source_lab, dtype=np.float64)
    shared = _shared_boundaries(regions)
    neighbors: dict[int, set[int]] = {
        region_id: set() for region_id in range(1, int(regions.max(initial=0)) + 1)
    }
    for first, second in shared:
        neighbors[first].add(second)
        neighbors[second].add(first)

    records: list[RegionRecord] = []
    for region_id in range(1, int(regions.max(initial=0)) + 1):
        pixels = regions == region_id
        ys, xs = np.nonzero(pixels)
        if len(xs) == 0:
            continue
        region_tiles = tiles[pixels]
        tile_index = int(np.bincount(region_tiles, minlength=len(palette.tiles)).argmax())
        mean_rgb = rgb[pixels].mean(axis=0)
        mean_lab = lab_values[pixels].mean(axis=0)
        delta_e = float(
            deltaE_ciede2000(
                mean_lab[np.newaxis, :],
                palette.lab[tile_index][np.newaxis, :],
            )[0]
        )
        pixel_count = int(len(xs))
        records.append(
            RegionRecord(
                region_id=region_id,
                tile_id=palette.tiles[tile_index].tile_id,
                pixel_count=pixel_count,
                estimated_area_cm2=(
                    pixel_count * pixel_area_cm2 if pixel_area_cm2 is not None else None
                ),
                bbox_xyxy=(
                    int(xs.min()),
                    int(ys.min()),
                    int(xs.max()) + 1,
                    int(ys.max()) + 1,
                ),
                centroid_xy=(float(xs.mean()), float(ys.mean())),
                mean_source_rgb=tuple(float(value) for value in mean_rgb),
                mean_source_lab=tuple(float(value) for value in mean_lab),
                delta_e=delta_e,
                neighbor_region_ids=sorted(neighbors[region_id]),
            )
        )
    return records


def _grid_segment(work_mask: np.ndarray, target_count: int) -> np.ndarray:
    height, width = work_mask.shape
    aspect = width / max(height, 1)
    columns = max(1, round(np.sqrt(target_count * aspect)))
    rows = max(1, int(np.ceil(target_count / columns)))
    y_bins = np.minimum((np.arange(height) * rows) // height, rows - 1)
    x_bins = np.minimum((np.arange(width) * columns) // width, columns - 1)
    labels = y_bins[:, None] * columns + x_bins[None, :] + 1
    return np.where(work_mask, labels, 0).astype(np.int32)


def _region_stats(
    region_ids: np.ndarray,
    tile_indices: np.ndarray,
    source_lab: np.ndarray,
) -> dict[int, dict[str, object]]:
    stats: dict[int, dict[str, object]] = {}
    for region_id in range(1, int(region_ids.max(initial=0)) + 1):
        pixels = region_ids == region_id
        if not np.any(pixels):
            continue
        region_tiles = tile_indices[pixels]
        stats[region_id] = {
            "area": int(pixels.sum()),
            "tile_index": int(np.bincount(region_tiles[region_tiles >= 0]).argmax()),
            "mean_lab": source_lab[pixels].mean(axis=0),
        }
    return stats


def _shared_boundaries(region_ids: np.ndarray) -> dict[tuple[int, int], int]:
    shared: dict[tuple[int, int], int] = {}
    for first_values, second_values in (
        (region_ids[:, :-1], region_ids[:, 1:]),
        (region_ids[:-1, :], region_ids[1:, :]),
    ):
        valid = (first_values > 0) & (second_values > 0) & (first_values != second_values)
        for first, second in zip(first_values[valid], second_values[valid], strict=True):
            pair = tuple(sorted((int(first), int(second))))
            shared[pair] = shared.get(pair, 0) + 1
    return shared
