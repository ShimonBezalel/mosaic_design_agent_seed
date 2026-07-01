from pathlib import Path

from mosaic_agent.edit_prompt_compiler import compile_edit_prompt
from mosaic_agent.ideation_stub import generate_stub_concepts
from mosaic_agent.load import load_brief, load_palette


ROOT = Path(__file__).resolve().parents[1]


def test_edit_prompt_for_hebrew_requires_a_blank_lettering_field():
    brief = load_brief(ROOT / "examples" / "project_brief.example.json")
    palette = load_palette(ROOT / "examples" / "palette_db.example.json")
    concept = generate_stub_concepts(brief, palette)[0]

    prompt = compile_edit_prompt(concept, brief, palette)

    assert "broken ceramic tile mosaic" in prompt
    assert "visible grout" in prompt
    assert "proposal image, not an exact construction plan" in prompt
    assert "Do not render Hebrew letters" in prompt
    assert "fake Hebrew" in prompt
    assert "pseudo-text" in prompt
    assert "completely blank high-contrast lettering field" in prompt
    assert "ברוכים הבאים" not in prompt
