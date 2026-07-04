from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from mosaic_agent.physical_scale import build_physical_scale
from mosaic_agent.tessera import (
    TesseraContext,
    cleanup_tessera_fragments,
    generate_tessera_seeds,
    subdivide_tesserae,
)
from mosaic_agent.tile_map_models import TesseraCompileOptions


def make_context(
    *,
    height: int = 60,
    width: int = 90,
    region_ids: np.ndarray | None = None,
    tile_indices: np.ndarray | None = None,
    source_rgb: np.ndarray | None = None,
) -> TesseraContext:
    regions = (
        np.ones((height, width), dtype=np.int32)
        if region_ids is None
        else np.asarray(region_ids, dtype=np.int32)
    )
    work = regions > 0
    tiles = (
        np.zeros((height, width), dtype=np.int32)
        if tile_indices is None
        else np.asarray(tile_indices, dtype=np.int32)
    )
    source = (
        np.full((height, width, 3), 128, dtype=np.uint8)
        if source_rgb is None
        else np.asarray(source_rgb, dtype=np.uint8)
    )
    scale = build_physical_scale(
        (width, height),
        work,
        float(width),
        float(height),
        "full_image",
    )
    return TesseraContext(
        source_rgb=source,
        work_mask=work,
        tile_indices=tiles,
        region_ids=regions,
        physical_scale=scale,
        palette_tile_ids=("tile-a", "tile-b"),
    )


def options(**updates) -> TesseraCompileOptions:
    values = {
        "min_short_edge_mm": 4.0,
        "target_short_edge_mm": 12.0,
        "max_long_edge_mm": 45.0,
        "preferred_aspect_ratio": 1.8,
        "max_aspect_ratio": 4.0,
        "max_tessera_count": 1000,
    }
    values.update(updates)
    return TesseraCompileOptions(**values)


def axial_error_degrees(actual: float, expected: float) -> float:
    return abs(((actual - expected + 90.0) % 180.0) - 90.0)


def test_seed_generation_is_repeatable():
    context = make_context()

    first = generate_tessera_seeds(context, options(random_seed=7))
    second = generate_tessera_seeds(context, options(random_seed=7))

    assert first == second


def test_smaller_target_short_edge_creates_more_seeds():
    context = make_context(height=80, width=120)

    smaller = generate_tessera_seeds(
        context,
        options(min_short_edge_mm=3, target_short_edge_mm=8),
    )
    larger = generate_tessera_seeds(
        context,
        options(min_short_edge_mm=4, target_short_edge_mm=16),
    )

    assert len(smaller) > len(larger)


def test_all_seeds_are_inside_their_parent_regions():
    regions = np.zeros((70, 100), dtype=np.int32)
    regions[5:65, 5:45] = 1
    regions[15:55, 55:95] = 2
    context = make_context(height=70, width=100, region_ids=regions)

    seeds = generate_tessera_seeds(context, options(random_seed=31))

    assert seeds
    assert all(context.region_ids[seed.y_px, seed.x_px] == seed.parent_region_id for seed in seeds)


def test_narrow_region_receives_multiple_axial_support_seeds():
    regions = np.zeros((20, 140), dtype=np.int32)
    regions[4:16, 10:130] = 1
    context = make_context(height=20, width=140, region_ids=regions)

    seeds = generate_tessera_seeds(context, options(target_short_edge_mm=10))

    assert len(seeds) >= 5
    assert max(seed.x_px for seed in seeds) - min(seed.x_px for seed in seeds) > 70


def test_subdivision_covers_every_work_pixel_and_nothing_outside():
    regions = np.zeros((50, 80), dtype=np.int32)
    regions[5:45, 8:72] = 1
    context = make_context(height=50, width=80, region_ids=regions)

    result = subdivide_tesserae(context, options())

    assert np.all(result.tessera_ids[context.work_mask] > 0)
    assert np.all(result.tessera_ids[~context.work_mask] == 0)
    assert result.outside_mask_pixel_count == 0
    assert int(np.count_nonzero(result.tessera_ids)) == int(context.work_mask.sum())


def test_tessera_map_cannot_cross_parent_regions():
    regions = np.ones((60, 100), dtype=np.int32)
    regions[:, 50:] = 2
    tiles = np.zeros((60, 100), dtype=np.int32)
    tiles[:, 50:] = 1
    context = make_context(height=60, width=100, region_ids=regions, tile_indices=tiles)

    result = subdivide_tesserae(context, options())

    assert result.crosses_region_boundary_count == 0
    assert np.array_equal(
        result.parent_region_map[result.work_mask],
        context.region_ids[result.work_mask],
    )


def test_tessera_records_inherit_parent_palette_tile_ids():
    regions = np.ones((50, 90), dtype=np.int32)
    regions[:, 45:] = 2
    tiles = np.zeros((50, 90), dtype=np.int32)
    tiles[:, 45:] = 1
    context = make_context(height=50, width=90, region_ids=regions, tile_indices=tiles)

    result = subdivide_tesserae(context, options())

    expected = {1: "tile-a", 2: "tile-b"}
    assert all(record.tile_id == expected[record.parent_region_id] for record in result.records)


def test_slivered_style_produces_higher_mean_piece_aspect_than_smooth():
    context = make_context(height=100, width=140)

    smooth = subdivide_tesserae(
        context,
        options(shape_style="smooth", preferred_aspect_ratio=1.4, random_seed=4),
    )
    slivered = subdivide_tesserae(
        context,
        options(shape_style="slivered", preferred_aspect_ratio=1.4, random_seed=4),
    )

    smooth_mean = np.mean([record.aspect_ratio for record in smooth.records])
    slivered_mean = np.mean([record.aspect_ratio for record in slivered.records])
    assert slivered_mean > smooth_mean


def test_vertical_source_edges_align_seed_flow_vertically():
    source = np.zeros((90, 120, 3), dtype=np.uint8)
    for start in range(0, 120, 16):
        source[:, start : start + 8] = 255
    context = make_context(height=90, width=120, source_rgb=source)

    seeds = generate_tessera_seeds(context, options(flow_strength="high", random_seed=8))

    errors = [axial_error_degrees(np.degrees(seed.orientation_radians), 90) for seed in seeds]
    assert float(np.median(errors)) < 20


def test_tiny_disconnected_fragment_merges_to_adjacent_piece():
    parent = np.ones((7, 7), dtype=np.int32)
    raw = np.ones((7, 7), dtype=np.int32)
    raw[3, 3] = 2
    context = make_context(height=7, width=7, region_ids=parent)

    cleaned, warnings = cleanup_tessera_fragments(
        raw,
        parent,
        context.physical_scale,
        min_fragment_area_mm2=2.0,
    )

    assert len(np.unique(cleaned[cleaned > 0])) == 1
    assert any("tiny" in warning.lower() and "merged" in warning.lower() for warning in warnings)


def test_tiny_boundary_fragment_never_merges_across_parent_region():
    parent = np.ones((5, 7), dtype=np.int32)
    parent[:, 3:] = 2
    parent[2, 3] = 1
    raw = np.ones((5, 7), dtype=np.int32)
    raw[parent == 2] = 3
    raw[2, 3] = 2
    context = make_context(
        height=5,
        width=7,
        region_ids=parent,
        tile_indices=np.where(parent == 1, 0, 1),
    )

    cleaned, _ = cleanup_tessera_fragments(
        raw,
        parent,
        context.physical_scale,
        min_fragment_area_mm2=2.0,
    )

    assert cleaned[2, 3] == cleaned[2, 2]
    assert all(
        len(np.unique(parent[cleaned == piece_id])) == 1
        for piece_id in np.unique(cleaned)
        if piece_id > 0
    )


def test_requested_tessera_count_above_cap_fails_cleanly():
    context = make_context(height=100, width=100)

    with pytest.raises(ValueError, match="max_tessera_count"):
        generate_tessera_seeds(
            context,
            options(
                min_short_edge_mm=1,
                target_short_edge_mm=2,
                preferred_aspect_ratio=1,
                max_tessera_count=10,
            ),
        )


def test_physical_piece_request_is_not_hidden_by_raster_clamping():
    context = make_context(height=32, width=32)
    mural_scale = build_physical_scale(
        (32, 32),
        context.work_mask,
        2000,
        2000,
        "full_image",
    )

    with pytest.raises(ValueError, match="max_tessera_count"):
        generate_tessera_seeds(
            replace(context, physical_scale=mural_scale),
            options(
                min_short_edge_mm=8,
                target_short_edge_mm=18,
                max_long_edge_mm=55,
                max_tessera_count=3000,
            ),
        )


def test_random_seed_changes_deterministic_signature():
    context = make_context()

    first = subdivide_tesserae(context, options(random_seed=2))
    second = subdivide_tesserae(context, options(random_seed=3))

    assert first.deterministic_signature != second.deterministic_signature


def test_repeated_subdivision_has_identical_signature_and_map():
    context = make_context()
    settings = options(random_seed=22)

    first = subdivide_tesserae(context, settings)
    second = subdivide_tesserae(context, settings)

    assert first.deterministic_signature == second.deterministic_signature
    assert np.array_equal(first.tessera_ids, second.tessera_ids)
