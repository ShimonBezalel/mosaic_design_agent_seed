from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from mosaic_agent.palette_compiler import compile_palette_map
from mosaic_agent.models import PaletteDB, Tile
from mosaic_agent.region_map import (
    build_region_records,
    build_palette_arrays,
    create_initial_tile_map,
    derive_segment_target,
    label_tile_components,
    load_source_rgb,
    load_work_area,
    merge_tiny_tile_regions,
    nearest_palette_indices,
    parse_hex_rgb,
    rgb_to_lab,
)
from mosaic_agent.tile_map_models import PaletteCompileRequest


def make_palette() -> PaletteDB:
    return PaletteDB(
        version="test",
        tiles=[
            Tile(tile_id="red", name="Red", hex="#ff0000", inventory_level="high"),
            Tile(tile_id="blue", name="Blue", hex="#0000ff", inventory_level="high"),
            Tile(tile_id="green", name="Green", hex="#00ff00", inventory_level="medium"),
        ],
    )


def save_rgba_mask(path: Path, alpha: list[list[int]], rgb: int = 255) -> Path:
    alpha_array = np.asarray(alpha, dtype=np.uint8)
    pixels = np.full((*alpha_array.shape, 4), rgb, dtype=np.uint8)
    pixels[..., 3] = alpha_array
    Image.fromarray(pixels, "RGBA").save(path)
    return path


def write_palette_db(path: Path) -> Path:
    path.write_text(make_palette().model_dump_json(indent=2), encoding="utf-8")
    return path


def make_compile_request(
    tmp_path: Path,
    source: np.ndarray,
    *,
    selected: list[str] | None = None,
    mask_path: Path | None = None,
    output_name: str = "compiled",
    **overrides,
) -> PaletteCompileRequest:
    source_path = tmp_path / f"source-{output_name}.png"
    Image.fromarray(source.astype(np.uint8), "RGB").save(source_path)
    palette_path = write_palette_db(tmp_path / f"palette-{output_name}.json")
    data: dict[str, object] = {
        "source_image_path": str(source_path),
        "mask_image_path": str(mask_path) if mask_path else None,
        "palette_db_path": str(palette_path),
        "selected_palette_ids": selected or [],
        "granularity": "coarse",
        "target_region_count": 40,
        "min_region_area_px": 4,
        "boundary_smoothing": "none",
        "merge_tiny_regions": True,
        "output_dir": str(tmp_path / output_name),
    }
    data.update(overrides)
    return PaletteCompileRequest(**data)


def test_parse_hex_rgb_accepts_hash_and_bare_values():
    assert parse_hex_rgb("#12aBcF") == (18, 171, 207)
    assert parse_hex_rgb("12abcf") == (18, 171, 207)


@pytest.mark.parametrize("value", ["#fff", "not-red", "#ff000000", ""])
def test_parse_hex_rgb_rejects_invalid_values(value):
    with pytest.raises(ValueError, match="six-digit RGB"):
        parse_hex_rgb(value)


def test_selected_palette_ids_are_respected_and_stably_sorted():
    arrays = build_palette_arrays(make_palette(), ["red", "blue"])

    assert [tile.tile_id for tile in arrays.tiles] == ["blue", "red"]
    assert arrays.rgb.tolist() == [[0, 0, 255], [255, 0, 0]]


def test_empty_selection_uses_every_palette_tile():
    arrays = build_palette_arrays(make_palette(), [])

    assert [tile.tile_id for tile in arrays.tiles] == ["blue", "green", "red"]


def test_unknown_selected_palette_id_is_rejected():
    with pytest.raises(ValueError, match="not in palette DB: missing"):
        build_palette_arrays(make_palette(), ["red", "missing"])


def test_no_mask_uses_the_whole_image():
    work = load_work_area(None, (3, 2))

    assert work.shape == (2, 3)
    assert work.all()


def test_transparent_alpha_is_work_area(tmp_path):
    mask = save_rgba_mask(tmp_path / "alpha.png", [[0, 255], [255, 0]])

    work = load_work_area(mask, (2, 2))

    assert work.tolist() == [[True, False], [False, True]]


def test_opaque_alpha_is_outside_work_area(tmp_path):
    mask = save_rgba_mask(tmp_path / "alpha.png", [[0, 255]])

    work = load_work_area(mask, (2, 1))

    assert work.tolist() == [[True, False]]


def test_black_white_mask_uses_white_as_work_area(tmp_path):
    mask = tmp_path / "bw.png"
    Image.fromarray(np.array([[255, 0], [0, 255]], dtype=np.uint8), "L").save(mask)

    work = load_work_area(mask, (2, 2))

    assert work.tolist() == [[True, False], [False, True]]


def test_rgba_mask_always_uses_alpha_even_without_variation(tmp_path):
    mask = tmp_path / "opaque-rgba.png"
    pixels = np.array([[[255, 255, 255, 255], [0, 0, 0, 255]]], dtype=np.uint8)
    Image.fromarray(pixels, "RGBA").save(mask)

    work = load_work_area(mask, (2, 1))

    assert work.tolist() == [[False, False]]


def test_mask_resize_preserves_hard_boundaries_with_nearest_neighbor(tmp_path):
    mask = tmp_path / "two-pixel-mask.png"
    Image.fromarray(np.array([[255, 0]], dtype=np.uint8), "L").save(mask)

    work = load_work_area(mask, (4, 2))

    assert work[:, :2].all()
    assert not work[:, 2:].any()


def test_nearest_palette_color_returns_exact_expected_tiles():
    source_lab = rgb_to_lab(np.array([[255, 0, 0], [0, 0, 255]], dtype=np.uint8))
    palette = build_palette_arrays(make_palette(), ["red", "blue"])

    indices, distances = nearest_palette_indices(source_lab, palette.lab)

    assert [palette.tiles[index].tile_id for index in indices] == ["red", "blue"]
    assert distances.tolist() == pytest.approx([0.0, 0.0], abs=1e-10)


def test_nearest_palette_color_cannot_use_an_unselected_tile():
    source_lab = rgb_to_lab(np.array([[0, 255, 0]], dtype=np.uint8))
    palette = build_palette_arrays(make_palette(), ["red", "blue"])

    indices, _ = nearest_palette_indices(source_lab, palette.lab)

    assert palette.tiles[int(indices[0])].tile_id in {"red", "blue"}


def test_large_source_is_resized_once_with_reported_scale(tmp_path):
    path = tmp_path / "large.png"
    Image.new("RGB", (200, 100), "red").save(path)

    normalized = load_source_rgb(path, max_working_size=100)

    assert normalized.original_size == (200, 100)
    assert normalized.working_size == (100, 50)
    assert normalized.rgb.shape == (50, 100, 3)
    assert normalized.scale == pytest.approx(0.5)


def test_granularity_derives_ordered_segment_targets():
    coarse = derive_segment_target("coarse", area_px=1_000_000)
    medium = derive_segment_target("medium", area_px=1_000_000)
    fine = derive_segment_target("fine", area_px=1_000_000)

    assert (coarse, medium, fine) == (120, 300, 650)


def test_target_region_count_overrides_granularity_with_safe_bounds():
    assert derive_segment_target("fine", area_px=10_000, target_region_count=75) == 75
    assert derive_segment_target("coarse", area_px=12, target_region_count=75) == 12


def test_simple_two_color_image_compiles_to_two_palette_colors():
    source = np.zeros((40, 80, 3), dtype=np.uint8)
    source[:, :40] = (255, 0, 0)
    source[:, 40:] = (0, 0, 255)
    work = np.ones((40, 80), dtype=bool)
    palette = build_palette_arrays(make_palette(), ["red", "blue"])

    initial = create_initial_tile_map(
        source,
        work,
        palette,
        granularity="coarse",
        target_region_count=40,
        boundary_smoothing="none",
    )

    used = {palette.tiles[index].tile_id for index in np.unique(initial.tile_indices[work])}
    assert used == {"red", "blue"}


def test_masked_two_color_image_only_assigns_inside_work_area():
    source = np.zeros((30, 60, 3), dtype=np.uint8)
    source[:, :30] = (255, 0, 0)
    source[:, 30:] = (0, 0, 255)
    work = np.zeros((30, 60), dtype=bool)
    work[:, :30] = True
    palette = build_palette_arrays(make_palette(), ["red", "blue"])

    initial = create_initial_tile_map(
        source,
        work,
        palette,
        granularity="coarse",
        boundary_smoothing="none",
    )

    assert set(np.unique(initial.tile_indices[work])) == {1}
    assert (initial.tile_indices[~work] == -1).all()


def test_segmentation_is_deterministic_for_identical_input():
    rng = np.random.default_rng(20260702)
    source = rng.integers(0, 256, size=(48, 64, 3), dtype=np.uint8)
    work = np.ones((48, 64), dtype=bool)
    palette = build_palette_arrays(make_palette(), [])

    first = create_initial_tile_map(source, work, palette, granularity="medium")
    second = create_initial_tile_map(source, work, palette, granularity="medium")

    assert np.array_equal(first.segment_labels, second.segment_labels)
    assert np.array_equal(first.tile_indices, second.tile_indices)
    assert first.segment_delta_e == second.segment_delta_e


def test_fine_granularity_produces_at_least_as_many_segments_as_coarse():
    rng = np.random.default_rng(41)
    source = rng.integers(0, 256, size=(120, 160, 3), dtype=np.uint8)
    work = np.ones((120, 160), dtype=bool)
    palette = build_palette_arrays(make_palette(), [])

    coarse = create_initial_tile_map(source, work, palette, granularity="coarse")
    fine = create_initial_tile_map(source, work, palette, granularity="fine")

    assert len(np.unique(coarse.segment_labels[work])) <= len(
        np.unique(fine.segment_labels[work])
    )


def test_adjacent_same_tile_pixels_merge_into_one_component():
    tile_indices = np.zeros((3, 4), dtype=np.int32)
    work = np.ones((3, 4), dtype=bool)

    regions = label_tile_components(tile_indices, work)

    assert set(regions.ravel()) == {1}


def test_diagonal_same_tile_pixels_remain_separate_components():
    tile_indices = np.array([[0, 1], [1, 0]], dtype=np.int32)
    work = np.ones((2, 2), dtype=bool)

    regions = label_tile_components(tile_indices, work)

    assert len(np.unique(regions)) == 4


def test_region_ids_are_stable_top_to_bottom_then_left_to_right():
    tile_indices = np.array(
        [
            [0, 0, 1, 1],
            [0, 0, 1, 1],
            [1, 1, 0, 0],
            [1, 1, 0, 0],
        ],
        dtype=np.int32,
    )
    work = np.ones((4, 4), dtype=bool)

    regions = label_tile_components(tile_indices, work)

    assert regions[0, 0] == 1
    assert regions[0, 2] == 2
    assert regions[2, 0] == 3
    assert regions[2, 2] == 4


def test_tiny_color_island_below_minimum_area_is_merged():
    tile_indices = np.ones((7, 7), dtype=np.int32)
    tile_indices[3, 3] = 0
    work = np.ones((7, 7), dtype=bool)
    source = np.full((7, 7, 3), (255, 0, 0), dtype=np.uint8)
    palette = build_palette_arrays(make_palette(), ["red", "blue"])

    cleaned = merge_tiny_tile_regions(
        tile_indices,
        work,
        rgb_to_lab(source),
        palette.lab,
        min_region_area_px=4,
    )

    assert set(np.unique(cleaned.tile_indices[work])) == {1}
    assert cleaned.region_count == 1


def test_tiny_merge_does_not_change_masked_pixel_count():
    tile_indices = np.ones((6, 6), dtype=np.int32)
    tile_indices[2, 2] = 0
    work = np.ones((6, 6), dtype=bool)
    source = np.full((6, 6, 3), (255, 0, 0), dtype=np.uint8)
    palette = build_palette_arrays(make_palette(), ["red", "blue"])

    cleaned = merge_tiny_tile_regions(
        tile_indices,
        work,
        rgb_to_lab(source),
        palette.lab,
        min_region_area_px=5,
    )

    assert int((cleaned.tile_indices >= 0).sum()) == int(work.sum())
    assert (cleaned.tile_indices[~work] == -1).all()


def test_tiny_only_region_without_neighbor_is_kept_with_warning():
    tile_indices = np.array([[0]], dtype=np.int32)
    work = np.array([[True]])
    source_lab = rgb_to_lab(np.array([[[255, 0, 0]]], dtype=np.uint8))
    palette = build_palette_arrays(make_palette(), ["red"])

    cleaned = merge_tiny_tile_regions(
        tile_indices,
        work,
        source_lab,
        palette.lab,
        min_region_area_px=4,
    )

    assert cleaned.region_count == 1
    assert any("no adjacent region" in warning for warning in cleaned.warnings)


def test_region_records_include_neighbors_and_geometry():
    tile_indices = np.array([[0, 0, 1, 1], [0, 0, 1, 1]], dtype=np.int32)
    work = np.ones((2, 4), dtype=bool)
    source = np.zeros((2, 4, 3), dtype=np.uint8)
    source[:, :2] = (0, 0, 255)
    source[:, 2:] = (255, 0, 0)
    palette = build_palette_arrays(make_palette(), ["red", "blue"])
    regions = label_tile_components(tile_indices, work)

    records = build_region_records(
        regions,
        tile_indices,
        source,
        rgb_to_lab(source),
        palette,
        pixel_area_cm2=2.5,
    )

    assert [record.region_id for record in records] == [1, 2]
    assert records[0].neighbor_region_ids == [2]
    assert records[1].neighbor_region_ids == [1]
    assert records[0].bbox_xyxy == (0, 0, 2, 2)
    assert records[0].centroid_xy == pytest.approx((0.5, 0.5))
    assert records[0].estimated_area_cm2 == pytest.approx(10.0)


def test_compile_output_uses_only_selected_palette_ids(tmp_path):
    source = np.zeros((40, 80, 3), dtype=np.uint8)
    source[:, :40] = (255, 0, 0)
    source[:, 40:] = (0, 255, 0)
    request = make_compile_request(tmp_path, source, selected=["red", "blue"])

    result = compile_palette_map(request)

    assert {usage.tile_id for usage in result.color_usage} <= {"red", "blue"}
    assert {region.tile_id for region in result.regions} <= {"red", "blue"}


def test_max_colors_keeps_highest_demand_tiles_and_reassigns(tmp_path):
    source = np.zeros((50, 100, 3), dtype=np.uint8)
    source[:, :50] = (255, 0, 0)
    source[:, 50:80] = (0, 0, 255)
    source[:, 80:] = (0, 255, 0)
    request = make_compile_request(tmp_path, source, max_colors=2)

    result = compile_palette_map(request)

    assert {usage.tile_id for usage in result.color_usage} == {"red", "blue"}
    assert result.color_count == 2
    assert any("max_colors" in warning and "green" in warning for warning in result.warnings)


def test_palette_map_pixels_inside_mask_are_exact_selected_hex_colors(tmp_path):
    source = np.zeros((30, 60, 3), dtype=np.uint8)
    source[:, :30] = (250, 20, 20)
    source[:, 30:] = (10, 30, 240)
    request = make_compile_request(tmp_path, source, selected=["red", "blue"])

    result = compile_palette_map(request)
    rendered = np.asarray(Image.open(result.palette_map_path).convert("RGB"))

    assert set(map(tuple, rendered.reshape(-1, 3))) <= {(255, 0, 0), (0, 0, 255)}


def test_same_input_and_parameters_have_same_signature_in_different_directories(tmp_path):
    source = np.zeros((32, 48, 3), dtype=np.uint8)
    source[:, :24] = (255, 0, 0)
    source[:, 24:] = (0, 0, 255)
    first = compile_palette_map(make_compile_request(tmp_path, source, output_name="first"))
    second = compile_palette_map(make_compile_request(tmp_path, source, output_name="second"))

    first_qa = json.loads(Path(first.qa_report_path).read_text(encoding="utf-8"))
    second_qa = json.loads(Path(second.qa_report_path).read_text(encoding="utf-8"))

    assert first_qa["deterministic_signature"] == second_qa["deterministic_signature"]
    assert first.run_id == second.run_id


def test_signature_changes_when_compilation_parameters_change(tmp_path):
    rng = np.random.default_rng(9)
    source = rng.integers(0, 256, size=(50, 70, 3), dtype=np.uint8)
    coarse = compile_palette_map(
        make_compile_request(tmp_path, source, output_name="coarse", granularity="coarse")
    )
    fine = compile_palette_map(
        make_compile_request(tmp_path, source, output_name="fine", granularity="fine")
    )

    coarse_qa = json.loads(Path(coarse.qa_report_path).read_text(encoding="utf-8"))
    fine_qa = json.loads(Path(fine.qa_report_path).read_text(encoding="utf-8"))
    assert coarse_qa["deterministic_signature"] != fine_qa["deterministic_signature"]


def test_no_mask_compiles_every_source_pixel(tmp_path):
    source = np.full((17, 23, 3), (255, 0, 0), dtype=np.uint8)

    result = compile_palette_map(make_compile_request(tmp_path, source, selected=["red"]))

    assert result.masked_pixel_count == 17 * 23


def test_masked_compile_excludes_outside_pixels_from_accounting(tmp_path):
    source = np.full((20, 30, 3), (255, 0, 0), dtype=np.uint8)
    alpha = np.full((20, 30), 255, dtype=np.uint8)
    alpha[:, :12] = 0
    mask_path = save_rgba_mask(tmp_path / "mask.png", alpha.tolist())

    result = compile_palette_map(
        make_compile_request(tmp_path, source, selected=["red"], mask_path=mask_path)
    )

    assert result.masked_pixel_count == 20 * 12
    assert sum(item.pixel_count for item in result.color_usage) == 20 * 12


def test_empty_work_mask_fails_cleanly(tmp_path):
    source = np.full((10, 10, 3), (255, 0, 0), dtype=np.uint8)
    mask_path = save_rgba_mask(tmp_path / "empty-mask.png", [[255] * 10 for _ in range(10)])
    request = make_compile_request(tmp_path, source, mask_path=mask_path)

    with pytest.raises(ValueError, match="Mask has no editable pixels"):
        compile_palette_map(request)


def test_legend_and_regions_account_for_every_masked_pixel(tmp_path):
    source = np.zeros((24, 36, 3), dtype=np.uint8)
    source[:, :18] = (255, 0, 0)
    source[:, 18:] = (0, 0, 255)

    result = compile_palette_map(make_compile_request(tmp_path, source))

    assert sum(item.pixel_count for item in result.color_usage) == result.masked_pixel_count
    assert sum(item.pixel_count for item in result.regions) == result.masked_pixel_count
    assert sum(item.percent_of_mask for item in result.color_usage) == pytest.approx(100.0)


def test_physical_dimensions_populate_region_and_color_areas(tmp_path):
    source = np.full((20, 40, 3), (255, 0, 0), dtype=np.uint8)
    request = make_compile_request(
        tmp_path,
        source,
        selected=["red"],
        physical_width_cm=200.0,
        physical_height_cm=100.0,
    )

    result = compile_palette_map(request)

    assert sum(item.estimated_area_cm2 or 0 for item in result.color_usage) == pytest.approx(20_000)
    assert sum(item.estimated_area_cm2 or 0 for item in result.regions) == pytest.approx(20_000)


def test_missing_physical_dimensions_leave_area_estimates_null(tmp_path):
    source = np.full((20, 40, 3), (255, 0, 0), dtype=np.uint8)

    result = compile_palette_map(make_compile_request(tmp_path, source, selected=["red"]))

    assert all(item.estimated_area_cm2 is None for item in result.color_usage)
    assert all(item.estimated_area_cm2 is None for item in result.regions)


def test_seeded_random_compile_is_repeatable_and_palette_grounded(tmp_path):
    rng = np.random.default_rng(2026)
    source = rng.integers(0, 256, size=(37, 53, 3), dtype=np.uint8)
    first = compile_palette_map(
        make_compile_request(tmp_path, source, selected=["red", "green"], output_name="random-a")
    )
    second = compile_palette_map(
        make_compile_request(tmp_path, source, selected=["red", "green"], output_name="random-b")
    )
    first_qa = json.loads(Path(first.qa_report_path).read_text(encoding="utf-8"))
    second_qa = json.loads(Path(second.qa_report_path).read_text(encoding="utf-8"))

    assert first_qa["deterministic_signature"] == second_qa["deterministic_signature"]
    assert first_qa["colors_used_not_in_selected_palette"] == []
    assert {usage.tile_id for usage in first.color_usage} <= {"red", "green"}
