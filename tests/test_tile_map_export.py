from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import numpy as np
import pytest
from PIL import Image

from mosaic_agent.palette_compiler import compile_palette_map
from mosaic_agent.tile_map_export import (
    DISCLAIMER,
    LEGEND_HEADERS,
    REGION_HEADERS,
    export_compile_archive,
)
from mosaic_agent.tile_map_models import PaletteCompileRequest, PaletteCompileResult


REQUIRED_FILES = {
    "source_image.png",
    "mask.png",
    "palette_map.png",
    "region_labels.png",
    "region_boundaries.png",
    "regions.svg",
    "legend.csv",
    "regions.csv",
    "qa_report.json",
    "compile_report.html",
    "compile_request.json",
}


@pytest.fixture
def compiled_result(tmp_path: Path) -> PaletteCompileResult:
    source = np.zeros((40, 64, 3), dtype=np.uint8)
    source[:, :32] = (242, 35, 30)
    source[:, 32:] = (20, 45, 238)
    source_path = tmp_path / "source.png"
    Image.fromarray(source, "RGB").save(source_path)

    mask = np.zeros((40, 64, 4), dtype=np.uint8)
    mask[:, 56:, 3] = 255
    mask_path = tmp_path / "mask.png"
    Image.fromarray(mask, "RGBA").save(mask_path)

    palette_path = tmp_path / "palette.json"
    palette_path.write_text(
        json.dumps(
            {
                "version": "test",
                "tiles": [
                    {
                        "tile_id": "red",
                        "name": "Studio Red",
                        "hex": "#ff0000",
                        "inventory_level": "high",
                    },
                    {
                        "tile_id": "blue",
                        "name": "Studio Blue",
                        "hex": "#0000ff",
                        "inventory_level": "high",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    request = PaletteCompileRequest(
        source_image_path=str(source_path),
        mask_image_path=str(mask_path),
        palette_db_path=str(palette_path),
        selected_palette_ids=["red", "blue"],
        granularity="coarse",
        target_region_count=30,
        min_region_area_px=4,
        boundary_smoothing="none",
        merge_tiny_regions=True,
        physical_width_cm=160.0,
        physical_height_cm=100.0,
        output_dir=str(tmp_path / "compiled"),
    )
    return compile_palette_map(request)


def test_compile_writes_complete_bundle(compiled_result):
    output = Path(compiled_result.qa_report_path).parent

    assert REQUIRED_FILES == {path.name for path in output.iterdir() if path.is_file()}


@pytest.mark.parametrize(
    "field",
    ["palette_map_path", "region_labels_path", "region_boundaries_path", "mask_image_path"],
)
def test_raster_artifacts_match_working_dimensions(compiled_result, field):
    with Image.open(getattr(compiled_result, field)) as image:
        assert image.size == (64, 40)


def test_normalized_mask_uses_transparent_work_and_opaque_outside(compiled_result):
    alpha = np.asarray(Image.open(compiled_result.mask_image_path).convert("RGBA"))[..., 3]

    assert (alpha[:, :56] == 0).all()
    assert (alpha[:, 56:] == 255).all()


def test_svg_contains_region_groups_and_polygon_geometry(compiled_result):
    root = ElementTree.parse(compiled_result.regions_svg_path).getroot()
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    groups = root.findall("svg:g", namespace)

    assert groups
    assert all("data-region-id" in group.attrib for group in groups)
    assert all("data-tile-id" in group.attrib for group in groups)
    assert all(group.findall("svg:polygon", namespace) for group in groups)


def test_legend_csv_has_exact_contract_and_area_sum(compiled_result):
    with Path(compiled_result.legend_csv_path).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert list(rows[0]) == LEGEND_HEADERS
    assert sum(int(row["pixel_count"]) for row in rows) == compiled_result.masked_pixel_count


def test_regions_csv_has_exact_contract_and_area_sum(compiled_result):
    with Path(compiled_result.regions_csv_path).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert list(rows[0]) == REGION_HEADERS
    assert sum(int(row["pixel_count"]) for row in rows) == compiled_result.masked_pixel_count


def test_qa_report_contains_signature_warnings_and_passing_checks(compiled_result):
    qa = json.loads(Path(compiled_result.qa_report_path).read_text(encoding="utf-8"))

    assert len(qa["deterministic_signature"]) == 64
    assert isinstance(qa["warnings"], list)
    assert qa["legend_area_sum_check"]["matches"] is True
    assert qa["region_area_sum_check"]["matches"] is True
    assert qa["colors_used_not_in_selected_palette"] == []


def test_compile_request_is_portable_json_record(compiled_result):
    request = json.loads(Path(compiled_result.compile_request_path).read_text(encoding="utf-8"))

    assert request["selected_palette_ids"] == ["red", "blue"]
    assert request["strict_palette"] is True
    assert request["physical_width_cm"] == 160.0


def test_compile_report_references_all_review_assets(compiled_result):
    report = Path(compiled_result.compile_report_html_path).read_text(encoding="utf-8")

    for asset in [
        "source_image.png",
        "mask.png",
        "palette_map.png",
        "region_labels.png",
        "region_boundaries.png",
        "regions.svg",
        "legend.csv",
        "regions.csv",
        "qa_report.json",
    ]:
        assert asset in report
    assert DISCLAIMER in report


def test_compile_report_contains_palette_legend_and_parameters(compiled_result):
    report = Path(compiled_result.compile_report_html_path).read_text(encoding="utf-8")

    assert "Studio Red" in report
    assert "Studio Blue" in report
    assert "selected_palette_ids" in report
    assert "QA warnings" in report


def test_compile_archive_contains_every_required_artifact(compiled_result, tmp_path):
    archive_path = export_compile_archive(compiled_result, tmp_path / "tile-map-bundle")

    with zipfile.ZipFile(archive_path) as archive:
        assert REQUIRED_FILES == set(archive.namelist())


def test_numbered_map_differs_from_flat_map_due_to_boundaries_and_labels(compiled_result):
    palette_map = np.asarray(Image.open(compiled_result.palette_map_path).convert("RGB"))
    labels = np.asarray(Image.open(compiled_result.region_labels_path).convert("RGB"))

    assert np.any(palette_map != labels)
