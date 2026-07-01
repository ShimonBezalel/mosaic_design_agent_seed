from pathlib import Path

from PIL import Image, ImageDraw

from mosaic_agent.load import load_brief, load_palette
from mosaic_agent.palette import palette_tile_ids
from mosaic_workbench.controllers import (
    create_session,
    generate_concepts,
    generate_variants,
    select_session_concept,
)
from mosaic_workbench.export import export_session


ROOT = Path(__file__).resolve().parents[1]
PALETTE_PATH = ROOT / "examples" / "palette_db.example.json"


def _input_images(tmp_path: Path) -> tuple[Path, Path, Path]:
    base_path = tmp_path / "base.jpg"
    mask_path = tmp_path / "mask.png"
    style_path = tmp_path / "style.png"
    Image.new("RGB", (96, 64), "#d8c6a8").save(base_path)
    Image.new("RGB", (32, 32), "#c95a2a").save(style_path)
    mask = Image.new("L", (96, 64), 0)
    ImageDraw.Draw(mask).rectangle((24, 16, 72, 48), fill=255)
    mask.save(mask_path)
    return base_path, mask_path, style_path


def test_stub_workbench_flow_generates_concepts_variants_and_export(tmp_path):
    base_path, mask_path, style_path = _input_images(tmp_path)
    brief = load_brief(ROOT / "examples" / "project_brief.example.json")
    palette = load_palette(PALETTE_PATH)

    session = create_session(
        brief=brief,
        palette_db_path=PALETTE_PATH,
        base_image_path=base_path,
        mask_image_path=mask_path,
        reference_inputs=[(style_path, "artist_style_reference")],
        out_root=tmp_path / "sessions",
        session_id="stub_flow",
    )

    assert session.edit_target is not None
    assert Path(session.edit_target.base_image_path).suffix == ".png"
    assert Path(session.edit_target.mask_image_path).exists()
    assert Path(session.edit_target.overlay_preview_path).exists()
    assert len(session.reference_assets) == 1

    session = generate_concepts(session, ideation_mode="stub")

    assert len(session.concepts) == 3
    available = palette_tile_ids(palette)
    assert all(set(concept.palette_tile_ids) <= available for concept in session.concepts)

    session = select_session_concept(session, session.concepts[0].concept_id)
    session = generate_variants(session, image_mode="stub", variant_count=3)

    assert len(session.generation_runs) == 1
    assert len(session.generation_runs[0].image_paths) == 3
    assert all(Path(path).exists() for path in session.generation_runs[0].image_paths)

    export_dir = export_session(session, tmp_path / "export")
    assert (export_dir / "session.json").exists()
    assert len(list((export_dir / "variants").glob("*.png"))) == 3
    assert (export_dir / "references" / "artist_style_reference_01.png").exists()


def test_stub_edit_changes_only_the_masked_region(tmp_path):
    base_path, mask_path, _ = _input_images(tmp_path)
    brief = load_brief(ROOT / "examples" / "project_brief.example.json")
    session = create_session(
        brief=brief,
        palette_db_path=PALETTE_PATH,
        base_image_path=base_path,
        mask_image_path=mask_path,
        reference_inputs=[],
        out_root=tmp_path / "sessions",
        session_id="mask_scope",
    )
    session = generate_concepts(session, ideation_mode="stub")
    session = select_session_concept(session, session.concepts[0].concept_id)
    session = generate_variants(session, image_mode="stub", variant_count=1)

    with Image.open(session.edit_target.base_image_path) as base, Image.open(
        session.generation_runs[0].image_paths[0]
    ) as edited:
        base_rgb = base.convert("RGB")
        edited_rgb = edited.convert("RGB")
        assert edited_rgb.getpixel((5, 5)) == base_rgb.getpixel((5, 5))
        assert edited_rgb.getpixel((48, 32)) != base_rgb.getpixel((48, 32))
