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
from mosaic_agent.tile_map_export import export_compile_archive
from mosaic_agent.tile_map_models import PaletteCompileRequest, PaletteCompileResult, TesseraCompileOptions


TESSERA_FILES = {
    "tessera_map.png",
    "tessera_boundaries.png",
    "tessera.svg",
    "tessera.csv",
    "tessera_qa_report.json",
}

TESSERA_CSV_HEADERS = [
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


@pytest.fixture
def tessera_result(tmp_path: Path) -> PaletteCompileResult:
    source = np.zeros((60, 100, 3), dtype=np.uint8)
    source[:, :50] = (245, 45, 32)
    source[:, 50:] = (30, 70, 225)
    source_path = tmp_path / "source.png"
    Image.fromarray(source, "RGB").save(source_path)
    palette_path = tmp_path / "palette.json"
    palette_path.write_text(
        json.dumps(
            {
                "version": "test",
                "tiles": [
                    {
                        "tile_id": "red",
                        "name": "Red",
                        "hex": "#ff0000",
                        "inventory_level": "high",
                    },
                    {
                        "tile_id": "blue",
                        "name": "Blue",
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
        palette_db_path=str(palette_path),
        selected_palette_ids=["red", "blue"],
        granularity="coarse",
        target_region_count=24,
        min_region_area_px=4,
        boundary_smoothing="none",
        physical_width_cm=10.0,
        physical_height_cm=6.0,
        physical_scale_basis="full_image",
        tessera_options=TesseraCompileOptions(
            physical_scale_basis="full_image",
            min_short_edge_mm=4,
            target_short_edge_mm=12,
            max_long_edge_mm=45,
            preferred_aspect_ratio=1.8,
            random_seed=14,
        ),
        output_dir=str(tmp_path / "compiled"),
    )
    return compile_palette_map(request)


def test_enabled_compile_writes_all_tessera_artifacts(tessera_result):
    assert tessera_result.tessera_result is not None
    output = Path(tessera_result.qa_report_path).parent

    assert TESSERA_FILES <= {path.name for path in output.iterdir() if path.is_file()}
    for field in [
        "tessera_map_path",
        "tessera_boundaries_path",
        "tessera_svg_path",
        "tessera_csv_path",
        "tessera_qa_report_path",
    ]:
        assert Path(getattr(tessera_result.tessera_result, field)).is_file()


def test_tessera_pngs_match_palette_map_dimensions(tessera_result):
    assert tessera_result.tessera_result is not None
    with Image.open(tessera_result.palette_map_path) as palette_map:
        expected = palette_map.size
    with Image.open(tessera_result.tessera_result.tessera_map_path) as tessera_map:
        assert tessera_map.size == expected
    with Image.open(tessera_result.tessera_result.tessera_boundaries_path) as boundaries:
        assert boundaries.size == expected


def test_tessera_svg_contains_piece_and_parent_identity(tessera_result):
    assert tessera_result.tessera_result is not None
    root = ElementTree.parse(tessera_result.tessera_result.tessera_svg_path).getroot()
    groups = root.findall("svg:g", {"svg": "http://www.w3.org/2000/svg"})

    assert groups
    assert all("data-tessera-id" in group.attrib for group in groups)
    assert all("data-parent-region-id" in group.attrib for group in groups)
    assert all("data-tile-id" in group.attrib for group in groups)
    assert all(group.findall("svg:polygon", {"svg": "http://www.w3.org/2000/svg"}) for group in groups)


def test_tessera_csv_has_exact_contract_and_complete_area(tessera_result):
    assert tessera_result.tessera_result is not None
    with Path(tessera_result.tessera_result.tessera_csv_path).open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    assert list(rows[0]) == TESSERA_CSV_HEADERS
    assert sum(int(row["area_px"]) for row in rows) == tessera_result.masked_pixel_count


def test_tessera_qa_reports_passing_invariants(tessera_result):
    assert tessera_result.tessera_result is not None
    qa = json.loads(
        Path(tessera_result.tessera_result.tessera_qa_report_path).read_text(encoding="utf-8")
    )

    assert qa["tessera_count"] == tessera_result.tessera_result.tessera_count
    assert qa["color_region_count"] == tessera_result.region_count
    assert qa["area_sum_check"]["matches"] is True
    assert qa["outside_mask_pixel_count"] == 0
    assert qa["crosses_region_boundary_count"] == 0
    assert qa["tile_inheritance_check"]["matches"] is True
    assert qa["count_cap_check"]["matches"] is True
    assert len(qa["deterministic_signature"]) == 64


def test_compile_report_links_tessera_previews_and_files(tessera_result):
    report = Path(tessera_result.compile_report_html_path).read_text(encoding="utf-8")

    for filename in TESSERA_FILES:
        assert filename in report
    assert "Tessera subdivision" in report
    assert "Tessera QA summary" in report


def test_compile_archive_includes_tessera_artifacts(tessera_result, tmp_path):
    archive_path = export_compile_archive(tessera_result, tmp_path / "tessera-bundle")

    with zipfile.ZipFile(archive_path) as archive:
        assert TESSERA_FILES <= set(archive.namelist())
