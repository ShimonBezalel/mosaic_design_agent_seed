from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from mosaic_agent.physical_scale import (
    area_mm2_to_px,
    area_px_to_mm2,
    build_physical_scale,
    length_mm_to_px,
)
from mosaic_agent.tile_map_models import TesseraCompileOptions


def test_full_image_scale_uses_working_dimensions():
    work = np.ones((100, 200), dtype=bool)

    scale = build_physical_scale((200, 100), work, 2000, 1000, "full_image")

    assert scale.image_width_px == 200
    assert scale.image_height_px == 100
    assert scale.mm_per_px_x == pytest.approx(10)
    assert scale.mm_per_px_y == pytest.approx(10)
    assert scale.px_per_mm_x == pytest.approx(0.1)
    assert scale.px_per_mm_y == pytest.approx(0.1)


def test_mask_bbox_scale_uses_only_mask_bounds():
    work = np.zeros((100, 200), dtype=bool)
    work[20:80, 50:150] = True

    scale = build_physical_scale((200, 100), work, 2000, 1200, "mask_bbox")

    assert scale.mm_per_px_x == pytest.approx(20)
    assert scale.mm_per_px_y == pytest.approx(20)


def test_length_conversion_is_axis_aware():
    work = np.ones((50, 100), dtype=bool)
    scale = build_physical_scale((100, 50), work, 1000, 1000, "full_image")

    assert length_mm_to_px(scale, 20, axis="x") == pytest.approx(2)
    assert length_mm_to_px(scale, 20, axis="y") == pytest.approx(1)
    assert length_mm_to_px(scale, 20, axis="mean") == pytest.approx(2**0.5)


def test_area_conversion_round_trips():
    work = np.ones((50, 100), dtype=bool)
    scale = build_physical_scale((100, 50), work, 1000, 500, "full_image")

    pixels = area_mm2_to_px(scale, 25_000)

    assert pixels == pytest.approx(250)
    assert area_px_to_mm2(scale, pixels) == pytest.approx(25_000)


def test_minimum_color_area_cm2_converts_to_pixels():
    work = np.ones((100, 100), dtype=bool)
    scale = build_physical_scale((100, 100), work, 1000, 1000, "full_image")

    assert area_mm2_to_px(scale, 100 * 100) == pytest.approx(100)


def test_empty_mask_cannot_define_mask_bbox_scale():
    with pytest.raises(ValueError, match="no work pixels"):
        build_physical_scale(
            (20, 20),
            np.zeros((20, 20), dtype=bool),
            100,
            100,
            "mask_bbox",
        )


@pytest.mark.parametrize(
    "updates",
    [
        {"min_short_edge_mm": 20, "target_short_edge_mm": 10},
        {"target_short_edge_mm": 60, "max_long_edge_mm": 55},
        {"preferred_aspect_ratio": 5, "max_aspect_ratio": 4},
    ],
)
def test_tessera_options_validate_edge_and_aspect_order(updates):
    with pytest.raises(ValidationError, match="ordering"):
        TesseraCompileOptions(**updates)


def test_tessera_options_have_practical_defaults():
    options = TesseraCompileOptions()

    assert options.physical_scale_basis == "mask_bbox"
    assert options.min_short_edge_mm == 8
    assert options.target_short_edge_mm == 18
    assert options.max_long_edge_mm == 55
    assert options.preferred_aspect_ratio == 1.8
    assert options.max_aspect_ratio == 4
    assert options.flow_strength == "medium"
    assert options.shape_style == "irregular"
    assert options.grout_width_mm == 2
    assert options.max_tessera_count == 3000


def test_physical_scale_rejects_missing_or_nonpositive_dimensions():
    work = np.ones((10, 10), dtype=bool)

    with pytest.raises(ValueError, match="positive physical dimensions"):
        build_physical_scale((10, 10), work, 0, 100, "full_image")
