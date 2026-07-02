from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from mosaic_agent.models import PaletteDB, Tile
from mosaic_agent.region_map import (
    build_palette_arrays,
    load_source_rgb,
    load_work_area,
    nearest_palette_indices,
    parse_hex_rgb,
    rgb_to_lab,
)


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


def test_opaque_rgba_without_alpha_variation_uses_grayscale(tmp_path):
    mask = tmp_path / "opaque-rgba.png"
    pixels = np.array([[[255, 255, 255, 255], [0, 0, 0, 255]]], dtype=np.uint8)
    Image.fromarray(pixels, "RGBA").save(mask)

    work = load_work_area(mask, (2, 1))

    assert work.tolist() == [[True, False]]


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
