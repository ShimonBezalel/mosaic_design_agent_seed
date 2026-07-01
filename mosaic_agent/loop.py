from __future__ import annotations

import re

from mosaic_agent.ideation_stub import generate_stub_concepts
from mosaic_agent.intake import MissingCriticalFieldsError, assumptions_for_missing_fields, check_missing_critical_fields
from mosaic_agent.models import ConceptPackage, PaletteDB, ProjectBrief
from mosaic_agent.openai_ideation import generate_openai_concepts
from mosaic_agent.palette import summarize_palette


SUPPORTED_IMAGE_MODES = {"stub", "openai-image", "openai-responses-image", "gemini-image"}
SUPPORTED_IDEATION_MODES = {"stub", "openai"}


def run_agent_loop(
    *,
    brief: ProjectBrief,
    palette: PaletteDB,
    mode: str | None = None,
    ideation_mode: str = "stub",
    image_mode: str = "stub",
    allow_assumptions: bool = False,
    concept_limit: int = 3,
) -> ConceptPackage:
    if mode is not None:
        image_mode = mode
        ideation_mode = "stub"
    if ideation_mode not in SUPPORTED_IDEATION_MODES:
        raise ValueError(f"Unsupported ideation mode: {ideation_mode}")
    if image_mode not in SUPPORTED_IMAGE_MODES:
        raise ValueError(f"Unsupported image mode: {image_mode}")
    if concept_limit < 1:
        raise ValueError("concept_limit must be at least 1")

    questions = check_missing_critical_fields(brief)
    if questions and not allow_assumptions:
        raise MissingCriticalFieldsError(questions)

    assumptions = assumptions_for_missing_fields(questions) if questions else []
    if ideation_mode == "stub":
        concepts = generate_stub_concepts(brief, palette)
    else:
        concepts = generate_openai_concepts(brief=brief, palette=palette, concept_limit=concept_limit)
    concepts = concepts[:concept_limit]

    return ConceptPackage(
        run_id=f"{_slugify(brief.project_name)}-{ideation_mode}-{image_mode}",
        project_name=brief.project_name,
        mode=image_mode,
        ideation_mode=ideation_mode,  # type: ignore[arg-type]
        image_mode=image_mode,  # type: ignore[arg-type]
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
