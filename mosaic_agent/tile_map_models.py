from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from mosaic_agent.models import StrictModel


Granularity = Literal["coarse", "medium", "fine"]
BoundarySmoothing = Literal["none", "light", "medium"]
PhysicalScaleBasis = Literal["full_image", "mask_bbox"]
FlowStrength = Literal["none", "low", "medium", "high"]
EdgeFollowing = Literal["low", "medium", "high"]
ShapeStyle = Literal["irregular", "angular", "smooth", "slivered"]


class PhysicalScale(StrictModel):
    image_width_px: int = Field(ge=1)
    image_height_px: int = Field(ge=1)
    physical_width_mm: float = Field(gt=0)
    physical_height_mm: float = Field(gt=0)
    mm_per_px_x: float = Field(gt=0)
    mm_per_px_y: float = Field(gt=0)
    px_per_mm_x: float = Field(gt=0)
    px_per_mm_y: float = Field(gt=0)
    scale_basis: PhysicalScaleBasis


class TesseraCompileOptions(StrictModel):
    physical_scale_basis: PhysicalScaleBasis = "mask_bbox"
    min_short_edge_mm: float = Field(default=8.0, gt=0)
    target_short_edge_mm: float = Field(default=18.0, gt=0)
    max_long_edge_mm: float = Field(default=55.0, gt=0)
    preferred_aspect_ratio: float = Field(default=1.8, ge=1)
    max_aspect_ratio: float = Field(default=4.0, ge=1)
    flow_strength: FlowStrength = "medium"
    edge_following: EdgeFollowing = "medium"
    shape_style: ShapeStyle = "irregular"
    random_seed: int = 0
    grout_width_mm: float = Field(default=2.0, ge=0)
    max_tessera_count: int = Field(default=3000, ge=1, le=10000)

    @model_validator(mode="after")
    def validate_physical_ordering(self) -> "TesseraCompileOptions":
        if self.min_short_edge_mm > self.target_short_edge_mm:
            raise ValueError("physical edge ordering requires minimum <= target")
        if self.target_short_edge_mm > self.max_long_edge_mm:
            raise ValueError("physical edge ordering requires target <= maximum long edge")
        if self.preferred_aspect_ratio > self.max_aspect_ratio:
            raise ValueError("aspect ordering requires preferred <= maximum")
        return self


class PaletteCompileRequest(StrictModel):
    source_image_path: str
    mask_image_path: str | None = None
    palette_db_path: str
    selected_palette_ids: list[str] = Field(default_factory=list)
    max_colors: int | None = Field(default=None, ge=1)
    granularity: Granularity = "medium"
    target_region_count: int | None = Field(default=None, ge=1)
    min_region_area_px: int = Field(default=64, ge=1)
    minimum_color_area_cm2: float | None = Field(default=None, gt=0)
    color_compactness: float = Field(default=5.0, gt=0)
    boundary_smoothing: BoundarySmoothing = "light"
    merge_tiny_regions: bool = True
    strict_palette: bool = True
    physical_width_cm: float | None = Field(default=None, gt=0)
    physical_height_cm: float | None = Field(default=None, gt=0)
    physical_scale_basis: PhysicalScaleBasis = "mask_bbox"
    tessera_options: TesseraCompileOptions | None = None
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
        if self.tessera_options is not None and not (has_width and has_height):
            raise ValueError("tessera subdivision requires positive physical dimensions")
        if self.minimum_color_area_cm2 is not None and not (has_width and has_height):
            raise ValueError("minimum color area in cm2 requires positive physical dimensions")

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


class ColorRegion(StrictModel):
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


RegionRecord = ColorRegion


class TesseraCompileRequest(StrictModel):
    source_image_path: str
    mask_image_path: str | None = None
    palette_map_path: str | None = None
    region_id_map_path: str | None = None
    palette_db_path: str
    selected_palette_ids: list[str] = Field(default_factory=list)
    physical_width_cm: float = Field(gt=0)
    physical_height_cm: float = Field(gt=0)
    physical_scale_basis: PhysicalScaleBasis = "mask_bbox"
    min_short_edge_mm: float = Field(default=8.0, gt=0)
    target_short_edge_mm: float = Field(default=18.0, gt=0)
    max_long_edge_mm: float = Field(default=55.0, gt=0)
    max_aspect_ratio: float = Field(default=4.0, ge=1)
    preferred_aspect_ratio: float = Field(default=1.8, ge=1)
    flow_strength: FlowStrength = "medium"
    edge_following: EdgeFollowing = "medium"
    shape_style: ShapeStyle = "irregular"
    random_seed: int = 0
    grout_width_mm: float = Field(default=2.0, ge=0)
    max_tessera_count: int = Field(default=3000, ge=1, le=10000)
    output_dir: str

    @model_validator(mode="after")
    def validate_tessera_request(self) -> "TesseraCompileRequest":
        TesseraCompileOptions(
            physical_scale_basis=self.physical_scale_basis,
            min_short_edge_mm=self.min_short_edge_mm,
            target_short_edge_mm=self.target_short_edge_mm,
            max_long_edge_mm=self.max_long_edge_mm,
            max_aspect_ratio=self.max_aspect_ratio,
            preferred_aspect_ratio=self.preferred_aspect_ratio,
            flow_strength=self.flow_strength,
            edge_following=self.edge_following,
            shape_style=self.shape_style,
            random_seed=self.random_seed,
            grout_width_mm=self.grout_width_mm,
            max_tessera_count=self.max_tessera_count,
        )
        paths = {
            "source image": self.source_image_path,
            "palette DB": self.palette_db_path,
        }
        if self.mask_image_path is not None:
            paths["mask image"] = self.mask_image_path
        if self.palette_map_path is not None:
            paths["palette map"] = self.palette_map_path
        if self.region_id_map_path is not None:
            paths["region ID map"] = self.region_id_map_path
        for label, value in paths.items():
            if not Path(value).is_file():
                raise ValueError(f"{label} does not exist: {value}")
        return self


class TesseraRecord(StrictModel):
    tessera_id: int = Field(ge=1)
    parent_region_id: int = Field(ge=1)
    tile_id: str
    polygon_xy: list[tuple[float, float]] = Field(min_length=3)
    area_px: int = Field(ge=1)
    area_mm2: float = Field(gt=0)
    short_edge_mm_estimate: float = Field(ge=0)
    long_edge_mm_estimate: float = Field(ge=0)
    aspect_ratio: float = Field(ge=1)
    centroid_xy: tuple[float, float]
    orientation_degrees: float
    warnings: list[str] = Field(default_factory=list)


class TesseraCompileResult(StrictModel):
    tessera_map_path: str
    tessera_boundaries_path: str
    tessera_svg_path: str
    tessera_csv_path: str
    tessera_qa_report_path: str
    tessera_count: int = Field(ge=1)
    mean_area_mm2: float = Field(gt=0)
    median_area_mm2: float = Field(gt=0)
    min_area_mm2: float = Field(gt=0)
    max_area_mm2: float = Field(gt=0)
    mean_aspect_ratio: float = Field(ge=1)
    warnings: list[str] = Field(default_factory=list)
    deterministic_signature: str
    records: list[TesseraRecord] = Field(default_factory=list)


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
    tessera_result: TesseraCompileResult | None = None
