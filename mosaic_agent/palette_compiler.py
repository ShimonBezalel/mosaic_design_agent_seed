from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from mosaic_agent.load import load_palette
from mosaic_agent.region_map import (
    PaletteArrays,
    build_palette_arrays,
    build_region_records,
    create_initial_tile_map,
    label_tile_components,
    load_source_rgb,
    load_work_area,
    merge_tiny_tile_regions,
    nearest_palette_indices,
    smooth_source_lab,
)
from mosaic_agent.tile_map_models import (
    ColorUsage,
    PaletteCompileRequest,
    PaletteCompileResult,
    RegionRecord,
)


@dataclass(frozen=True)
class CompiledTileMap:
    source_rgb: np.ndarray
    work_mask: np.ndarray
    tile_indices: np.ndarray
    region_ids: np.ndarray
    palette: PaletteArrays
    regions: tuple[RegionRecord, ...]
    color_usage: tuple[ColorUsage, ...]


def compile_palette_map(request: PaletteCompileRequest) -> PaletteCompileResult:
    palette_db = load_palette(request.palette_db_path)
    selected_palette = build_palette_arrays(palette_db, request.selected_palette_ids)
    source = load_source_rgb(request.source_image_path)
    work_mask = load_work_area(request.mask_image_path, source.working_size)
    masked_pixel_count = int(work_mask.sum())
    if masked_pixel_count == 0:
        raise ValueError("Mask has no editable pixels.")

    source_lab = smooth_source_lab(source.rgb, request.boundary_smoothing)
    initial = create_initial_tile_map(
        source.rgb,
        work_mask,
        selected_palette,
        granularity=request.granularity,
        target_region_count=request.target_region_count,
        boundary_smoothing=request.boundary_smoothing,
    )
    effective_palette, initial_tiles, dropped_ids = _apply_max_colors(
        palette_db,
        selected_palette,
        initial.segment_labels,
        initial.tile_indices,
        source_lab,
        work_mask,
        request.max_colors,
    )

    warnings: list[str] = []
    if source.scale < 1.0:
        warnings.append(
            "Source image was resized from "
            f"{source.original_size[0]}x{source.original_size[1]} to "
            f"{source.working_size[0]}x{source.working_size[1]} for compilation."
        )
    if initial.fallback_used:
        warnings.append("SLIC segmentation failed; deterministic grid segmentation was used.")
    if dropped_ids:
        warnings.append(
            "max_colors removed selected palette colors with lower source demand: "
            + ", ".join(dropped_ids)
        )

    if request.merge_tiny_regions:
        cleanup = merge_tiny_tile_regions(
            initial_tiles,
            work_mask,
            source_lab,
            effective_palette.lab,
            request.min_region_area_px,
        )
        final_tiles = cleanup.tile_indices
        region_ids = cleanup.region_ids
        warnings.extend(cleanup.warnings)
    else:
        final_tiles = initial_tiles.copy()
        final_tiles[~work_mask] = -1
        region_ids = label_tile_components(final_tiles, work_mask)

    pixel_area_cm2 = _pixel_area_cm2(request, source.working_size)
    regions = build_region_records(
        region_ids,
        final_tiles,
        source.rgb,
        source_lab,
        effective_palette,
        pixel_area_cm2,
    )
    color_usage = _build_color_usage(
        regions,
        effective_palette,
        masked_pixel_count,
        pixel_area_cm2,
    )
    if request.physical_width_cm is None:
        warnings.append("Physical dimensions were not provided; area estimates were skipped.")
    if len(regions) > 600:
        warnings.append(
            "Compilation produced too many regions for easy labeling; try coarser granularity "
            "or a larger minimum region area."
        )
    warnings = list(dict.fromkeys(warnings))

    selected_ids = [tile.tile_id for tile in selected_palette.tiles]
    effective_ids = [tile.tile_id for tile in effective_palette.tiles]
    parameters = _parameters(
        request,
        selected_ids=selected_ids,
        effective_ids=effective_ids,
        original_size=source.original_size,
        working_size=source.working_size,
        working_scale=source.scale,
        segment_target=initial.target_count,
    )
    signature = _deterministic_signature(
        final_tiles,
        region_ids,
        work_mask,
        parameters,
    )
    run_id = signature[:12]
    tiny_regions = [
        region.region_id for region in regions if region.pixel_count < request.min_region_area_px
    ]
    used_ids = {usage.tile_id for usage in color_usage}
    qa_report: dict[str, object] = {
        "masked_pixel_count": masked_pixel_count,
        "region_count": len(regions),
        "color_count": len(color_usage),
        "parameters": parameters,
        "warnings": warnings,
        "worst_regions_by_delta_e": [
            region.model_dump(mode="json")
            for region in sorted(regions, key=lambda item: (-item.delta_e, item.region_id))[:10]
        ],
        "tiny_regions_remaining": tiny_regions,
        "colors_used_not_in_selected_palette": sorted(used_ids - set(selected_ids)),
        "legend_area_sum_check": {
            "expected": masked_pixel_count,
            "actual": sum(item.pixel_count for item in color_usage),
            "matches": sum(item.pixel_count for item in color_usage) == masked_pixel_count,
        },
        "region_area_sum_check": {
            "expected": masked_pixel_count,
            "actual": sum(item.pixel_count for item in regions),
            "matches": sum(item.pixel_count for item in regions) == masked_pixel_count,
        },
        "original_dimensions": list(source.original_size),
        "working_dimensions": list(source.working_size),
        "working_scale": source.scale,
        "deterministic_signature": signature,
    }

    compiled = CompiledTileMap(
        source_rgb=source.rgb,
        work_mask=work_mask,
        tile_indices=final_tiles,
        region_ids=region_ids,
        palette=effective_palette,
        regions=tuple(regions),
        color_usage=tuple(color_usage),
    )
    from mosaic_agent.tile_map_export import write_compile_artifacts

    artifacts = write_compile_artifacts(
        compiled,
        request=request,
        qa_report=qa_report,
        output_dir=Path(request.output_dir),
    )
    return PaletteCompileResult(
        run_id=run_id,
        source_image_path=str(artifacts.source_image),
        mask_image_path=str(artifacts.mask_image),
        palette_map_path=str(artifacts.palette_map),
        region_labels_path=str(artifacts.region_labels),
        region_boundaries_path=str(artifacts.region_boundaries),
        regions_svg_path=str(artifacts.regions_svg),
        legend_csv_path=str(artifacts.legend_csv),
        regions_csv_path=str(artifacts.regions_csv),
        qa_report_path=str(artifacts.qa_report),
        compile_report_html_path=str(artifacts.compile_report_html),
        compile_request_path=str(artifacts.compile_request),
        region_count=len(regions),
        color_count=len(color_usage),
        masked_pixel_count=masked_pixel_count,
        color_usage=color_usage,
        regions=regions,
        warnings=warnings,
        parameters=parameters,
    )


def _apply_max_colors(
    palette_db,
    selected_palette: PaletteArrays,
    segment_labels: np.ndarray,
    initial_tiles: np.ndarray,
    source_lab: np.ndarray,
    work_mask: np.ndarray,
    max_colors: int | None,
) -> tuple[PaletteArrays, np.ndarray, list[str]]:
    if max_colors is None or max_colors >= len(selected_palette.tiles):
        return selected_palette, initial_tiles.copy(), []

    demand = np.bincount(
        initial_tiles[work_mask],
        minlength=len(selected_palette.tiles),
    )
    ranked_indices = sorted(
        range(len(selected_palette.tiles)),
        key=lambda index: (-int(demand[index]), selected_palette.tiles[index].tile_id),
    )
    retained_ids = {
        selected_palette.tiles[index].tile_id for index in ranked_indices[:max_colors]
    }
    dropped_ids = sorted(
        tile.tile_id for tile in selected_palette.tiles if tile.tile_id not in retained_ids
    )
    effective = build_palette_arrays(palette_db, sorted(retained_ids))
    reassigned = np.full(initial_tiles.shape, -1, dtype=np.int32)
    segment_ids = np.unique(segment_labels[work_mask])
    segment_means = np.asarray(
        [source_lab[segment_labels == segment_id].mean(axis=0) for segment_id in segment_ids]
    )
    assigned, _ = nearest_palette_indices(segment_means, effective.lab)
    for segment_id, tile_index in zip(segment_ids, assigned, strict=True):
        reassigned[segment_labels == segment_id] = int(tile_index)
    reassigned[~work_mask] = -1
    return effective, reassigned, dropped_ids


def _pixel_area_cm2(
    request: PaletteCompileRequest,
    working_size: tuple[int, int],
) -> float | None:
    if request.physical_width_cm is None or request.physical_height_cm is None:
        return None
    return (request.physical_width_cm * request.physical_height_cm) / (
        working_size[0] * working_size[1]
    )


def _build_color_usage(
    regions: list[RegionRecord],
    palette: PaletteArrays,
    masked_pixel_count: int,
    pixel_area_cm2: float | None,
) -> list[ColorUsage]:
    by_tile: dict[str, list[RegionRecord]] = {}
    for region in regions:
        by_tile.setdefault(region.tile_id, []).append(region)
    tile_by_id = {tile.tile_id: (index, tile) for index, tile in enumerate(palette.tiles)}
    usage: list[ColorUsage] = []
    for tile_id in sorted(by_tile):
        tile_regions = by_tile[tile_id]
        pixel_count = sum(region.pixel_count for region in tile_regions)
        _, tile = tile_by_id[tile_id]
        usage.append(
            ColorUsage(
                tile_id=tile_id,
                tile_name=tile.name,
                hex=_canonical_hex(tile.hex),
                pixel_count=pixel_count,
                percent_of_mask=100.0 * pixel_count / masked_pixel_count,
                estimated_area_cm2=(
                    pixel_count * pixel_area_cm2 if pixel_area_cm2 is not None else None
                ),
                region_count=len(tile_regions),
                mean_delta_e=(
                    sum(region.delta_e * region.pixel_count for region in tile_regions)
                    / pixel_count
                ),
                max_delta_e=max(region.delta_e for region in tile_regions),
            )
        )
    return usage


def _canonical_hex(value: str) -> str:
    return f"#{value.lstrip('#').lower()}"


def _parameters(
    request: PaletteCompileRequest,
    *,
    selected_ids: list[str],
    effective_ids: list[str],
    original_size: tuple[int, int],
    working_size: tuple[int, int],
    working_scale: float,
    segment_target: int,
) -> dict[str, object]:
    return {
        "selected_palette_ids": selected_ids,
        "effective_palette_ids": effective_ids,
        "max_colors": request.max_colors,
        "granularity": request.granularity,
        "target_region_count": request.target_region_count,
        "segment_target": segment_target,
        "min_region_area_px": request.min_region_area_px,
        "boundary_smoothing": request.boundary_smoothing,
        "merge_tiny_regions": request.merge_tiny_regions,
        "strict_palette": request.strict_palette,
        "physical_width_cm": request.physical_width_cm,
        "physical_height_cm": request.physical_height_cm,
        "original_dimensions": list(original_size),
        "working_dimensions": list(working_size),
        "working_scale": working_scale,
    }


def _deterministic_signature(
    tile_indices: np.ndarray,
    region_ids: np.ndarray,
    work_mask: np.ndarray,
    parameters: dict[str, object],
) -> str:
    digest = hashlib.sha256()
    digest.update(np.asarray(tile_indices, dtype="<i4").tobytes(order="C"))
    digest.update(np.asarray(region_ids, dtype="<i4").tobytes(order="C"))
    digest.update(np.asarray(work_mask, dtype=np.uint8).tobytes(order="C"))
    digest.update(json.dumps(parameters, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return digest.hexdigest()
