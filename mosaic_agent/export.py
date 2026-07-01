from __future__ import annotations

import json
from pathlib import Path

from mosaic_agent.models import ConceptPackage, RunTrace


def export_artifacts(package: ConceptPackage, out_dir: str | Path, trace: RunTrace | None = None) -> None:
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)

    _write_json(output / "concept_package.json", package.model_dump(mode="json"))
    (output / "artist_questions.md").write_text(_render_questions(package), encoding="utf-8")
    (output / "image_prompts.md").write_text(_render_image_prompts(package), encoding="utf-8")
    (output / "critique.md").write_text(_render_critique(package), encoding="utf-8")

    if trace is not None:
        _write_json(output / "run_trace.json", trace.model_dump(mode="json"))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _render_questions(package: ConceptPackage) -> str:
    lines = [f"# Artist Questions — {package.project_name}", ""]

    if package.questions:
        lines.extend(["## Blocking Or Active Assumption Questions", ""])
        lines.extend(f"- {question}" for question in package.questions)
    else:
        lines.extend(["No blocking questions were detected.", ""])

    if package.assumptions:
        lines.extend(["", "## Active Assumptions", ""])
        lines.extend(f"- {assumption}" for assumption in package.assumptions)

    lines.extend(["", "## Next Session Focus", "", f"- {package.recommended_next_step}", ""])
    return "\n".join(lines)


def _render_image_prompts(package: ConceptPackage) -> str:
    lines = [f"# Image Prompts — {package.project_name}", ""]
    for concept in package.concepts:
        lines.extend(
            [
                f"## {concept.name}",
                "",
                "### OpenAI",
                "",
                concept.image_prompts.openai,
                "",
                "### Gemini / Nano Banana",
                "",
                concept.image_prompts.gemini_nano_banana,
                "",
                "### Negative Prompt",
                "",
                concept.image_prompts.negative_prompt,
                "",
            ]
        )
    return "\n".join(lines)


def _render_critique(package: ConceptPackage) -> str:
    lines = [f"# Critique — {package.project_name}", ""]
    for concept in package.concepts:
        scores = concept.critique.scores
        lines.extend(
            [
                f"## {concept.name}",
                "",
                "### Scores",
                "",
                f"- Palette adherence: {scores.palette_adherence}/5",
                f"- Distance readability: {scores.distance_readability}/5",
                f"- Tile buildability: {scores.tile_buildability}/5",
                f"- Text survivability: {scores.text_survivability}/5",
                f"- Yael-style fit: {scores.style_fit}/5",
                f"- Novelty: {scores.novelty}/5",
                "",
                "### Notes",
                "",
            ]
        )
        lines.extend(f"- {note}" for note in concept.critique.notes)
        lines.extend(["", "### Risks", ""])
        lines.extend(f"- {risk}" for risk in concept.critique.risks)
        lines.append("")
    return "\n".join(lines)
