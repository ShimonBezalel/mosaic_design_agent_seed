from __future__ import annotations

import numpy as np
import pytest

from mosaic_agent.flow_field import (
    blend_axial_orientations,
    compute_gradient_orientation_field,
    dominant_orientation_for_mask,
    pca_orientation_for_mask,
    resolve_region_orientation,
)
from mosaic_agent.physical_scale import build_physical_scale


def axial_error_degrees(actual: float, expected: float) -> float:
    return abs(((actual - expected + 90.0) % 180.0) - 90.0)


def solid_scale(mask: np.ndarray):
    height, width = mask.shape
    return build_physical_scale(
        (width, height),
        np.ones_like(mask),
        float(width),
        float(height),
        "full_image",
    )


def test_vertical_stripe_has_vertical_tangent_flow():
    source = np.zeros((80, 100, 3), dtype=np.uint8)
    source[:, 42:58] = 255

    field = compute_gradient_orientation_field(source)
    orientation, confidence = dominant_orientation_for_mask(field, np.ones((80, 100), bool))

    assert axial_error_degrees(np.degrees(orientation), 90) < 12
    assert confidence > 0.2


def test_horizontal_band_has_horizontal_tangent_flow():
    source = np.zeros((100, 80, 3), dtype=np.uint8)
    source[42:58, :] = 255

    field = compute_gradient_orientation_field(source)
    orientation, confidence = dominant_orientation_for_mask(field, np.ones((100, 80), bool))

    assert axial_error_degrees(np.degrees(orientation), 0) < 12
    assert confidence > 0.2


def test_diagonal_line_has_diagonal_tangent_flow():
    yy, xx = np.mgrid[:96, :96]
    source = np.zeros((96, 96, 3), dtype=np.uint8)
    source[np.abs(yy - xx) <= 3] = 255

    field = compute_gradient_orientation_field(source, sigma=1.5)
    orientation, confidence = dominant_orientation_for_mask(field, np.ones((96, 96), bool))

    assert axial_error_degrees(np.degrees(orientation), 45) < 12
    assert confidence > 0.2


def test_flat_image_has_negligible_flow_confidence():
    source = np.full((50, 70, 3), 127, dtype=np.uint8)

    field = compute_gradient_orientation_field(source)
    _, confidence = dominant_orientation_for_mask(field, np.ones((50, 70), bool))

    assert confidence < 0.05
    assert np.max(field.confidence) < 0.05


def test_pca_orientation_follows_horizontal_physical_mask():
    mask = np.zeros((80, 120), dtype=bool)
    mask[34:46, 10:110] = True

    orientation = pca_orientation_for_mask(mask, solid_scale(mask))

    assert axial_error_degrees(np.degrees(orientation), 0) < 2


def test_pca_orientation_follows_diagonal_mask():
    yy, xx = np.mgrid[:100, :100]
    mask = np.abs(yy - xx) <= 2

    orientation = pca_orientation_for_mask(mask, solid_scale(mask))

    assert axial_error_degrees(np.degrees(orientation), 45) < 2


def test_flat_flow_resolves_to_deterministic_region_pca():
    source = np.full((60, 100, 3), 127, dtype=np.uint8)
    mask = np.zeros((60, 100), dtype=bool)
    mask[25:35, 10:90] = True
    field = compute_gradient_orientation_field(source)
    scale = solid_scale(mask)

    first = resolve_region_orientation(field, mask, scale, "high")
    second = resolve_region_orientation(field, mask, scale, "high")

    assert first == pytest.approx(second)
    assert axial_error_degrees(np.degrees(first), 0) < 2


def test_axial_blend_wraps_across_zero_degrees():
    blended = blend_axial_orientations(np.radians(175), np.radians(5), 0.5)

    assert axial_error_degrees(np.degrees(blended), 0) < 1


def test_one_pixel_pca_falls_back_to_zero():
    mask = np.zeros((5, 5), dtype=bool)
    mask[2, 2] = True

    assert pca_orientation_for_mask(mask, solid_scale(mask)) == 0.0
