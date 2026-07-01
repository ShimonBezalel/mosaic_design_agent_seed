from __future__ import annotations

import re

from mosaic_agent.ideation_stub import generate_stub_concepts
from mosaic_agent.intake import MissingCriticalFieldsError, assumptions_for_missing_fields, check_missing_critical_fields
from mosaic_agent.models import ConceptPackage, PaletteDB, ProjectBrief
from mosaic_agent.palette import summarize_palette


SUPPORTED_MODES = {"stub", "openai-image", "gemini-image"}


def run_agent_loop(
    *,
    brief: ProjectBrief,
    palette: PaletteDB,
    mode: str = "stub",
    allow_assumptions: bool = False,
) -> ConceptPackage:
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported mode: {mode}")

    questions = check_missing_critical_fields(brief)
    if questions and not allow_assumptions:
        raise MissingCriticalFieldsError(questions)

    assumptions = assumptions_for_missing_fields(questions) if questions else []
    concepts = generate_stub_concepts(brief, palette)

    return ConceptPackage(
        run_id=f"{_slugify(brief.project_name)}-stub",
        project_name=brief.project_name,
        mode=mode,
        assumptions=assumptions,
        questions=questions,
        palette_summary=summarize_palette(palette),
        concepts=concepts,
        recommended_next_step=(
            "Review the three directions with the artist, confirm stone dimensions and text geometry, "
            "then pick one direction for a real image-provider pass."
        ),
    )


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "mosaic-run"
