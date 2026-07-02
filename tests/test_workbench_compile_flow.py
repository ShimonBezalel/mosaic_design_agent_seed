from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from mosaic_agent.load import load_brief, load_palette
from mosaic_agent.session_models import EditTarget, GenerationRun, InteractiveSession
from mosaic_workbench.controllers import compile_session_tile_map, resolve_compile_source
from mosaic_workbench.export import export_session


ROOT = Path(__file__).resolve().parents[1]
PALETTE_PATH = ROOT / "examples" / "palette_db.example.json"


def make_source(path: Path, size: tuple[int, int] = (80, 48)) -> Path:
    width, height = size
    source = np.zeros((height, width, 3), dtype=np.uint8)
    source[:, : width // 2] = (201, 90, 42)
    source[:, width // 2 :] = (30, 78, 140)
    Image.fromarray(source, "RGB").save(path)
    return path


def make_alpha_mask(path: Path, size: tuple[int, int] = (80, 48), work_width: int = 60) -> Path:
    width, height = size
    mask = np.zeros((height, width, 4), dtype=np.uint8)
    mask[:, work_width:, 3] = 255
    Image.fromarray(mask, "RGBA").save(path)
    return path


def make_session(tmp_path: Path, *, with_edit_target: bool = False) -> InteractiveSession:
    brief = load_brief(ROOT / "examples" / "project_brief.example.json")
    palette = load_palette(PALETTE_PATH)
    edit_target = None
    if with_edit_target:
        base = make_source(tmp_path / "base.png")
        mask = make_alpha_mask(tmp_path / "base-mask.png")
        edit_target = EditTarget(base_image_path=str(base), mask_image_path=str(mask))
    return InteractiveSession(
        session_id="compile_test",
        brief=brief,
        palette_db_path=str(PALETTE_PATH),
        selected_palette_ids=[tile.tile_id for tile in palette.tiles[:3]],
        edit_target=edit_target,
    )


def compile_kwargs(tmp_path: Path) -> dict[str, object]:
    return {
        "compile_mask_path": None,
        "whole_image": True,
        "max_colors": 2,
        "granularity": "coarse",
        "min_region_area_px": 8,
        "boundary_smoothing": "none",
        "merge_tiny_regions": True,
        "physical_width_cm": None,
        "physical_height_cm": None,
        "out_root": tmp_path / "runs",
    }


def test_compile_uploaded_image_without_concept_generation(tmp_path):
    session = make_session(tmp_path)
    source = make_source(tmp_path / "finalized.png")

    updated = compile_session_tile_map(
        session,
        source_choice="upload",
        uploaded_source_path=str(source),
        **compile_kwargs(tmp_path),
    )

    assert updated.concepts == []
    assert updated.selected_concept_id is None
    assert updated.accepted_source_image_path == str(source)
    assert updated.latest_compile_result is not None
    assert len(updated.compile_runs) == 1
    assert Path(updated.latest_compile_result.palette_map_path).exists()


def test_compile_uses_latest_generated_variant(tmp_path):
    session = make_session(tmp_path)
    first = make_source(tmp_path / "variant-1.png")
    latest = make_source(tmp_path / "variant-2.png")
    session = session.model_copy(
        update={
            "generation_runs": [
                GenerationRun(
                    concept_id="concept",
                    provider="stub",
                    prompt="first",
                    image_paths=[str(first)],
                ),
                GenerationRun(
                    concept_id="concept",
                    provider="stub",
                    prompt="latest",
                    image_paths=[str(latest)],
                ),
            ]
        }
    )

    updated = compile_session_tile_map(
        session,
        source_choice="latest_variant",
        uploaded_source_path=None,
        **compile_kwargs(tmp_path),
    )

    assert updated.accepted_source_image_path == str(latest)
    assert updated.latest_compile_result is not None


def test_compile_uses_base_canvas(tmp_path):
    session = make_session(tmp_path, with_edit_target=True)

    updated = compile_session_tile_map(
        session,
        source_choice="base_canvas",
        uploaded_source_path=None,
        **compile_kwargs(tmp_path),
    )

    assert updated.accepted_source_image_path == session.edit_target.base_image_path


def test_recompiling_appends_runs_and_updates_latest(tmp_path):
    session = make_session(tmp_path)
    source = make_source(tmp_path / "finalized.png")
    first = compile_session_tile_map(
        session,
        source_choice="upload",
        uploaded_source_path=str(source),
        **compile_kwargs(tmp_path),
    )
    second_options = compile_kwargs(tmp_path) | {"granularity": "fine"}

    second = compile_session_tile_map(
        first,
        source_choice="upload",
        uploaded_source_path=str(source),
        **second_options,
    )

    assert len(second.compile_runs) == 2
    assert second.latest_compile_result == second.compile_runs[-1]
    assert second.compile_runs[0].parameters["granularity"] == "coarse"
    assert second.compile_runs[1].parameters["granularity"] == "fine"


@pytest.mark.parametrize(
    ("choice", "expected"),
    [
        ("upload", "Upload a finalized source image"),
        ("latest_variant", "No generated variant is available"),
        ("base_canvas", "No base canvas is available"),
    ],
)
def test_missing_compile_sources_fail_with_friendly_messages(tmp_path, choice, expected):
    session = make_session(tmp_path)

    with pytest.raises(ValueError, match=expected):
        resolve_compile_source(session, choice, None)


def test_compile_requires_selected_palette_colors(tmp_path):
    session = make_session(tmp_path).model_copy(update={"selected_palette_ids": []})
    source = make_source(tmp_path / "finalized.png")

    with pytest.raises(ValueError, match="Select at least one palette color"):
        compile_session_tile_map(
            session,
            source_choice="upload",
            uploaded_source_path=str(source),
            **compile_kwargs(tmp_path),
        )


def test_compile_specific_mask_overrides_session_mask(tmp_path):
    session = make_session(tmp_path, with_edit_target=True)
    override = make_alpha_mask(tmp_path / "override.png", work_width=20)
    options = compile_kwargs(tmp_path) | {
        "whole_image": False,
        "compile_mask_path": str(override),
    }

    updated = compile_session_tile_map(
        session,
        source_choice="base_canvas",
        uploaded_source_path=None,
        **options,
    )

    assert updated.latest_compile_result.masked_pixel_count == 20 * 48


def test_whole_image_mode_ignores_available_session_mask(tmp_path):
    session = make_session(tmp_path, with_edit_target=True)

    updated = compile_session_tile_map(
        session,
        source_choice="base_canvas",
        uploaded_source_path=None,
        **compile_kwargs(tmp_path),
    )

    assert updated.latest_compile_result.masked_pixel_count == 80 * 48


def test_compile_only_session_export_contains_complete_compile_bundle(tmp_path):
    session = make_session(tmp_path)
    source = make_source(tmp_path / "finalized.png")
    compiled = compile_session_tile_map(
        session,
        source_choice="upload",
        uploaded_source_path=str(source),
        **compile_kwargs(tmp_path),
    )

    output = export_session(compiled, tmp_path / "full-export")

    assert not (output / "selected_concept.json").exists()
    assert (output / "compile_runs/run_01/palette_map.png").exists()
    assert (output / "compile_runs/run_01/qa_report.json").exists()
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["compile_runs"][0]["run_id"] == compiled.latest_compile_result.run_id
    assert manifest["latest_compile_run"] == "compile_runs/run_01"
