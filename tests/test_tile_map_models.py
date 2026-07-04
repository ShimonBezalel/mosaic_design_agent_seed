from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from mosaic_agent.tile_map_models import (
    ColorRegion,
    ColorUsage,
    PaletteCompileRequest,
    PaletteCompileResult,
    RegionRecord,
    TesseraCompileOptions,
    TesseraCompileResult,
    TesseraRecord,
)


@pytest.fixture
def valid_request_data(tmp_path: Path) -> dict[str, object]:
    source = tmp_path / "source.png"
    Image.new("RGB", (8, 6), "red").save(source)
    palette = tmp_path / "palette.json"
    palette.write_text(
        json.dumps(
            {
                "version": "1",
                "tiles": [
                    {
                        "tile_id": "red",
                        "name": "Red",
                        "hex": "#ff0000",
                        "inventory_level": "high",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return {
        "source_image_path": str(source),
        "palette_db_path": str(palette),
        "selected_palette_ids": ["red"],
        "granularity": "medium",
        "min_region_area_px": 8,
        "boundary_smoothing": "light",
        "merge_tiny_regions": True,
        "output_dir": str(tmp_path / "out"),
    }


def test_compile_request_defaults_to_strict_palette(valid_request_data):
    request = PaletteCompileRequest(**valid_request_data)

    assert request.strict_palette is True
    assert request.mask_image_path is None
    assert request.max_colors is None
    assert request.target_region_count is None
    assert request.color_compactness == 5.0
    assert request.minimum_color_area_cm2 is None
    assert request.tessera_options is None


@pytest.mark.parametrize("value", [0, -1])
def test_compile_request_rejects_non_positive_min_area(valid_request_data, value):
    with pytest.raises(ValidationError):
        PaletteCompileRequest(**(valid_request_data | {"min_region_area_px": value}))


@pytest.mark.parametrize("field", ["max_colors", "target_region_count"])
def test_compile_request_rejects_non_positive_limits(valid_request_data, field):
    with pytest.raises(ValidationError):
        PaletteCompileRequest(**(valid_request_data | {field: 0}))


def test_compile_request_rejects_non_strict_mode(valid_request_data):
    with pytest.raises(ValidationError, match="strict palette"):
        PaletteCompileRequest(**(valid_request_data | {"strict_palette": False}))


def test_compile_request_rejects_duplicate_selected_ids(valid_request_data):
    with pytest.raises(ValidationError, match="duplicate selected palette IDs"):
        PaletteCompileRequest(
            **(valid_request_data | {"selected_palette_ids": ["red", "red"]})
        )


def test_compile_request_requires_both_physical_dimensions(valid_request_data):
    with pytest.raises(ValidationError, match="physical dimensions"):
        PaletteCompileRequest(**(valid_request_data | {"physical_width_cm": 120.0}))


@pytest.mark.parametrize("field", ["source_image_path", "palette_db_path", "mask_image_path"])
def test_compile_request_rejects_missing_input_paths(valid_request_data, field, tmp_path):
    data = valid_request_data | {field: str(tmp_path / f"missing-{field}.png")}

    with pytest.raises(ValidationError, match="does not exist"):
        PaletteCompileRequest(**data)


def test_color_usage_serializes_tile_identity():
    usage = ColorUsage(
        tile_id="red",
        tile_name="Red",
        hex="#ff0000",
        pixel_count=10,
        percent_of_mask=100.0,
        region_count=1,
        mean_delta_e=0.0,
        max_delta_e=0.0,
    )

    assert usage.model_dump(mode="json")["tile_id"] == "red"
    assert usage.estimated_area_cm2 is None


def test_compile_result_serializes_nested_usage_and_regions(tmp_path):
    usage = ColorUsage(
        tile_id="red",
        tile_name="Red",
        hex="#ff0000",
        pixel_count=10,
        percent_of_mask=100.0,
        estimated_area_cm2=25.0,
        region_count=1,
        mean_delta_e=0.0,
        max_delta_e=0.0,
    )
    region = RegionRecord(
        region_id=1,
        tile_id="red",
        pixel_count=10,
        estimated_area_cm2=25.0,
        bbox_xyxy=(0, 0, 5, 2),
        centroid_xy=(2.0, 0.5),
        mean_source_rgb=(255.0, 0.0, 0.0),
        mean_source_lab=(53.24, 80.09, 67.20),
        delta_e=0.0,
        neighbor_region_ids=[],
    )
    result = PaletteCompileResult(
        run_id="abc123",
        source_image_path="source.png",
        mask_image_path="mask.png",
        palette_map_path="palette_map.png",
        region_labels_path="region_labels.png",
        region_boundaries_path="region_boundaries.png",
        regions_svg_path="regions.svg",
        legend_csv_path="legend.csv",
        regions_csv_path="regions.csv",
        qa_report_path="qa_report.json",
        compile_report_html_path="compile_report.html",
        compile_request_path="compile_request.json",
        region_count=1,
        color_count=1,
        masked_pixel_count=10,
        color_usage=[usage],
        regions=[region],
        warnings=[],
        parameters={"granularity": "medium"},
    )

    payload = result.model_dump(mode="json")
    assert payload["color_usage"][0]["tile_id"] == "red"
    assert payload["regions"][0]["bbox_xyxy"] == [0, 0, 5, 2]


def test_models_forbid_unrecognized_fields(valid_request_data):
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PaletteCompileRequest(**(valid_request_data | {"invent_colors": True}))


def test_region_record_remains_alias_for_color_region():
    assert RegionRecord is ColorRegion


def test_tessera_result_serializes_records_and_signature():
    record = TesseraRecord(
        tessera_id=1,
        parent_region_id=2,
        tile_id="red",
        polygon_xy=[(0.0, 0.0), (2.0, 0.0), (2.0, 1.0)],
        area_px=2,
        area_mm2=200.0,
        short_edge_mm_estimate=10.0,
        long_edge_mm_estimate=20.0,
        aspect_ratio=2.0,
        centroid_xy=(1.0, 0.5),
        orientation_degrees=0.0,
        warnings=[],
    )
    result = TesseraCompileResult(
        tessera_map_path="tessera_map.png",
        tessera_boundaries_path="tessera_boundaries.png",
        tessera_svg_path="tessera.svg",
        tessera_csv_path="tessera.csv",
        tessera_qa_report_path="tessera_qa_report.json",
        tessera_count=1,
        mean_area_mm2=200.0,
        median_area_mm2=200.0,
        min_area_mm2=200.0,
        max_area_mm2=200.0,
        mean_aspect_ratio=2.0,
        warnings=[],
        deterministic_signature="a" * 64,
        records=[record],
    )

    payload = result.model_dump(mode="json")
    assert payload["records"][0]["parent_region_id"] == 2
    assert payload["deterministic_signature"] == "a" * 64


def test_palette_result_defaults_to_no_tessera_result(tmp_path):
    usage = ColorUsage(
        tile_id="red",
        tile_name="Red",
        hex="#ff0000",
        pixel_count=1,
        percent_of_mask=100,
        region_count=1,
        mean_delta_e=0,
        max_delta_e=0,
    )
    region = RegionRecord(
        region_id=1,
        tile_id="red",
        pixel_count=1,
        bbox_xyxy=(0, 0, 1, 1),
        centroid_xy=(0, 0),
        mean_source_rgb=(255, 0, 0),
        mean_source_lab=(53, 80, 67),
        delta_e=0,
    )
    result = PaletteCompileResult(
        run_id="run",
        source_image_path="source.png",
        mask_image_path="mask.png",
        palette_map_path="palette.png",
        region_labels_path="labels.png",
        region_boundaries_path="boundaries.png",
        regions_svg_path="regions.svg",
        legend_csv_path="legend.csv",
        regions_csv_path="regions.csv",
        qa_report_path="qa.json",
        compile_report_html_path="report.html",
        compile_request_path="request.json",
        region_count=1,
        color_count=1,
        masked_pixel_count=1,
        color_usage=[usage],
        regions=[region],
        warnings=[],
        parameters={},
    )

    assert result.tessera_result is None


def test_palette_request_accepts_nested_tessera_options(valid_request_data):
    request = PaletteCompileRequest(
        **(
            valid_request_data
            | {
                "physical_width_cm": 200,
                "physical_height_cm": 100,
                "tessera_options": TesseraCompileOptions(random_seed=9),
            }
        )
    )

    assert request.tessera_options is not None
    assert request.tessera_options.random_seed == 9
