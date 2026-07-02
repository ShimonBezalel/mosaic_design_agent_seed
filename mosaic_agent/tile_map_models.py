from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from mosaic_agent.models import StrictModel


Granularity = Literal["coarse", "medium", "fine"]
BoundarySmoothing = Literal["none", "light", "medium"]


class PaletteCompileRequest(StrictModel):
    source_image_path: str
    mask_image_path: str | None = None
    palette_db_path: str
    selected_palette_ids: list[str] = Field(default_factory=list)
    max_colors: int | None = Field(default=None, ge=1)
    granularity: Granularity = "medium"
    target_region_count: int | None = Field(default=None, ge=1)
    min_region_area_px: int = Field(default=64, ge=1)
    boundary_smoothing: BoundarySmoothing = "light"
    merge_tiny_regions: bool = True
    strict_palette: bool = True
    physical_width_cm: float | None = Field(default=None, gt=0)
    physical_height_cm: float | None = Field(default=None, gt=0)
    output_dir: str

    @model_validator(mode="after")
    def validate_compile_inputs(self) -> "PaletteCompileRequest":
        if not self.strict_palette:
            raise ValueError("strict palette compilation is required")

        duplicates = sorted(
            tile_id
            for tile_id in set(self.selected_palette_ids)
            if self.selected_palette_ids.count(tile_id) > 1
        )
        if duplicates:
            raise ValueError(f"duplicate selected palette IDs: {', '.join(duplicates)}")

        has_width = self.physical_width_cm is not None
        has_height = self.physical_height_cm is not None
        if has_width != has_height:
            raise ValueError("physical dimensions require both width and height")

        paths = {
            "source image": self.source_image_path,
            "palette DB": self.palette_db_path,
        }
        if self.mask_image_path is not None:
            paths["mask image"] = self.mask_image_path
        for label, value in paths.items():
            if not Path(value).is_file():
                raise ValueError(f"{label} does not exist: {value}")
        return self


class ColorUsage(StrictModel):
    tile_id: str
    tile_name: str
    hex: str
    pixel_count: int = Field(ge=0)
    percent_of_mask: float = Field(ge=0, le=100)
    estimated_area_cm2: float | None = Field(default=None, ge=0)
    region_count: int = Field(ge=0)
    mean_delta_e: float = Field(ge=0)
    max_delta_e: float = Field(ge=0)


class RegionRecord(StrictModel):
    region_id: int = Field(ge=1)
    tile_id: str
    pixel_count: int = Field(ge=1)
    estimated_area_cm2: float | None = Field(default=None, ge=0)
    bbox_xyxy: tuple[int, int, int, int]
    centroid_xy: tuple[float, float]
    mean_source_rgb: tuple[float, float, float]
    mean_source_lab: tuple[float, float, float]
    delta_e: float = Field(ge=0)
    neighbor_region_ids: list[int] = Field(default_factory=list)


class PaletteCompileResult(StrictModel):
    run_id: str
    source_image_path: str
    mask_image_path: str
    palette_map_path: str
    region_labels_path: str
    region_boundaries_path: str
    regions_svg_path: str
    legend_csv_path: str
    regions_csv_path: str
    qa_report_path: str
    compile_report_html_path: str
    compile_request_path: str
    region_count: int = Field(ge=0)
    color_count: int = Field(ge=0)
    masked_pixel_count: int = Field(ge=1)
    color_usage: list[ColorUsage]
    regions: list[RegionRecord]
    warnings: list[str]
    parameters: dict[str, object]
