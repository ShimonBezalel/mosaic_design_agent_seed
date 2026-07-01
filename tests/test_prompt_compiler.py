from pathlib import Path

from mosaic_agent.load import load_brief, load_palette
from mosaic_agent.loop import run_agent_loop
from mosaic_agent.prompt_compiler import compile_visual_prompt


ROOT = Path(__file__).resolve().parents[1]


def test_visual_prompt_includes_palette_and_mosaic_constraints():
    brief = load_brief(ROOT / "examples" / "project_brief.example.json")
    palette = load_palette(ROOT / "examples" / "palette_db.example.json")
    package = run_agent_loop(brief=brief, palette=palette, mode="stub", allow_assumptions=True)

    compiled = compile_visual_prompt(package.concepts[0], brief, palette, variant_index=1)

    assert "terracotta orange (#C95A2A)" in compiled.prompt
    assert "broken ceramic tile mosaic" in compiled.prompt
    assert "public entrance stone" in compiled.prompt
    assert "large-scale readability" in compiled.prompt
    assert "visible grout" in compiled.prompt
    assert "hand-built" in compiled.prompt
    assert "proposal image, not a final exact construction plan" in compiled.prompt
    assert "ברוכים הבאים" not in compiled.prompt
    assert "reserved high-contrast lettering field" in compiled.prompt
    assert "abstract placeholder letter blocks" in compiled.prompt
    assert "manually redrawn/vectorized" in compiled.prompt
    assert "avoid pixel art" in compiled.negative_prompt
    assert "avoid photomosaic" in compiled.negative_prompt
    assert "overly tiny details" in compiled.negative_prompt
    assert compiled.has_hebrew_text is True
