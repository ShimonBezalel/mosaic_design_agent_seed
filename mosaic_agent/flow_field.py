from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import gaussian_filter, sobel
from skimage.color import rgb2gray

from mosaic_agent.tile_map_models import FlowStrength, PhysicalScale


FLOW_WEIGHTS: dict[FlowStrength, float] = {
    "none": 0.0,
    "low": 0.35,
    "medium": 0.65,
    "high": 1.0,
}


@dataclass(frozen=True)
class FlowField:
    orientation_radians: np.ndarray
    confidence: np.ndarray
    magnitude: np.ndarray


def compute_gradient_orientation_field(
    source_rgb: np.ndarray,
    sigma: float = 2.0,
) -> FlowField:
    source = np.asarray(source_rgb)
    if source.ndim != 3 or source.shape[-1] != 3:
        raise ValueError("source image must have shape (height, width, 3)")
    if sigma < 0:
        raise ValueError("flow smoothing sigma cannot be negative")

    grayscale = np.asarray(rgb2gray(source), dtype=np.float64)
    gradient_x = sobel(grayscale, axis=1, mode="reflect")
    gradient_y = sobel(grayscale, axis=0, mode="reflect")
    magnitude = np.hypot(gradient_x, gradient_y)
    tangent = np.arctan2(gradient_y, gradient_x) + np.pi / 2.0

    vector_x = magnitude * np.cos(2.0 * tangent)
    vector_y = magnitude * np.sin(2.0 * tangent)
    if sigma > 0:
        vector_x = gaussian_filter(vector_x, sigma=sigma, mode="reflect")
        vector_y = gaussian_filter(vector_y, sigma=sigma, mode="reflect")
        denominator = gaussian_filter(magnitude, sigma=sigma, mode="reflect")
    else:
        denominator = magnitude

    resultant = np.hypot(vector_x, vector_y)
    confidence = np.divide(
        resultant,
        denominator,
        out=np.zeros_like(resultant),
        where=denominator > np.finfo(np.float64).eps,
    )
    confidence = np.clip(confidence, 0.0, 1.0)
    orientation = np.mod(0.5 * np.arctan2(vector_y, vector_x), np.pi)
    return FlowField(
        orientation_radians=orientation,
        confidence=confidence,
        magnitude=magnitude,
    )


def dominant_orientation_for_mask(
    field: FlowField,
    mask: np.ndarray,
) -> tuple[float, float]:
    region = np.asarray(mask, dtype=bool)
    if region.shape != field.orientation_radians.shape:
        raise ValueError("flow field and mask dimensions must match")
    if not np.any(region):
        raise ValueError("orientation mask has no pixels")

    weights = field.magnitude[region] * field.confidence[region]
    weight_sum = float(weights.sum())
    if weight_sum <= np.finfo(np.float64).eps:
        return 0.0, 0.0

    angles = field.orientation_radians[region]
    vector_x = float(np.sum(weights * np.cos(2.0 * angles)))
    vector_y = float(np.sum(weights * np.sin(2.0 * angles)))
    coherence = min(1.0, np.hypot(vector_x, vector_y) / weight_sum)
    orientation = float(np.mod(0.5 * np.arctan2(vector_y, vector_x), np.pi))
    return orientation, float(coherence)


def pca_orientation_for_mask(mask: np.ndarray, scale: PhysicalScale) -> float:
    region = np.asarray(mask, dtype=bool)
    if region.shape != (scale.image_height_px, scale.image_width_px):
        raise ValueError("physical scale and mask dimensions must match")
    ys, xs = np.nonzero(region)
    if len(xs) < 2:
        return 0.0

    points = np.column_stack(
        (
            (xs.astype(np.float64) + 0.5) * scale.mm_per_px_x,
            (ys.astype(np.float64) + 0.5) * scale.mm_per_px_y,
        )
    )
    centered = points - points.mean(axis=0)
    covariance = centered.T @ centered / len(points)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    if eigenvalues[-1] <= np.finfo(np.float64).eps:
        return 0.0
    if abs(eigenvalues[-1] - eigenvalues[0]) <= eigenvalues[-1] * 1e-9:
        return 0.0
    major_axis = eigenvectors[:, -1]
    return float(np.mod(np.arctan2(major_axis[1], major_axis[0]), np.pi))


def blend_axial_orientations(base: float, flow: float, weight: float) -> float:
    if not 0.0 <= weight <= 1.0:
        raise ValueError("orientation blend weight must be between zero and one")
    vector_x = (1.0 - weight) * np.cos(2.0 * base) + weight * np.cos(2.0 * flow)
    vector_y = (1.0 - weight) * np.sin(2.0 * base) + weight * np.sin(2.0 * flow)
    if np.hypot(vector_x, vector_y) <= np.finfo(np.float64).eps:
        return float(np.mod(base, np.pi))
    return float(np.mod(0.5 * np.arctan2(vector_y, vector_x), np.pi))


def resolve_region_orientation(
    field: FlowField,
    mask: np.ndarray,
    scale: PhysicalScale,
    flow_strength: FlowStrength,
) -> float:
    base = pca_orientation_for_mask(mask, scale)
    strength = FLOW_WEIGHTS[flow_strength]
    if strength == 0:
        return base
    flow, confidence = dominant_orientation_for_mask(field, mask)
    return blend_axial_orientations(base, flow, strength * confidence)
