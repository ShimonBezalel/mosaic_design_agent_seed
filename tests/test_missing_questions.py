from pathlib import Path

import pytest

from mosaic_agent.intake import MissingCriticalFieldsError, check_missing_critical_fields
from mosaic_agent.load import load_brief, load_palette
from mosaic_agent.loop import run_agent_loop


ROOT = Path(__file__).resolve().parents[1]


def test_missing_canvas_dimensions_produce_questions():
    brief = load_brief(ROOT / "examples" / "project_brief.example.json")

    questions = check_missing_critical_fields(brief)

    assert any("stone face dimensions" in question for question in questions)


def test_loop_refuses_to_generate_concepts_without_assumptions():
    brief = load_brief(ROOT / "examples" / "project_brief.example.json")
    palette = load_palette(ROOT / "examples" / "palette_db.example.json")

    with pytest.raises(MissingCriticalFieldsError) as error:
        run_agent_loop(brief=brief, palette=palette, mode="stub", allow_assumptions=False)

    assert error.value.questions
    assert "stone face dimensions" in "\n".join(error.value.questions)
