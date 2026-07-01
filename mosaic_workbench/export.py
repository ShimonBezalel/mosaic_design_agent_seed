from __future__ import annotations

import json
import shutil
from pathlib import Path

from mosaic_agent.models import Concept
from mosaic_agent.session_models import InteractiveSession


def export_session(session: InteractiveSession, out_dir: str | Path) -> Path:
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    selected = _selected_concept(session)

    _write_json(output / "session.json", session.model_dump(mode="json"))
    _write_json(output / "normalized_brief.json", session.brief.model_dump(mode="json"))
    _write_json(output / "selected_concept.json", selected.model_dump(mode="json"))
    (output / "prompts.md").write_text(_render_prompts(session), encoding="utf-8")
    (output / "critique.md").write_text(_render_critique(selected), encoding="utf-8")

    generated_variants: list[str] = []
    generation_runs: list[dict[str, object]] = []
    input_references: list[dict[str, str]] = []
    if session.edit_target is not None:
        shutil.copy2(session.edit_target.base_image_path, output / "base_image.png")
        shutil.copy2(session.edit_target.mask_image_path, output / "mask.png")
        if session.edit_target.overlay_preview_path:
            shutil.copy2(session.edit_target.overlay_preview_path, output / "mask_overlay.png")

    references_dir = output / "references"
    for asset in session.reference_assets:
        source = Path(asset.path)
        relative_path = f"references/{asset.asset_id}{source.suffix or '.png'}"
        references_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, output / relative_path)
        input_references.append(
            {
                "asset_id": asset.asset_id,
                "role": asset.role,
                "path": relative_path,
            }
        )

    variants_dir = output / "variants"
    variant_index = 1
    for run in session.generation_runs:
        run_variants: list[str] = []
        for source_path in run.image_paths:
            variants_dir.mkdir(parents=True, exist_ok=True)
            relative_path = f"variants/variant_{variant_index:02d}.png"
            shutil.copy2(source_path, output / relative_path)
            generated_variants.append(relative_path)
            run_variants.append(relative_path)
            variant_index += 1
        generation_runs.append(
            {
                "concept_id": run.concept_id,
                "provider": run.provider,
                "mode": run.mode,
                "created_at": run.created_at,
                "revision_notes": run.revision_notes,
                "metadata": run.metadata,
                "image_paths": run_variants,
            }
        )

    _write_json(
        output / "manifest.json",
        {
            "session_id": session.session_id,
            "selected_concept_id": session.selected_concept_id,
            "base_image": "base_image.png" if session.edit_target else "",
            "mask_image": "mask.png" if session.edit_target else "",
            "mask_overlay": "mask_overlay.png"
            if session.edit_target and session.edit_target.overlay_preview_path
            else "",
            "input_references": input_references,
            "generated_variants": generated_variants,
            "generation_runs": generation_runs,
        },
    )
    return output


def _selected_concept(session: InteractiveSession) -> Concept:
    for concept in session.concepts:
        if concept.concept_id == session.selected_concept_id:
            return concept
    raise ValueError("a valid selected concept is required before export")


def _render_prompts(session: InteractiveSession) -> str:
    lines = [f"# Prompts - {session.brief.project_name}", ""]
    for run in session.generation_runs:
        lines.extend([f"## {run.concept_id}", "", run.prompt, ""])
        if run.revision_notes:
            lines.extend(["Revision notes:", "", run.revision_notes, ""])
    return "\n".join(lines)


def _render_critique(concept: Concept) -> str:
    lines = [f"# Critique - {concept.name}", "", "## Notes", ""]
    lines.extend(f"- {note}" for note in concept.critique.notes)
    lines.extend(["", "## Risks", ""])
    lines.extend(f"- {risk}" for risk in concept.critique.risks)
    lines.append("")
    return "\n".join(lines)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
