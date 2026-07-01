import json
from pathlib import Path

import pytest
from PIL import Image

from mosaic_agent.ideation_stub import generate_stub_concepts
from mosaic_agent.load import load_brief, load_palette
from mosaic_agent.session_models import EditTarget, GenerationRun, InteractiveSession
from mosaic_workbench.export import export_session
from mosaic_workbench.session_state import select_concept


ROOT = Path(__file__).resolve().parents[1]


def _session(tmp_path: Path) -> InteractiveSession:
    brief = load_brief(ROOT / "examples" / "project_brief.example.json")
    palette = load_palette(ROOT / "examples" / "palette_db.example.json")
    concepts = generate_stub_concepts(brief, palette)
    base_path = tmp_path / "normalized_base.png"
    mask_path = tmp_path / "normalized_mask.png"
    variant_path = tmp_path / "variant_01.png"
    Image.new("RGB", (64, 64), "#d8c6a8").save(base_path)
    Image.new("RGBA", (64, 64), (0, 0, 0, 255)).save(mask_path)
    Image.new("RGB", (64, 64), "#c95a2a").save(variant_path)
    return InteractiveSession(
        session_id="session_test",
        brief=brief,
        palette_db_path=str(ROOT / "examples" / "palette_db.example.json"),
        selected_palette_ids=concepts[0].palette_tile_ids,
        edit_target=EditTarget(
            base_image_path=str(base_path),
            mask_image_path=str(mask_path),
            mode="inpaint",
        ),
        concepts=concepts,
        selected_concept_id=concepts[0].concept_id,
        generation_runs=[
            GenerationRun(
                concept_id=concepts[0].concept_id,
                provider="stub",
                prompt="Mosaic edit prompt",
                image_paths=[str(variant_path)],
                mode="inpaint",
            )
        ],
    )


def test_select_concept_updates_known_concept_and_rejects_unknown(tmp_path):
    session = _session(tmp_path)

    updated = select_concept(session, session.concepts[1].concept_id)

    assert updated.selected_concept_id == session.concepts[1].concept_id
    with pytest.raises(ValueError, match="unknown concept ID"):
        select_concept(session, "missing_concept")


def test_export_session_writes_required_artifacts(tmp_path):
    session = _session(tmp_path)
    export_dir = tmp_path / "export"

    result = export_session(session, export_dir)

    assert result == export_dir
    expected = {
        "session.json",
        "normalized_brief.json",
        "selected_concept.json",
        "prompts.md",
        "critique.md",
        "base_image.png",
        "mask.png",
        "manifest.json",
        "variants/variant_01.png",
    }
    actual = {
        str(path.relative_to(export_dir))
        for path in export_dir.rglob("*")
        if path.is_file()
    }
    assert expected <= actual

    manifest = json.loads((export_dir / "manifest.json").read_text())
    assert manifest["session_id"] == "session_test"
    assert manifest["selected_concept_id"] == session.selected_concept_id
    assert manifest["generated_variants"] == ["variants/variant_01.png"]
    assert manifest["generation_runs"][0]["provider"] == "stub"
    assert manifest["generation_runs"][0]["concept_id"] == session.selected_concept_id
