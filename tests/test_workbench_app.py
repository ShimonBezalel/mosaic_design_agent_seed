import json
from pathlib import Path

import gradio as gr
from PIL import Image

from mosaic_workbench.app import build_app


ROOT = Path(__file__).resolve().parents[1]


def test_build_app_exposes_required_workbench_controls():
    app = build_app()

    assert isinstance(app, gr.Blocks)
    config = json.dumps(app.get_config_file(), default=str)
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
