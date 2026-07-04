from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation
from skimage.segmentation import find_boundaries

from mosaic_agent.physical_scale import length_mm_to_px
from mosaic_agent.tessera import TesseraSubdivision
from mosaic_agent.tile_map_models import (
    PhysicalScale,
    TesseraCompileOptions,
    TesseraCompileResult,
)

if TYPE_CHECKING:
    from mosaic_agent.palette_compiler import CompiledTileMap


TESSERA_HEADERS = [
    "tessera_id",
    "parent_region_id",
    "tile_id",
    "area_px",
    "area_mm2",
    "centroid_x",
    "centroid_y",
    "orientation_degrees",
    "estimated_short_edge_mm",
    "estimated_long_edge_mm",
    "aspect_ratio",
    "warning",
]


def write_tessera_artifacts(
    compiled: "CompiledTileMap",
    subdivision: TesseraSubdivision,
    scale: PhysicalScale,
    options: TesseraCompileOptions,
    output_dir: Path,
) -> TesseraCompileResult:
    paths = {
        "map": output_dir / "tessera_map.png",
        "boundaries": output_dir / "tessera_boundaries.png",
        "svg": output_dir / "tessera.svg",
        "csv": output_dir / "tessera.csv",
        "qa": output_dir / "tessera_qa_report.json",
    }
    render_tessera_map(compiled, subdivision, scale, options).save(paths["map"])
    render_tessera_boundaries(compiled, subdivision, scale, options).save(paths["boundaries"])
    write_tessera_svg(compiled, subdivision, paths["svg"])
    write_tessera_csv(subdivision, paths["csv"])
    qa = build_tessera_qa(compiled, subdivision, scale, options)
    paths["qa"].write_text(
        json.dumps(qa, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    areas = np.asarray([record.area_mm2 for record in subdivision.records], dtype=np.float64)
    aspects = np.asarray([record.aspect_ratio for record in subdivision.records], dtype=np.float64)
    return TesseraCompileResult(
        tessera_map_path=str(paths["map"]),
        tessera_boundaries_path=str(paths["boundaries"]),
        tessera_svg_path=str(paths["svg"]),
        tessera_csv_path=str(paths["csv"]),
        tessera_qa_report_path=str(paths["qa"]),
        tessera_count=len(subdivision.records),
        mean_area_mm2=float(areas.mean()),
        median_area_mm2=float(np.median(areas)),
        min_area_mm2=float(areas.min()),
        max_area_mm2=float(areas.max()),
        mean_aspect_ratio=float(aspects.mean()),
        warnings=qa["warnings"],
        deterministic_signature=subdivision.deterministic_signature,
        records=list(subdivision.records),
    )


def render_tessera_map(
    compiled: "CompiledTileMap",
    subdivision: TesseraSubdivision,
    scale: PhysicalScale,
    options: TesseraCompileOptions,
) -> Image.Image:
    rendered = _palette_render(compiled)
    boundaries = find_boundaries(subdivision.tessera_ids, mode="inner") & compiled.work_mask
    grout_px = length_mm_to_px(scale, options.grout_width_mm, axis="mean")
    if grout_px > 0:
        extra_radius = max(0, int(round((grout_px - 1.0) / 2.0)))
        if extra_radius > 0:
            boundaries = binary_dilation(
                boundaries,
                iterations=extra_radius,
            ) & compiled.work_mask
        rendered[boundaries] = (34, 30, 26)
    return Image.fromarray(rendered, "RGB")


def render_tessera_boundaries(
    compiled: "CompiledTileMap",
    subdivision: TesseraSubdivision,
    scale: PhysicalScale,
    options: TesseraCompileOptions,
) -> Image.Image:
    rendered = compiled.source_rgb.astype(np.uint8).copy()
    boundaries = find_boundaries(subdivision.tessera_ids, mode="thick") & compiled.work_mask
    preview_px = length_mm_to_px(scale, options.grout_width_mm, axis="mean")
    if preview_px > 2:
        boundaries = binary_dilation(
            boundaries,
            iterations=max(1, int(np.ceil(preview_px / 4.0))),
        ) & compiled.work_mask
    rendered[boundaries] = (24, 22, 20)
    return Image.fromarray(rendered, "RGB")


def write_tessera_svg(
    compiled: "CompiledTileMap",
    subdivision: TesseraSubdivision,
    path: Path,
) -> None:
    height, width = compiled.work_mask.shape
    tile_by_id = {tile.tile_id: tile for tile in compiled.palette.tiles}
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">'
        ),
        "  <desc>Physically scaled tessera planning geometry; artist review required.</desc>",
    ]
    for record in subdivision.records:
        fill = f"#{tile_by_id[record.tile_id].hex.lstrip('#').lower()}"
        points = " ".join(f"{x:.2f},{y:.2f}" for x, y in record.polygon_xy)
        lines.append(
            f'  <g data-tessera-id="{record.tessera_id}" '
            f'data-parent-region-id="{record.parent_region_id}" '
            f'data-tile-id="{html.escape(record.tile_id)}" fill="{fill}" '
            'stroke="#202020" stroke-width="0.75">'
        )
        lines.append(f'    <polygon points="{points}" />')
        lines.append("  </g>")
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_tessera_csv(subdivision: TesseraSubdivision, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TESSERA_HEADERS)
        writer.writeheader()
        for record in subdivision.records:
            writer.writerow(
                {
                    "tessera_id": record.tessera_id,
                    "parent_region_id": record.parent_region_id,
                    "tile_id": record.tile_id,
                    "area_px": record.area_px,
                    "area_mm2": record.area_mm2,
                    "centroid_x": record.centroid_xy[0],
                    "centroid_y": record.centroid_xy[1],
                    "orientation_degrees": record.orientation_degrees,
                    "estimated_short_edge_mm": record.short_edge_mm_estimate,
                    "estimated_long_edge_mm": record.long_edge_mm_estimate,
                    "aspect_ratio": record.aspect_ratio,
                    "warning": "; ".join(record.warnings),
                }
            )


def build_tessera_qa(
    compiled: "CompiledTileMap",
    subdivision: TesseraSubdivision,
    scale: PhysicalScale,
    options: TesseraCompileOptions,
) -> dict[str, object]:
    records = subdivision.records
    areas = np.asarray([record.area_mm2 for record in records], dtype=np.float64)
    aspects = np.asarray([record.aspect_ratio for record in records], dtype=np.float64)
    expected_tile_by_parent = {region.region_id: region.tile_id for region in compiled.regions}
    bad_inheritance = [
        record.tessera_id
        for record in records
        if record.tile_id != expected_tile_by_parent[record.parent_region_id]
    ]
    warnings = list(subdivision.warnings)
    warnings.extend(
        f"Tessera {record.tessera_id}: {warning}"
        for record in records
        for warning in record.warnings
    )
    warnings = list(dict.fromkeys(warnings))
    actual_pixels = sum(record.area_px for record in records)
    expected_pixels = int(compiled.work_mask.sum())
    return {
        "tessera_count": len(records),
        "color_region_count": len(compiled.regions),
        "area_sum_check": {
            "expected": expected_pixels,
            "actual": actual_pixels,
            "matches": actual_pixels == expected_pixels,
        },
        "outside_mask_pixel_count": subdivision.outside_mask_pixel_count,
        "crosses_region_boundary_count": subdivision.crosses_region_boundary_count,
        "tile_inheritance_check": {
            "invalid_tessera_ids": bad_inheritance,
            "matches": not bad_inheritance,
        },
        "count_cap_check": {
            "limit": options.max_tessera_count,
            "actual": len(records),
            "matches": len(records) <= options.max_tessera_count,
        },
        "min_short_edge_mm": options.min_short_edge_mm,
        "target_short_edge_mm": options.target_short_edge_mm,
        "max_long_edge_mm": options.max_long_edge_mm,
        "mean_area_mm2": float(areas.mean()),
        "median_area_mm2": float(np.median(areas)),
        "aspect_ratio_percentiles": {
            str(percentile): float(np.percentile(aspects, percentile))
            for percentile in (5, 25, 50, 75, 95)
        },
        "warnings": warnings,
        "physical_scale": scale.model_dump(mode="json"),
        "settings": options.model_dump(mode="json"),
        "deterministic_signature": subdivision.deterministic_signature,
    }


def _palette_render(compiled: "CompiledTileMap") -> np.ndarray:
    source = compiled.source_rgb.astype(np.float64)
    gray = source.mean(axis=2, keepdims=True)
    rendered = np.clip(gray * 0.25 + 190.0, 0, 255).repeat(3, axis=2).astype(np.uint8)
    rendered[compiled.work_mask] = compiled.palette.rgb[
        compiled.tile_indices[compiled.work_mask]
    ].astype(np.uint8)
    return rendered
