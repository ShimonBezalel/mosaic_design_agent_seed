import json
from pathlib import Path

import gradio as gr
import numpy as np
from PIL import Image

from mosaic_agent.ideation_stub import generate_stub_concepts
from mosaic_agent.load import load_brief, load_palette
from mosaic_agent.session_models import InteractiveSession
from mosaic_workbench import app as workbench_app
from mosaic_workbench.app import _compile_tile_map_ui, _render_concepts, build_app


ROOT = Path(__file__).resolve().parents[1]


def test_build_app_exposes_required_workbench_controls():
    app = build_app()

    assert isinstance(app, gr.Blocks)
    config = json.dumps(app.get_config_file(), default=str, ensure_ascii=False)
    for label in [
        "Palette DB path",
        "Base canvas image",
        "Upload mask PNG",
        "Draw mask",
        "Generate concepts",
        "Generate 1 variant",
        "Generate 3 variants",
        "Export session",
        "Generated images are visual ideation only",
        "5. Compile to Tile Map",
        "Finalized source image",
        "Compile source",
        "Compile-specific mask",
        "Whole image",
        "Color-area compilation",
        "Max colors",
        "Minimum color area (cm²)",
        "Color shape regularity",
        "Boundary smoothing",
        "Merge tiny regions",
        "Strict palette",
        "Physical width (cm)",
        "Physical height (cm)",
        "Physical dimensions apply to",
        "Tessera / shard subdivision",
        "Enable tessera subdivision",
        "Minimum short edge (mm)",
        "Target short edge (mm)",
        "Maximum long edge (mm)",
        "Preferred aspect ratio",
        "Maximum aspect ratio",
        "Flow strength",
        "Edge following",
        "Shape style",
        "Random seed",
        "Grout preview width (mm)",
        "Maximum tessera count",
        "Compile to Tile Map",
        "Palette map",
        "Numbered region map",
        "Region boundaries",
        "Tessera map",
        "Tessera boundaries",
        "Tessera QA",
        "Tile legend",
        "Compile report",
        "Compile bundle",
        "Generated maps are planning aids",
        "Color regions define palette areas",
    ]:
        assert label in config


def test_demo_fixture_has_matching_base_and_alpha_mask():
    demo_dir = ROOT / "examples" / "workbench_demo"
    for name in [
        "base_canvas.png",
        "sample_mask.png",
        "site_context.png",
        "style_reference.png",
        "composition_sketch.png",
        "session_preset.json",
    ]:
        assert (demo_dir / name).exists()

    with Image.open(demo_dir / "base_canvas.png") as base, Image.open(
        demo_dir / "sample_mask.png"
    ) as mask:
        assert base.size == mask.size
        assert mask.format == "PNG"
        assert "A" in mask.getbands()


def test_concept_cards_are_scan_friendly_with_collapsible_details():
    brief = load_brief(ROOT / "examples" / "project_brief.example.json")
    palette = load_palette(ROOT / "examples" / "palette_db.example.json")
    concepts = generate_stub_concepts(brief, palette)
    session = InteractiveSession(
        session_id="concept_cards",
        brief=brief,
        palette_db_path=str(ROOT / "examples" / "palette_db.example.json"),
        concepts=concepts,
    )

    rendered = _render_concepts(session)

    assert f"<h3>{concepts[0].name}</h3>" in rendered
    assert "<details>" in rendered
    assert "<summary>Details</summary>" in rendered
    assert rendered.index("<details>") < rendered.index(concepts[0].composition)


def test_compile_ui_can_start_from_uploaded_image_without_prepared_session(tmp_path, monkeypatch):
    monkeypatch.setattr(workbench_app, "ROOT", tmp_path)
    source = np.zeros((24, 36, 3), dtype=np.uint8)
    source[:, :18] = (201, 90, 42)
    source[:, 18:] = (30, 78, 140)
    source_path = tmp_path / "finalized.png"
    Image.fromarray(source, "RGB").save(source_path)
    palette_path = ROOT / "examples" / "palette_db.example.json"
    selected = [tile.tile_id for tile in load_palette(palette_path).tiles[:3]]

    result = _compile_tile_map_ui(
        None,
        str(palette_path),
        selected,
        "Direct compile",
        "Studio",
        "Compile an accepted image",
        "",
        "",
        "",
        "",
        10.0,
        "coarse",
        "",
        "upload",
        str(source_path),
        None,
        True,
        "coarse",
        2,
        4,
        "none",
        True,
        0,
        0,
    )

    (
        state,
        palette_map,
        region_labels,
        boundaries,
        tessera_map,
        tessera_boundaries,
        legend,
        warnings,
        tessera_qa,
        report,
        status,
    ) = result
    assert state["concepts"] == []
    assert Path(palette_map).exists()
    assert Path(region_labels).exists()
    assert Path(boundaries).exists()
    assert tessera_map is None
    assert tessera_boundaries is None
    assert legend
    assert "planning aids" in warnings
    assert tessera_qa == ""
    assert Path(report).exists()
    assert "Compiled" in status
