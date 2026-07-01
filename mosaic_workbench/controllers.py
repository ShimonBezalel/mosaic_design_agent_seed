from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from mosaic_agent.edit_prompt_compiler import compile_edit_prompt
from mosaic_agent.image_edit_service import ImageEditRequest, StubImageEditProvider
from mosaic_agent.load import load_palette
from mosaic_agent.loop import run_agent_loop
from mosaic_agent.models import PaletteDB, ProjectBrief, ReferenceImageRole
from mosaic_agent.providers.openai_edit import OpenAIImageEditProvider
from mosaic_agent.session_models import EditTarget, GenerationRun, InteractiveSession, ReferenceAsset
from mosaic_workbench.mask_utils import create_mask_overlay, normalize_base_image, normalize_mask
from mosaic_workbench.session_state import select_concept


def create_session(
    *,
    brief: ProjectBrief,
    palette_db_path: str | Path,
    base_image_path: str | Path,
    mask_image_path: str | Path,
    reference_inputs: list[tuple[str | Path, ReferenceImageRole]],
    out_root: str | Path = "runs/workbench",
    session_id: str | None = None,
) -> InteractiveSession:
    palette = load_palette(palette_db_path)
    identifier = session_id or uuid4().hex[:12]
    session_dir = Path(out_root) / identifier
    inputs_dir = session_dir / "inputs"
    base_output = normalize_base_image(base_image_path, inputs_dir / "base_image.png")
    mask_output = normalize_mask(base_output, mask_image_path, inputs_dir / "mask.png")
    overlay_output = create_mask_overlay(base_output, mask_output, inputs_dir / "mask_overlay.png")

    reference_assets: list[ReferenceAsset] = []
    for index, (source_value, role) in enumerate(reference_inputs, start=1):
        source = Path(source_value)
        relative_name = f"{role}_{index:02d}{source.suffix or '.png'}"
        destination = inputs_dir / "references" / relative_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        reference_assets.append(
            ReferenceAsset(
                asset_id=f"{role}_{index:02d}",
                path=str(destination),
                role=role,
            )
        )

    normalized_brief = brief.model_copy(
        update={
            "reference_image_paths": [asset.path for asset in reference_assets],
            "reference_image_roles": [asset.role for asset in reference_assets],
        }
    )
    return InteractiveSession(
        session_id=identifier,
        brief=normalized_brief,
        palette_db_path=str(palette_db_path),
        selected_palette_ids=[tile.tile_id for tile in palette.tiles],
        reference_assets=reference_assets,
        edit_target=EditTarget(
            base_image_path=str(base_output),
            mask_image_path=str(mask_output),
            overlay_preview_path=str(overlay_output),
            mode="inpaint",
        ),
    )


def generate_concepts(
    session: InteractiveSession,
    *,
    ideation_mode: str = "stub",
) -> InteractiveSession:
    palette = _working_palette(session)
    package = run_agent_loop(
        brief=session.brief,
        palette=palette,
        ideation_mode=ideation_mode,
        image_mode="stub",
        allow_assumptions=True,
        concept_limit=3,
    )
    return session.model_copy(
        update={
            "concepts": package.concepts,
            "selected_concept_id": None,
            "critique": [risk for concept in package.concepts for risk in concept.critique.risks],
        }
    )


def select_session_concept(session: InteractiveSession, concept_id: str) -> InteractiveSession:
    return select_concept(session, concept_id)


def generate_variants(
    session: InteractiveSession,
    *,
    image_mode: str = "stub",
    variant_count: int = 1,
    quality: str = "low",
    size: str = "auto",
    revision_notes: str = "",
) -> InteractiveSession:
    if session.edit_target is None:
        raise ValueError("base image and mask are required before generating variants")
    concept = _selected_concept(session)
    palette = _working_palette(session)
    prompt = compile_edit_prompt(
        concept,
        session.brief,
        palette,
        revision_notes=revision_notes,
    )
    if image_mode == "stub":
        provider = StubImageEditProvider()
    elif image_mode == "openai-edit":
        provider = OpenAIImageEditProvider()
    else:
        raise ValueError(f"unsupported image edit mode: {image_mode}")
    session_dir = Path(session.edit_target.base_image_path).parents[1]
    run_dir = session_dir / "generations" / f"run_{len(session.generation_runs) + 1:02d}"
    request = ImageEditRequest(
        provider=image_mode,
        concept_id=concept.concept_id,
        prompt=prompt,
        base_image_path=session.edit_target.base_image_path,
        mask_image_path=session.edit_target.mask_image_path,
        reference_image_paths=[asset.path for asset in session.reference_assets],
        variant_count=variant_count,
        quality=quality,
        size=size,
    )
    image_paths = provider.edit(request, run_dir)
    generation = GenerationRun(
        concept_id=concept.concept_id,
        provider=provider.provider_name,
        prompt=prompt,
        image_paths=[str(path) for path in image_paths],
        mode=session.edit_target.mode,
        revision_notes=revision_notes,
        metadata={"quality": quality, "size": size},
    )
    return session.model_copy(update={"generation_runs": [*session.generation_runs, generation]})


def _working_palette(session: InteractiveSession) -> PaletteDB:
    palette = load_palette(session.palette_db_path)
    selected = set(session.selected_palette_ids)
    if not selected:
        return palette
    return palette.model_copy(update={"tiles": [tile for tile in palette.tiles if tile.tile_id in selected]})


def _selected_concept(session: InteractiveSession):
    for concept in session.concepts:
        if concept.concept_id == session.selected_concept_id:
            return concept
    raise ValueError("select a concept before generating variants")
