from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from mosaic_agent.load import load_brief, load_palette
from mosaic_agent.session_models import InteractiveSession
from mosaic_workbench.controllers import compile_session_tile_map
from mosaic_workbench.export import export_session


ROOT = Path(__file__).resolve().parents[1]
PALETTE_PATH = ROOT / "examples" / "palette_db.example.json"


def make_session_and_source(tmp_path: Path) -> tuple[InteractiveSession, Path]:
    brief = load_brief(ROOT / "examples" / "project_brief.example.json")
    palette = load_palette(PALETTE_PATH)
    source = np.zeros((84, 84, 3), dtype=np.uint8)
    source[:, :42] = (205, 92, 44)
    source[:, 42:] = (36, 84, 148)
    source_path = tmp_path / "accepted.png"
    Image.fromarray(source, "RGB").save(source_path)
    session = InteractiveSession(
        session_id="tessera_flow",
        brief=brief,
        palette_db_path=str(PALETTE_PATH),
        selected_palette_ids=[tile.tile_id for tile in palette.tiles[:3]],
    )
    return session, source_path


def controller_options(tmp_path: Path) -> dict[str, object]:
    return {
        "compile_mask_path": None,
        "whole_image": True,
        "max_colors": 2,
        "granularity": "coarse",
        "min_region_area_px": 4,
        "boundary_smoothing": "none",
        "merge_tiny_regions": True,
        "color_compactness": 5.0,
        "minimum_color_area_cm2": None,
        "physical_scale_basis": "full_image",
        "out_root": tmp_path / "runs",
    }


def test_controller_compile_with_physical_tessera_subdivision(tmp_path):
    session, source = make_session_and_source(tmp_path)

    updated = compile_session_tile_map(
        session,
        source_choice="upload",
        uploaded_source_path=str(source),
        physical_width_cm=200,
        physical_height_cm=200,
        enable_tessera=True,
        min_short_edge_mm=8,
        target_short_edge_mm=18,
        max_long_edge_mm=55,
        preferred_aspect_ratio=1.8,
        max_aspect_ratio=4,
        flow_strength="medium",
        edge_following="medium",
        shape_style="irregular",
        random_seed=0,
        grout_width_mm=2,
        max_tessera_count=10000,
        **controller_options(tmp_path),
    )

    assert updated.latest_compile_result is not None
    tessera = updated.latest_compile_result.tessera_result
    assert tessera is not None
    assert Path(tessera.tessera_map_path).is_file()
    assert Path(tessera.tessera_boundaries_path).is_file()
    assert Path(tessera.tessera_qa_report_path).is_file()
    assert tessera.tessera_count <= 10000


def test_controller_compile_without_tessera_preserves_disabled_path(tmp_path):
    session, source = make_session_and_source(tmp_path)

    updated = compile_session_tile_map(
        session,
        source_choice="upload",
        uploaded_source_path=str(source),
        physical_width_cm=None,
        physical_height_cm=None,
        enable_tessera=False,
        **controller_options(tmp_path),
    )

    assert updated.latest_compile_result is not None
    assert updated.latest_compile_result.tessera_result is None


def test_controller_tessera_requires_friendly_physical_dimensions_error(tmp_path):
    session, source = make_session_and_source(tmp_path)

    with pytest.raises(ValueError, match="Physical width and height are required"):
        compile_session_tile_map(
            session,
            source_choice="upload",
            uploaded_source_path=str(source),
            physical_width_cm=None,
            physical_height_cm=None,
            enable_tessera=True,
            **controller_options(tmp_path),
        )


def test_full_session_export_includes_tessera_artifacts(tmp_path):
    session, source = make_session_and_source(tmp_path)
    compiled = compile_session_tile_map(
        session,
        source_choice="upload",
        uploaded_source_path=str(source),
        physical_width_cm=20,
        physical_height_cm=20,
        enable_tessera=True,
        max_tessera_count=3000,
        **controller_options(tmp_path),
    )

    output = export_session(compiled, tmp_path / "export")

    assert (output / "compile_runs/run_01/tessera_map.png").is_file()
    assert (output / "compile_runs/run_01/tessera.csv").is_file()
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["compile_runs"][0]["path"] == "compile_runs/run_01"
