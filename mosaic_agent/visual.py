from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

from mosaic_agent.models import (
    Concept,
    ConceptPackage,
    ImageGenerationRequest,
    PaletteDB,
    ProjectBrief,
    VisualCritique,
    VisualManifest,
    VisualManifestImage,
    VisualManifestInputReference,
)
from mosaic_agent.prompt_compiler import CompiledVisualPrompt, compile_visual_prompt
from mosaic_agent.providers.base import ImageProvider
from mosaic_agent.providers.gemini_nano_banana import GeminiNanoBananaProvider
from mosaic_agent.providers.openai_image import OpenAIImageProvider
from mosaic_agent.providers.openai_responses_image import OpenAIResponsesImageProvider
from mosaic_agent.providers.stub import StubImageProvider
from mosaic_agent.reference_images import ensure_reference_images_exist


def generate_visual_artifacts(
    *,
    package: ConceptPackage,
    brief: ProjectBrief,
    palette: PaletteDB,
    out_dir: str | Path,
    image_mode: str,
    ideation_mode: str = "stub",
    variants_per_concept: int = 2,
    image_size: str = "1536x1024",
    image_quality: str = "low",
    image_model: str | None = None,
) -> VisualManifest:
    if variants_per_concept < 1:
        raise ValueError("variants_per_concept must be at least 1")
    provider = _provider_for_mode(image_mode, image_size=image_size, image_quality=image_quality, image_model=image_model)
    output = Path(out_dir)
    images_dir = output / "images"
    input_references = _copy_input_references(brief, output)
    manifest_images: list[VisualManifestImage] = []

    for concept_index, concept in enumerate(package.concepts, start=1):
        for variant_index in range(1, variants_per_concept + 1):
            compiled = compile_visual_prompt(concept, brief, palette, variant_index=variant_index)
            variant_id = f"variant_{variant_index:02d}"
            relative_path = f"images/concept_{concept_index:02d}_variant_{variant_index:02d}.png"
            output_path = output / relative_path
            request = ImageGenerationRequest(
                provider=image_mode,
                concept_id=concept.concept_id,
                variant_id=variant_id,
                prompt=compiled.prompt,
                negative_prompt=compiled.negative_prompt,
                input_image_paths=[reference.source_path for reference in input_references],
                input_image_roles=[reference.role for reference in input_references],
            )
            result = provider.generate(request, output_path)
            manifest_images.append(
                VisualManifestImage(
                    provider=image_mode,
                    concept_id=concept.concept_id,
                    concept_name=concept.name,
                    variant_id=variant_id,
                    image_path=relative_path,
                    prompt=compiled.prompt,
                    negative_prompt=compiled.negative_prompt,
                    status=result.status,
                    metadata=result.metadata,
                    critique=_build_visual_critique(concept, compiled, variant_index),
                )
            )

    manifest = VisualManifest(
        run_id=package.run_id,
        provider=image_mode,
        ideation_mode=ideation_mode,  # type: ignore[arg-type]
        image_mode=image_mode,  # type: ignore[arg-type]
        project_name=brief.project_name,
        location=brief.location,
        reference_image_paths=brief.reference_image_paths,
        input_references=input_references,
        images=manifest_images,
    )
    output.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    (output / "visual_manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "contact_sheet.html").write_text(_render_contact_sheet(package, brief, palette, manifest), encoding="utf-8")
    (output / "image_prompts.md").write_text(_render_visual_prompts(manifest), encoding="utf-8")
    (output / "critique.md").write_text(_render_visual_critique_markdown(manifest), encoding="utf-8")
    return manifest


def _provider_for_mode(
    mode: str,
    *,
    image_size: str,
    image_quality: str,
    image_model: str | None,
) -> ImageProvider:
    if mode == "stub":
        return StubImageProvider()
    if mode == "openai-image":
        return OpenAIImageProvider(image_model=image_model, image_size=image_size, image_quality=image_quality)
    if mode == "openai-responses-image":
        return OpenAIResponsesImageProvider(image_model=image_model, image_size=image_size, image_quality=image_quality)
    if mode == "gemini-image":
        return GeminiNanoBananaProvider()
    raise ValueError(f"Unsupported visual provider mode: {mode}")


def _build_visual_critique(
    concept: Concept,
    compiled: CompiledVisualPrompt,
    variant_index: int,
) -> VisualCritique:
    if variant_index == 1:
        strongest = f"The strongest visual idea is the broad composition gesture in {concept.name}."
    else:
        strongest = f"The strongest visual idea is the shard-flow and material rhythm in {concept.name}."

    text_risk = "No required text was requested."
    if compiled.has_hebrew_text:
        text_risk = "AI lettering may be unreliable and should be manually redrawn/vectorized before execution."

    return VisualCritique(
        strongest_visual_idea=strongest,
        palette_fit="Palette fit is controlled by the selected tile IDs and named hex colors in the prompt.",
        feasibility_for_broken_tiles=(
            "Feasibility is plausible if the artist keeps the main shapes coarse and treats fine details as accents."
        ),
        readability_from_distance=(
            "Distance readability depends on preserving broad silhouettes, high-contrast lettering fields, and simple symbols."
        ),
        text_risk=text_risk,
        ask_yael="Ask Yael which concept feels closest to her hand and which areas should stay flexible.",
    )


def _render_contact_sheet(
    package: ConceptPackage,
    brief: ProjectBrief,
    palette: PaletteDB,
    manifest: VisualManifest,
) -> str:
    by_concept: dict[str, list[VisualManifestImage]] = {}
    for image in manifest.images:
        by_concept.setdefault(image.concept_id, []).append(image)

    swatches = "\n".join(
        "<span class='swatch' style='--color:{color}'><span></span>{name}<br><code>{hex}</code></span>".format(
            color=html.escape(tile.hex),
            name=html.escape(tile.name),
            hex=html.escape(tile.hex),
        )
        for tile in palette.tiles
    )
    question_items = "\n".join(f"<li>{html.escape(question)}</li>" for question in package.questions) or (
        "<li>No blocking questions detected.</li>"
    )
    assumption_items = "\n".join(f"<li>{html.escape(assumption)}</li>" for assumption in package.assumptions)
    reference_cards = "\n".join(_render_reference_card(reference) for reference in manifest.input_references)
    if not reference_cards:
        reference_cards = "<p>No input references were provided.</p>"

    concept_sections: list[str] = []
    for concept in package.concepts:
        cards = "\n".join(_render_image_card(image) for image in by_concept.get(concept.concept_id, []))
        notes = "\n".join(f"<li>{html.escape(note)}</li>" for note in concept.critique.notes)
        risks = "\n".join(f"<li>{html.escape(risk)}</li>" for risk in concept.critique.risks)
        concept_sections.append(
            f"""
      <section class="concept">
        <h2>{html.escape(concept.name)}</h2>
        <p>{html.escape(concept.intent)}</p>
        <p><strong>Composition:</strong> {html.escape(concept.composition)}</p>
        <div class="grid">{cards}</div>
        <h3>Concept critique</h3>
        <ul>{notes}</ul>
        <h3>Risks</h3>
        <ul>{risks}</ul>
      </section>
            """
        )

    assumptions = f"<h3>Active assumptions</h3><ul>{assumption_items}</ul>" if assumption_items else ""
    reference_paths = ", ".join(brief.reference_image_paths) if brief.reference_image_paths else "None"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(brief.project_name)} visual contact sheet</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; color: #24211d; background: #f7f4ee; }}
    header, main {{ width: 100%; max-width: 1180px; margin: 0 auto; padding: 24px; }}
    header {{ border-bottom: 1px solid #d8d0c2; }}
    h1, h2, h3 {{ margin-bottom: 8px; }}
    .meta, .palette, .concept {{ margin-top: 20px; }}
    .meta {{ overflow-wrap: anywhere; }}
    .palette {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .swatch {{ border: 1px solid #cfc6b6; background: white; padding: 8px; min-width: 126px; font-size: 13px; }}
    .swatch span {{ display: block; height: 34px; background: var(--color); margin-bottom: 6px; border: 1px solid rgba(0,0,0,.2); }}
    .concept {{ border-top: 1px solid #d8d0c2; padding-top: 20px; }}
    .warning {{ padding: 12px; border: 1px solid #a45c24; background: #fff3e6; font-weight: 700; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }}
    .references {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    figure {{ margin: 0; background: #fff; border: 1px solid #d8d0c2; padding: 12px; }}
    img {{ width: 100%; height: auto; display: block; background: #e9e1d3; }}
    figcaption {{ margin-top: 10px; font-weight: 600; }}
    details {{ margin-top: 10px; }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; max-width: 100%; overflow-x: auto; background: #f1ece3; padding: 10px; }}
    code {{ font-size: 12px; }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(brief.project_name)}</h1>
    <p>{html.escape(brief.intent)}</p>
    <div class="meta">
      <strong>Location:</strong> {html.escape(brief.location)}<br>
      <strong>Provider:</strong> {html.escape(manifest.provider)}<br>
      <strong>Reference images:</strong> {html.escape(reference_paths)}
    </div>
    <p class="warning">Generated images are visual ideation only. They are not a construction-ready mosaic plan.</p>
    <h2>Input References</h2>
    <div class="references">{reference_cards}</div>
    <h2>Palette</h2>
    <div class="palette">{swatches}</div>
    <h2>Questions for Yael</h2>
    <ul>{question_items}</ul>
    {assumptions}
  </header>
  <main>
    {''.join(concept_sections)}
  </main>
</body>
</html>
"""


def _copy_input_references(brief: ProjectBrief, output: Path) -> list[VisualManifestInputReference]:
    references: list[VisualManifestInputReference] = []
    destination_dir = output / "input_references"
    destination_dir.mkdir(parents=True, exist_ok=True)
    ensure_reference_images_exist(brief.reference_image_paths)
    for index, (source_path, role) in enumerate(zip(brief.reference_image_paths, brief.reference_image_roles), start=1):
        source = Path(source_path)
        suffix = source.suffix or ".png"
        relative_path = f"input_references/{role}_{index:02d}{suffix}"
        shutil.copy2(source, output / relative_path)
        references.append(
            VisualManifestInputReference(
                role=role,
                source_path=source_path,
                image_path=relative_path,
            )
        )
    return references


def _render_reference_card(reference: VisualManifestInputReference) -> str:
    return f"""
      <figure>
        <img src="{html.escape(reference.image_path)}" alt="{html.escape(reference.role)}">
        <figcaption>{html.escape(reference.role)}</figcaption>
        <p><code>{html.escape(reference.source_path)}</code></p>
      </figure>
    """


def _render_image_card(image: VisualManifestImage) -> str:
    critique = image.critique
    return f"""
          <figure>
            <img src="{html.escape(image.image_path)}" alt="{html.escape(image.concept_name)} {html.escape(image.variant_id)}">
            <figcaption>{html.escape(image.concept_name)} / {html.escape(image.variant_id)}</figcaption>
            <p><strong>Strongest idea:</strong> {html.escape(critique.strongest_visual_idea)}</p>
            <p><strong>Palette fit:</strong> {html.escape(critique.palette_fit)}</p>
            <p><strong>Broken-tile feasibility:</strong> {html.escape(critique.feasibility_for_broken_tiles)}</p>
            <p><strong>Distance readability:</strong> {html.escape(critique.readability_from_distance)}</p>
            <p><strong>Text risk:</strong> {html.escape(critique.text_risk)}</p>
            <p><strong>Ask Yael:</strong> {html.escape(critique.ask_yael)}</p>
            <details>
              <summary>Prompt</summary>
              <pre>{html.escape(image.prompt)}</pre>
              <pre>{html.escape(image.negative_prompt)}</pre>
            </details>
          </figure>
    """


def _render_visual_prompts(manifest: VisualManifest) -> str:
    lines = [f"# Image Prompts - {manifest.project_name}", ""]
    for image in manifest.images:
        lines.extend(
            [
                f"## {image.concept_name} / {image.variant_id}",
                "",
                image.prompt,
                "",
                "### Negative prompt",
                "",
                image.negative_prompt,
                "",
            ]
        )
    return "\n".join(lines)


def _render_visual_critique_markdown(manifest: VisualManifest) -> str:
    lines = [f"# Critique - {manifest.project_name}", ""]
    for image in manifest.images:
        critique = image.critique
        lines.extend(
            [
                f"## {image.concept_name} / {image.variant_id}",
                "",
                f"- Strongest visual idea: {critique.strongest_visual_idea}",
                f"- Palette fit: {critique.palette_fit}",
                f"- Feasibility for broken tiles: {critique.feasibility_for_broken_tiles}",
                f"- Readability from distance: {critique.readability_from_distance}",
                f"- Text risk: {critique.text_risk}",
                f"- What to ask Yael: {critique.ask_yael}",
                "",
            ]
        )
    return "\n".join(lines)
