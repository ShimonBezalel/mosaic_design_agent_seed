from __future__ import annotations

import csv
import html
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from skimage.measure import find_contours
from skimage.segmentation import find_boundaries

from mosaic_agent.tile_map_models import (
    PaletteCompileRequest,
    PaletteCompileResult,
    TesseraCompileResult,
)

if TYPE_CHECKING:
    from mosaic_agent.palette_compiler import CompiledTileMap


DISCLAIMER = "Generated maps are planning aids. They are not construction-ready without artist review."

LEGEND_HEADERS = [
    "tile_id",
    "tile_name",
    "hex",
    "pixel_count",
    "percent_of_mask",
    "estimated_area_cm2",
    "region_count",
    "mean_delta_e",
    "max_delta_e",
]

REGION_HEADERS = [
    "region_id",
    "tile_id",
    "pixel_count",
    "estimated_area_cm2",
    "bbox_x1",
    "bbox_y1",
    "bbox_x2",
    "bbox_y2",
    "centroid_x",
    "centroid_y",
    "delta_e",
    "neighbor_region_ids",
]


@dataclass(frozen=True)
class ArtifactPaths:
    source_image: Path
    mask_image: Path
    palette_map: Path
    region_labels: Path
    region_boundaries: Path
    regions_svg: Path
    legend_csv: Path
    regions_csv: Path
    qa_report: Path
    compile_report_html: Path
    compile_request: Path
    tessera_result: TesseraCompileResult | None = None


def write_compile_artifacts(
    compiled: "CompiledTileMap",
    *,
    request: PaletteCompileRequest,
    qa_report: dict[str, object],
    output_dir: Path,
) -> ArtifactPaths:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = ArtifactPaths(
        source_image=output_dir / "source_image.png",
        mask_image=output_dir / "mask.png",
        palette_map=output_dir / "palette_map.png",
        region_labels=output_dir / "region_labels.png",
        region_boundaries=output_dir / "region_boundaries.png",
        regions_svg=output_dir / "regions.svg",
        legend_csv=output_dir / "legend.csv",
        regions_csv=output_dir / "regions.csv",
        qa_report=output_dir / "qa_report.json",
        compile_report_html=output_dir / "compile_report.html",
        compile_request=output_dir / "compile_request.json",
    )
    Image.fromarray(compiled.source_rgb.astype(np.uint8), "RGB").save(paths.source_image)
    _write_mask(compiled.work_mask, paths.mask_image)
    palette_image = render_palette_map(compiled)
    palette_image.save(paths.palette_map)
    render_region_labels(compiled, palette_image).save(paths.region_labels)
    render_boundary_overlay(compiled).save(paths.region_boundaries)
    write_regions_svg(compiled, paths.regions_svg)
    write_legend_csv(compiled, paths.legend_csv)
    write_regions_csv(compiled, paths.regions_csv)
    _write_json(paths.qa_report, qa_report)
    _write_json(paths.compile_request, request.model_dump(mode="json"))
    tessera_result = None
    if compiled.tessera_subdivision is not None:
        if compiled.physical_scale is None or request.tessera_options is None:
            raise ValueError("tessera artifact export requires scale and options")
        from mosaic_agent.tessera_export import write_tessera_artifacts

        tessera_result = write_tessera_artifacts(
            compiled,
            compiled.tessera_subdivision,
            compiled.physical_scale,
            request.tessera_options,
            output_dir,
        )
    write_compile_report(
        compiled,
        qa_report,
        paths.compile_report_html,
        tessera_result=tessera_result,
    )
    return ArtifactPaths(
        source_image=paths.source_image,
        mask_image=paths.mask_image,
        palette_map=paths.palette_map,
        region_labels=paths.region_labels,
        region_boundaries=paths.region_boundaries,
        regions_svg=paths.regions_svg,
        legend_csv=paths.legend_csv,
        regions_csv=paths.regions_csv,
        qa_report=paths.qa_report,
        compile_report_html=paths.compile_report_html,
        compile_request=paths.compile_request,
        tessera_result=tessera_result,
    )


def render_palette_map(compiled: "CompiledTileMap") -> Image.Image:
    source = compiled.source_rgb.astype(np.float64)
    gray = source.mean(axis=2, keepdims=True)
    outside = np.clip(gray * 0.25 + 190.0, 0, 255).repeat(3, axis=2).astype(np.uint8)
    rendered = outside
    palette_rgb = compiled.palette.rgb.astype(np.uint8)
    rendered[compiled.work_mask] = palette_rgb[compiled.tile_indices[compiled.work_mask]]
    return Image.fromarray(rendered, "RGB")


def render_region_labels(
    compiled: "CompiledTileMap",
    palette_image: Image.Image,
) -> Image.Image:
    rendered = palette_image.copy()
    draw = ImageDraw.Draw(rendered)
    boundaries = find_boundaries(compiled.region_ids, mode="inner") & compiled.work_mask
    boundary_pixels = np.asarray(rendered).copy()
    boundary_pixels[boundaries] = (24, 24, 24)
    rendered = Image.fromarray(boundary_pixels, "RGB")
    draw = ImageDraw.Draw(rendered)
    size = max(10, min(28, round(min(rendered.size) / 24)))
    try:
        font = ImageFont.load_default(size=size)
    except TypeError:
        font = ImageFont.load_default()
    for region in compiled.regions:
        x, y = region.centroid_xy
        text = str(region.region_id)
        draw.text(
            (x, y),
            text,
            fill="white",
            stroke_width=max(1, size // 8),
            stroke_fill="black",
            font=font,
            anchor="mm",
        )
    return rendered


def render_boundary_overlay(compiled: "CompiledTileMap") -> Image.Image:
    rendered = compiled.source_rgb.copy()
    boundaries = find_boundaries(compiled.region_ids, mode="thick") & compiled.work_mask
    rendered[boundaries] = (20, 20, 20)
    return Image.fromarray(rendered.astype(np.uint8), "RGB")


def write_regions_svg(compiled: "CompiledTileMap", path: Path) -> None:
    width = compiled.source_rgb.shape[1]
    height = compiled.source_rgb.shape[0]
    tile_by_id = {tile.tile_id: tile for tile in compiled.palette.tiles}
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">'
        ),
        f"  <desc>{html.escape(DISCLAIMER)}</desc>",
    ]
    for region in compiled.regions:
        fill = f"#{tile_by_id[region.tile_id].hex.lstrip('#').lower()}"
        lines.append(
            f'  <g data-region-id="{region.region_id}" data-tile-id="{html.escape(region.tile_id)}" '
            f'fill="{fill}" stroke="#202020" stroke-width="1">'
        )
        padded = np.pad(compiled.region_ids == region.region_id, 1, constant_values=False)
        contours = find_contours(padded.astype(np.uint8), 0.5)
        for contour in contours:
            points = " ".join(
                f"{point[1] - 1:.2f},{point[0] - 1:.2f}" for point in contour
            )
            lines.append(f'    <polygon points="{points}" />')
        lines.append("  </g>")
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_legend_csv(compiled: "CompiledTileMap", path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEGEND_HEADERS)
        writer.writeheader()
        for usage in compiled.color_usage:
            writer.writerow(usage.model_dump(mode="json"))


def write_regions_csv(compiled: "CompiledTileMap", path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REGION_HEADERS)
        writer.writeheader()
        for region in compiled.regions:
            x1, y1, x2, y2 = region.bbox_xyxy
            centroid_x, centroid_y = region.centroid_xy
            writer.writerow(
                {
                    "region_id": region.region_id,
                    "tile_id": region.tile_id,
                    "pixel_count": region.pixel_count,
                    "estimated_area_cm2": region.estimated_area_cm2,
                    "bbox_x1": x1,
                    "bbox_y1": y1,
                    "bbox_x2": x2,
                    "bbox_y2": y2,
                    "centroid_x": centroid_x,
                    "centroid_y": centroid_y,
                    "delta_e": region.delta_e,
                    "neighbor_region_ids": ";".join(map(str, region.neighbor_region_ids)),
                }
            )


def write_compile_report(
    compiled: "CompiledTileMap",
    qa_report: dict[str, object],
    path: Path,
    *,
    tessera_result: TesseraCompileResult | None = None,
) -> None:
    warning_items = "".join(
        f"<li>{html.escape(str(warning))}</li>" for warning in qa_report["warnings"]
    ) or "<li>No QA warnings.</li>"
    legend_rows = "".join(
        "<tr>"
        f"<td><span class='swatch' style='background:{html.escape(item.hex)}'></span></td>"
        f"<td>{html.escape(item.tile_id)}</td>"
        f"<td>{html.escape(item.tile_name)}</td>"
        f"<td>{item.pixel_count}</td>"
        f"<td>{item.percent_of_mask:.2f}%</td>"
        f"<td>{'' if item.estimated_area_cm2 is None else f'{item.estimated_area_cm2:.2f}'}</td>"
        f"<td>{item.region_count}</td>"
        f"<td>{item.mean_delta_e:.2f}</td>"
        "</tr>"
        for item in compiled.color_usage
    )
    parameters = html.escape(json.dumps(qa_report["parameters"], indent=2, sort_keys=True))
    tessera_section = ""
    if tessera_result is not None:
        tessera_section = f"""
  <h2>Tessera subdivision</h2>
  <div class="images">
    <figure><img src="tessera_map.png" alt="Palette tessera map"><figcaption>Palette tessera map</figcaption></figure>
    <figure><img src="tessera_boundaries.png" alt="Tessera boundary overlay"><figcaption>Tessera boundaries on source</figcaption></figure>
  </div>
  <h3>Tessera QA summary</h3>
  <p>{tessera_result.tessera_count} tesserae; mean area {tessera_result.mean_area_mm2:.2f} mm2; mean aspect ratio {tessera_result.mean_aspect_ratio:.2f}.</p>
  <ul>
    <li><a href="tessera.svg">Tessera contours (SVG)</a></li>
    <li><a href="tessera.csv">Tessera records (CSV)</a></li>
    <li><a href="tessera_qa_report.json">Tessera QA report (JSON)</a></li>
  </ul>
"""
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mosaic tile map compile report</title>
  <style>
    body {{ font: 15px/1.45 system-ui, sans-serif; margin: 0 auto; max-width: 1200px; padding: 24px; color: #202020; }}
    .warning {{ border-left: 5px solid #b42318; background: #fff1f0; padding: 12px 16px; }}
    .images {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }}
    figure {{ margin: 0; }} img {{ width: 100%; height: auto; border: 1px solid #bbb; }}
    table {{ border-collapse: collapse; width: 100%; }} th, td {{ border: 1px solid #bbb; padding: 6px; text-align: left; }}
    .swatch {{ display: inline-block; width: 28px; height: 20px; border: 1px solid #555; }}
    pre {{ overflow: auto; background: #f4f4f4; padding: 12px; }}
  </style>
</head>
<body>
  <h1>Mosaic tile map compile report</h1>
  <p class="warning"><strong>{html.escape(DISCLAIMER)}</strong></p>
  <h2>Inputs and maps</h2>
  <div class="images">
    <figure><img src="source_image.png" alt="Source image"><figcaption>Source image</figcaption></figure>
    <figure><img src="mask.png" alt="Normalized work mask"><figcaption>Normalized work mask</figcaption></figure>
    <figure><img src="palette_map.png" alt="Flat palette map"><figcaption>Flat palette map</figcaption></figure>
    <figure><img src="region_labels.png" alt="Numbered region map"><figcaption>Numbered region map</figcaption></figure>
    <figure><img src="region_boundaries.png" alt="Region boundaries"><figcaption>Boundary overlay</figcaption></figure>
  </div>
  {tessera_section}
  <h2>QA warnings</h2><ul>{warning_items}</ul>
  <h2>Tile legend</h2>
  <table><thead><tr><th>Color</th><th>Tile ID</th><th>Name</th><th>Pixels</th><th>Mask</th><th>Area cm2</th><th>Regions</th><th>Mean Delta E</th></tr></thead><tbody>{legend_rows}</tbody></table>
  <h2>Planning files</h2>
  <ul>
    <li><a href="regions.svg">Region contours (SVG)</a></li>
    <li><a href="legend.csv">Tile legend (CSV)</a></li>
    <li><a href="regions.csv">Region records (CSV)</a></li>
    <li><a href="qa_report.json">QA report (JSON)</a></li>
    <li><a href="compile_request.json">Compile request (JSON)</a></li>
  </ul>
  <h2>Parameters</h2><pre>{parameters}</pre>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def export_compile_archive(
    result: PaletteCompileResult,
    archive_path: str | Path,
) -> Path:
    destination = Path(archive_path)
    if destination.suffix.lower() != ".zip":
        destination = destination.with_suffix(".zip")
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_dir = Path(result.qa_report_path).parent
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(source_dir.iterdir(), key=lambda item: item.name):
            if source.is_file():
                archive.write(source, arcname=source.name)
    return destination


def _write_mask(work_mask: np.ndarray, path: Path) -> None:
    height, width = work_mask.shape
    mask = np.zeros((height, width, 4), dtype=np.uint8)
    mask[..., 3] = np.where(work_mask, 0, 255).astype(np.uint8)
    Image.fromarray(mask, "RGBA").save(path)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
