from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree
from skimage.measure import find_contours, label

from mosaic_agent.flow_field import (
    FLOW_WEIGHTS,
    FlowField,
    blend_axial_orientations,
    compute_gradient_orientation_field,
    dominant_orientation_for_mask,
    pca_orientation_for_mask,
    resolve_region_orientation,
)
from mosaic_agent.tile_map_models import (
    PhysicalScale,
    ShapeStyle,
    TesseraCompileOptions,
    TesseraRecord,
)


STYLE_ASPECT_MULTIPLIER: dict[ShapeStyle, float] = {
    "irregular": 1.0,
    "angular": 1.0,
    "smooth": 0.9,
    "slivered": 1.6,
}


@dataclass(frozen=True)
class TesseraContext:
    source_rgb: np.ndarray
    work_mask: np.ndarray
    tile_indices: np.ndarray
    region_ids: np.ndarray
    physical_scale: PhysicalScale
    palette_tile_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        source = np.asarray(self.source_rgb)
        work = np.asarray(self.work_mask, dtype=bool)
        tiles = np.asarray(self.tile_indices)
        regions = np.asarray(self.region_ids)
        expected = (self.physical_scale.image_height_px, self.physical_scale.image_width_px)
        if source.shape != (*expected, 3):
            raise ValueError("source image and physical scale dimensions must match")
        if work.shape != expected or tiles.shape != expected or regions.shape != expected:
            raise ValueError("tessera context maps must share physical scale dimensions")
        if not np.any(work):
            raise ValueError("tessera work mask has no pixels")
        if np.any(regions[work] < 1) or np.any(regions[~work] != 0):
            raise ValueError("parent region IDs must be positive only inside the work mask")
        if np.any(tiles[work] < 0):
            raise ValueError("tile indices must be nonnegative inside the work mask")
        if int(tiles[work].max(initial=-1)) >= len(self.palette_tile_ids):
            raise ValueError("tile index is outside palette tile IDs")
        for region_id in np.unique(regions[work]):
            if len(np.unique(tiles[regions == region_id])) != 1:
                raise ValueError(f"parent region {region_id} contains multiple palette tiles")


@dataclass(frozen=True)
class TesseraSeed:
    seed_index: int
    parent_region_id: int
    x_px: int
    y_px: int
    x_mm: float
    y_mm: float
    orientation_radians: float
    aspect_ratio: float
    short_radius_mm: float
    long_radius_mm: float


@dataclass(frozen=True)
class TesseraSubdivision:
    work_mask: np.ndarray
    tessera_ids: np.ndarray
    parent_region_map: np.ndarray
    tile_index_map: np.ndarray
    seeds: tuple[TesseraSeed, ...]
    records: tuple[TesseraRecord, ...]
    warnings: tuple[str, ...]
    outside_mask_pixel_count: int
    crosses_region_boundary_count: int
    deterministic_signature: str


def generate_tessera_seeds(
    context: TesseraContext,
    options: TesseraCompileOptions,
) -> tuple[TesseraSeed, ...]:
    desired = _desired_seed_counts(context, options)
    requested_total = sum(desired.values())
    if requested_total > options.max_tessera_count:
        raise ValueError(
            f"requested {requested_total} tesserae exceeds max_tessera_count="
            f"{options.max_tessera_count}; increase physical target size or the explicit cap"
        )
    for region_id, count in desired.items():
        available_pixels = int(np.count_nonzero(context.region_ids == region_id))
        if count > available_pixels:
            raise ValueError(
                f"parent region {region_id} needs {count} tesserae but has only "
                f"{available_pixels} working pixels; use a higher-resolution source or increase "
                "the physical target size"
            )

    field = compute_gradient_orientation_field(context.source_rgb)
    seeds: list[TesseraSeed] = []
    for region_id in sorted(desired):
        region_mask = context.region_ids == region_id
        count = desired[region_id]
        base_orientation = resolve_region_orientation(
            field,
            region_mask,
            context.physical_scale,
            options.flow_strength,
        )
        positions = _seed_positions_for_region(
            context,
            region_mask,
            region_id,
            count,
            base_orientation,
            options,
        )
        region_flow, region_confidence = dominant_orientation_for_mask(field, region_mask)
        for x_px, y_px in positions:
            orientation = _seed_orientation(
                field,
                x_px,
                y_px,
                base_orientation,
                region_flow,
                region_confidence,
                options,
            )
            aspect_ratio, size_factor = _seed_shape(
                region_id,
                x_px,
                y_px,
                options,
            )
            short_radius = max(
                options.min_short_edge_mm / 2.0,
                options.target_short_edge_mm * size_factor / 2.0,
            )
            long_radius = min(
                options.max_long_edge_mm / 2.0,
                short_radius * aspect_ratio,
            )
            aspect_ratio = max(1.0, long_radius / short_radius)
            seeds.append(
                TesseraSeed(
                    seed_index=len(seeds),
                    parent_region_id=region_id,
                    x_px=x_px,
                    y_px=y_px,
                    x_mm=(x_px + 0.5) * context.physical_scale.mm_per_px_x,
                    y_mm=(y_px + 0.5) * context.physical_scale.mm_per_px_y,
                    orientation_radians=orientation,
                    aspect_ratio=aspect_ratio,
                    short_radius_mm=short_radius,
                    long_radius_mm=long_radius,
                )
            )
    return tuple(seeds)


def subdivide_tesserae(
    context: TesseraContext,
    options: TesseraCompileOptions,
) -> TesseraSubdivision:
    seeds = generate_tessera_seeds(context, options)
    raw_ids = _assign_pixels_to_seeds(context, seeds)
    pixel_area_mm2 = (
        context.physical_scale.mm_per_px_x * context.physical_scale.mm_per_px_y
    )
    min_fragment_area = max(
        pixel_area_mm2 * 1.01,
        options.min_short_edge_mm**2 * 0.15,
    )
    tessera_ids, cleanup_warnings = cleanup_tessera_fragments(
        raw_ids,
        context.region_ids,
        context.physical_scale,
        min_fragment_area_mm2=min_fragment_area,
    )
    records = _build_tessera_records(context, tessera_ids, options)
    parent_map = np.zeros(context.region_ids.shape, dtype=np.int32)
    for record in records:
        parent_map[tessera_ids == record.tessera_id] = record.parent_region_id
    tile_map = np.full(context.tile_indices.shape, -1, dtype=np.int32)
    tile_map[context.work_mask] = context.tile_indices[context.work_mask]
    outside_count = int(np.count_nonzero((tessera_ids > 0) & ~context.work_mask))
    crossing_count = _count_region_crossings(tessera_ids, context.region_ids)
    signature = _subdivision_signature(
        tessera_ids,
        parent_map,
        tile_map,
        seeds,
        options,
    )
    warnings = tuple(dict.fromkeys(cleanup_warnings))
    return TesseraSubdivision(
        work_mask=context.work_mask.copy(),
        tessera_ids=tessera_ids,
        parent_region_map=parent_map,
        tile_index_map=tile_map,
        seeds=seeds,
        records=records,
        warnings=warnings,
        outside_mask_pixel_count=outside_count,
        crosses_region_boundary_count=crossing_count,
        deterministic_signature=signature,
    )


def cleanup_tessera_fragments(
    tessera_ids: np.ndarray,
    parent_region_ids: np.ndarray,
    scale: PhysicalScale,
    *,
    min_fragment_area_mm2: float,
) -> tuple[np.ndarray, tuple[str, ...]]:
    raw = np.asarray(tessera_ids, dtype=np.int32)
    parents = np.asarray(parent_region_ids, dtype=np.int32)
    expected = (scale.image_height_px, scale.image_width_px)
    if raw.shape != expected or parents.shape != expected:
        raise ValueError("tessera, parent, and physical scale dimensions must match")
    if min_fragment_area_mm2 < 0:
        raise ValueError("minimum fragment area cannot be negative")

    pieces = _split_connected_components(raw, parents)
    pixel_area = scale.mm_per_px_x * scale.mm_per_px_y
    warnings: list[str] = []
    for _ in range(max(1, int(pieces.max(initial=0)))):
        areas = {
            piece_id: int(np.count_nonzero(pieces == piece_id)) * pixel_area
            for piece_id in np.unique(pieces)
            if piece_id > 0
        }
        tiny = sorted(
            (piece_id for piece_id, area in areas.items() if area < min_fragment_area_mm2),
            key=lambda piece_id: (areas[piece_id], piece_id),
        )
        if not tiny:
            break
        merged_any = False
        for piece_id in tiny:
            pixels = pieces == piece_id
            if not np.any(pixels):
                continue
            parent_values = parents[pixels]
            parent_id = int(np.bincount(parent_values[parent_values > 0]).argmax())
            shared = _neighbor_shared_edges(pieces, pixels, parents == parent_id)
            if not shared:
                warnings.append(
                    f"Tiny tessera fragment {piece_id} could not be merged because it has no "
                    "adjacent tessera in its parent region."
                )
                continue
            replacement = min(
                shared,
                key=lambda neighbor: (-shared[neighbor], -areas.get(neighbor, 0.0), neighbor),
            )
            pieces[pixels] = replacement
            warnings.append(
                f"Merged tiny tessera fragment {piece_id} into adjacent tessera {replacement}."
            )
            merged_any = True
        if not merged_any:
            break
    return _stable_renumber(pieces, parents), tuple(warnings)


def _desired_seed_counts(
    context: TesseraContext,
    options: TesseraCompileOptions,
) -> dict[int, int]:
    pixel_area = context.physical_scale.mm_per_px_x * context.physical_scale.mm_per_px_y
    target_area = options.target_short_edge_mm**2 * options.preferred_aspect_ratio
    desired: dict[int, int] = {}
    for region_id in sorted(int(value) for value in np.unique(context.region_ids[context.work_mask])):
        pixel_count = int(np.count_nonzero(context.region_ids == region_id))
        count = max(1, int(round(pixel_count * pixel_area / target_area)))
        desired[region_id] = count
    return desired


def _seed_positions_for_region(
    context: TesseraContext,
    region_mask: np.ndarray,
    region_id: int,
    desired_count: int,
    orientation: float,
    options: TesseraCompileOptions,
) -> list[tuple[int, int]]:
    ys, xs = np.nonzero(region_mask)
    x_mm = (xs.astype(np.float64) + 0.5) * context.physical_scale.mm_per_px_x
    y_mm = (ys.astype(np.float64) + 0.5) * context.physical_scale.mm_per_px_y
    cosine = np.cos(orientation)
    sine = np.sin(orientation)
    along = x_mm * cosine + y_mm * sine
    across = -x_mm * sine + y_mm * cosine

    target_area = options.target_short_edge_mm**2 * options.preferred_aspect_ratio
    lattice_aspect = np.clip(
        options.preferred_aspect_ratio * STYLE_ASPECT_MULTIPLIER[options.shape_style],
        1.0,
        options.max_aspect_ratio,
    )
    along_spacing = np.sqrt(target_area * lattice_aspect)
    across_spacing = np.sqrt(target_area / lattice_aspect)
    candidates: set[tuple[int, int]] = set()
    along_start = np.floor(along.min() / along_spacing) - 1
    along_stop = np.ceil(along.max() / along_spacing) + 1
    across_start = np.floor(across.min() / across_spacing) - 1
    across_stop = np.ceil(across.max() / across_spacing) + 1
    for along_index in range(int(along_start), int(along_stop) + 1):
        for across_index in range(int(across_start), int(across_stop) + 1):
            jitter_along = (
                _hash_unit(options.random_seed, region_id, along_index, across_index, "u") - 0.5
            ) * along_spacing * 0.5
            jitter_across = (
                _hash_unit(options.random_seed, region_id, along_index, across_index, "v") - 0.5
            ) * across_spacing * 0.5
            candidate_along = (along_index + 0.5) * along_spacing + jitter_along
            candidate_across = (across_index + 0.5) * across_spacing + jitter_across
            candidate_x_mm = candidate_along * cosine - candidate_across * sine
            candidate_y_mm = candidate_along * sine + candidate_across * cosine
            x_px = int(np.floor(candidate_x_mm / context.physical_scale.mm_per_px_x))
            y_px = int(np.floor(candidate_y_mm / context.physical_scale.mm_per_px_y))
            if (
                0 <= y_px < region_mask.shape[0]
                and 0 <= x_px < region_mask.shape[1]
                and region_mask[y_px, x_px]
            ):
                candidates.add((x_px, y_px))

    ordered_candidates = sorted(
        candidates,
        key=lambda point: (
            _hash_unit(options.random_seed, region_id, point[0], point[1], "rank"),
            point[1],
            point[0],
        ),
    )
    if len(ordered_candidates) >= desired_count:
        return sorted(ordered_candidates[:desired_count], key=lambda point: (point[1], point[0]))

    positions = list(ordered_candidates)
    used = set(positions)
    projection_order = np.argsort(along, kind="stable")
    support_indices = np.linspace(0, len(projection_order) - 1, desired_count, dtype=int)
    for support_index in support_indices:
        pixel_index = int(projection_order[support_index])
        point = (int(xs[pixel_index]), int(ys[pixel_index]))
        if point not in used:
            positions.append(point)
            used.add(point)
        if len(positions) == desired_count:
            break

    valid_points = np.column_stack((xs, ys)).astype(np.int32)
    while len(positions) < desired_count:
        selected_mm = np.asarray(
            [
                (
                    (x + 0.5) * context.physical_scale.mm_per_px_x,
                    (y + 0.5) * context.physical_scale.mm_per_px_y,
                )
                for x, y in positions
            ],
            dtype=np.float64,
        )
        valid_mm = np.column_stack((x_mm, y_mm))
        if len(selected_mm) == 0:
            distances = (valid_mm - valid_mm.mean(axis=0)) ** 2
            scores = -distances.sum(axis=1)
        else:
            distances = ((valid_mm[:, np.newaxis, :] - selected_mm[np.newaxis, :, :]) ** 2).sum(
                axis=2
            )
            scores = distances.min(axis=1)
        for point in used:
            matches = (valid_points[:, 0] == point[0]) & (valid_points[:, 1] == point[1])
            scores[matches] = -np.inf
        best = int(np.argmax(scores))
        point = (int(valid_points[best, 0]), int(valid_points[best, 1]))
        positions.append(point)
        used.add(point)
    return sorted(positions, key=lambda point: (point[1], point[0]))


def _seed_orientation(
    field: FlowField,
    x_px: int,
    y_px: int,
    base_orientation: float,
    region_flow: float,
    region_confidence: float,
    options: TesseraCompileOptions,
) -> float:
    local_confidence = float(field.confidence[y_px, x_px])
    if local_confidence > 0.05:
        flow_orientation = float(field.orientation_radians[y_px, x_px])
        confidence = local_confidence
    else:
        flow_orientation = region_flow
        confidence = region_confidence
    if options.edge_following == "low":
        confidence *= 0.7
    elif options.edge_following == "high":
        confidence = np.sqrt(confidence)
    weight = float(np.clip(FLOW_WEIGHTS[options.flow_strength] * confidence, 0.0, 1.0))
    orientation = blend_axial_orientations(base_orientation, flow_orientation, weight)
    if options.shape_style == "angular":
        orientation = np.radians(round(np.degrees(orientation) / 15.0) * 15.0)
    return float(np.mod(orientation, np.pi))


def _seed_shape(
    region_id: int,
    x_px: int,
    y_px: int,
    options: TesseraCompileOptions,
) -> tuple[float, float]:
    aspect_noise = _hash_unit(options.random_seed, region_id, x_px, y_px, "aspect") - 0.5
    size_noise = _hash_unit(options.random_seed, region_id, x_px, y_px, "size") - 0.5
    if options.shape_style == "smooth":
        aspect_variation = 1.0 + 0.10 * aspect_noise
        size_variation = 1.0 + 0.08 * size_noise
    elif options.shape_style == "slivered":
        aspect_variation = 1.6 + 0.35 * aspect_noise
        size_variation = 1.0 + 0.15 * size_noise
    elif options.shape_style == "angular":
        aspect_variation = 1.0 + 0.20 * aspect_noise
        size_variation = 1.0 + 0.20 * size_noise
    else:
        aspect_variation = 1.0 + 0.35 * aspect_noise
        size_variation = 1.0 + 0.30 * size_noise
    aspect = float(
        np.clip(
            options.preferred_aspect_ratio * aspect_variation,
            1.0,
            options.max_aspect_ratio,
        )
    )
    return aspect, float(max(0.5, size_variation))


def _assign_pixels_to_seeds(
    context: TesseraContext,
    seeds: tuple[TesseraSeed, ...],
) -> np.ndarray:
    assignment = np.zeros(context.region_ids.shape, dtype=np.int32)
    for region_id in sorted(int(value) for value in np.unique(context.region_ids[context.work_mask])):
        region_seed_indices = [
            index for index, seed in enumerate(seeds) if seed.parent_region_id == region_id
        ]
        region_seeds = [seeds[index] for index in region_seed_indices]
        ys, xs = np.nonzero(context.region_ids == region_id)
        points = np.column_stack(
            (
                (xs.astype(np.float64) + 0.5) * context.physical_scale.mm_per_px_x,
                (ys.astype(np.float64) + 0.5) * context.physical_scale.mm_per_px_y,
            )
        )
        seed_points = np.asarray([(seed.x_mm, seed.y_mm) for seed in region_seeds])
        candidate_count = min(12, len(region_seeds))
        _, candidates = cKDTree(seed_points).query(points, k=candidate_count)
        if candidate_count == 1:
            candidates = np.asarray(candidates)[:, np.newaxis]

        best_metric = np.full(len(points), np.inf)
        best_local_seed = np.full(len(points), np.iinfo(np.int32).max, dtype=np.int32)
        for column in range(candidate_count):
            local_indices = candidates[:, column].astype(np.int32)
            orientations = np.asarray(
                [region_seeds[index].orientation_radians for index in local_indices]
            )
            dx = points[:, 0] - seed_points[local_indices, 0]
            dy = points[:, 1] - seed_points[local_indices, 1]
            parallel = dx * np.cos(orientations) + dy * np.sin(orientations)
            perpendicular = -dx * np.sin(orientations) + dy * np.cos(orientations)
            long_radii = np.asarray(
                [region_seeds[index].long_radius_mm for index in local_indices]
            )
            short_radii = np.asarray(
                [region_seeds[index].short_radius_mm for index in local_indices]
            )
            metric = (parallel / long_radii) ** 2 + (perpendicular / short_radii) ** 2
            better = metric < best_metric - 1e-12
            ties = np.isclose(metric, best_metric, rtol=0, atol=1e-12) & (
                local_indices < best_local_seed
            )
            update = better | ties
            best_metric[update] = metric[update]
            best_local_seed[update] = local_indices[update]
        global_ids = np.asarray(region_seed_indices, dtype=np.int32)[best_local_seed] + 1
        assignment[ys, xs] = global_ids
    return assignment


def _split_connected_components(raw: np.ndarray, parents: np.ndarray) -> np.ndarray:
    pieces = np.zeros(raw.shape, dtype=np.int32)
    next_id = 1
    for parent_id in sorted(int(value) for value in np.unique(parents) if value > 0):
        for raw_id in sorted(int(value) for value in np.unique(raw[parents == parent_id]) if value > 0):
            components = label((raw == raw_id) & (parents == parent_id), connectivity=1)
            for component_id in range(1, int(components.max(initial=0)) + 1):
                pieces[components == component_id] = next_id
                next_id += 1
    return pieces


def _neighbor_shared_edges(
    pieces: np.ndarray,
    pixels: np.ndarray,
    same_parent: np.ndarray,
) -> dict[int, int]:
    shared: dict[int, int] = {}
    for y_shift, x_shift in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        shifted = np.roll(pieces, shift=(y_shift, x_shift), axis=(0, 1))
        shifted_same_parent = np.roll(
            same_parent,
            shift=(y_shift, x_shift),
            axis=(0, 1),
        )
        valid = pixels & same_parent & shifted_same_parent
        if y_shift == 1:
            valid[0, :] = False
        elif y_shift == -1:
            valid[-1, :] = False
        if x_shift == 1:
            valid[:, 0] = False
        elif x_shift == -1:
            valid[:, -1] = False
        values, counts = np.unique(shifted[valid], return_counts=True)
        for value, count in zip(values, counts, strict=True):
            if value > 0 and not np.any(pieces[pixels] == value):
                shared[int(value)] = shared.get(int(value), 0) + int(count)
    return shared


def _stable_renumber(pieces: np.ndarray, parents: np.ndarray) -> np.ndarray:
    ordered: list[tuple[tuple[float | int, ...], int]] = []
    for piece_id in np.unique(pieces):
        if piece_id <= 0:
            continue
        pixels = pieces == piece_id
        ys, xs = np.nonzero(pixels)
        parent_values = parents[pixels]
        parent_id = int(np.bincount(parent_values[parent_values > 0]).argmax())
        ordered.append(
            (
                (
                    parent_id,
                    int(ys.min()),
                    int(xs.min()),
                    float(ys.mean()),
                    float(xs.mean()),
                    int(piece_id),
                ),
                int(piece_id),
            )
        )
    result = np.zeros(pieces.shape, dtype=np.int32)
    for new_id, (_, old_id) in enumerate(sorted(ordered), start=1):
        result[pieces == old_id] = new_id
    return result


def _build_tessera_records(
    context: TesseraContext,
    tessera_ids: np.ndarray,
    options: TesseraCompileOptions,
) -> tuple[TesseraRecord, ...]:
    records: list[TesseraRecord] = []
    pixel_area = context.physical_scale.mm_per_px_x * context.physical_scale.mm_per_px_y
    for tessera_id in range(1, int(tessera_ids.max(initial=0)) + 1):
        pixels = tessera_ids == tessera_id
        ys, xs = np.nonzero(pixels)
        if len(xs) == 0:
            continue
        parent_values = context.region_ids[pixels]
        parent_id = int(np.bincount(parent_values[parent_values > 0]).argmax())
        tile_values = context.tile_indices[pixels]
        tile_index = int(np.bincount(tile_values[tile_values >= 0]).argmax())
        short_edge, long_edge, orientation, aspect = _piece_geometry(
            xs,
            ys,
            context.physical_scale,
        )
        warnings: list[str] = []
        if short_edge < options.min_short_edge_mm:
            warnings.append("Estimated short edge is below the requested minimum.")
        if long_edge > options.max_long_edge_mm:
            warnings.append("Estimated long edge exceeds the requested maximum.")
        if aspect > options.max_aspect_ratio:
            warnings.append("Estimated aspect ratio exceeds the requested maximum.")
        if len(xs) < 3:
            warnings.append("Piece is too small for stable raster geometry estimates.")
        records.append(
            TesseraRecord(
                tessera_id=tessera_id,
                parent_region_id=parent_id,
                tile_id=context.palette_tile_ids[tile_index],
                polygon_xy=_largest_contour_polygon(pixels),
                area_px=int(len(xs)),
                area_mm2=float(len(xs) * pixel_area),
                short_edge_mm_estimate=short_edge,
                long_edge_mm_estimate=long_edge,
                aspect_ratio=aspect,
                centroid_xy=(float(xs.mean()), float(ys.mean())),
                orientation_degrees=float(np.degrees(orientation) % 180.0),
                warnings=warnings,
            )
        )
    return tuple(records)


def _piece_geometry(
    xs: np.ndarray,
    ys: np.ndarray,
    scale: PhysicalScale,
) -> tuple[float, float, float, float]:
    points = np.column_stack(
        (
            (xs.astype(np.float64) + 0.5) * scale.mm_per_px_x,
            (ys.astype(np.float64) + 0.5) * scale.mm_per_px_y,
        )
    )
    centered = points - points.mean(axis=0)
    covariance = centered.T @ centered / len(points)
    covariance += np.diag((scale.mm_per_px_x**2 / 12.0, scale.mm_per_px_y**2 / 12.0))
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    eigenvalues = np.maximum(eigenvalues, 0.0)
    short_edge = float(np.sqrt(12.0 * eigenvalues[0]))
    long_edge = float(np.sqrt(12.0 * eigenvalues[-1]))
    aspect = max(1.0, long_edge / max(short_edge, np.finfo(np.float64).eps))
    major = eigenvectors[:, -1]
    orientation = float(np.mod(np.arctan2(major[1], major[0]), np.pi))
    return short_edge, long_edge, orientation, float(aspect)


def _largest_contour_polygon(mask: np.ndarray) -> list[tuple[float, float]]:
    padded = np.pad(mask.astype(np.uint8), 1)
    contours = find_contours(padded, 0.5)
    if not contours:
        ys, xs = np.nonzero(mask)
        x = float(xs[0])
        y = float(ys[0])
        return [(x, y), (x + 1.0, y), (x + 1.0, y + 1.0), (x, y + 1.0)]
    contour = max(contours, key=len)
    return [
        (float(point[1] - 1.0), float(point[0] - 1.0))
        for point in contour
    ]


def _count_region_crossings(tessera_ids: np.ndarray, region_ids: np.ndarray) -> int:
    crossings = 0
    for tessera_id in np.unique(tessera_ids):
        if tessera_id <= 0:
            continue
        parents = np.unique(region_ids[tessera_ids == tessera_id])
        parents = parents[parents > 0]
        if len(parents) > 1:
            crossings += 1
    return crossings


def _subdivision_signature(
    tessera_ids: np.ndarray,
    parent_map: np.ndarray,
    tile_map: np.ndarray,
    seeds: tuple[TesseraSeed, ...],
    options: TesseraCompileOptions,
) -> str:
    digest = hashlib.sha256()
    digest.update(np.asarray(tessera_ids, dtype="<i4").tobytes(order="C"))
    digest.update(np.asarray(parent_map, dtype="<i4").tobytes(order="C"))
    digest.update(np.asarray(tile_map, dtype="<i4").tobytes(order="C"))
    digest.update(
        json.dumps(
            [seed.__dict__ for seed in seeds],
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    digest.update(
        json.dumps(
            options.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    return digest.hexdigest()


def _hash_unit(*parts: object) -> float:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    value = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    return value / float(2**64)
