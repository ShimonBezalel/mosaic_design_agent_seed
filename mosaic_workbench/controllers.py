from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal
from uuid import uuid4

from mosaic_agent.edit_prompt_compiler import compile_edit_prompt
from mosaic_agent.image_edit_service import ImageEditRequest, StubImageEditProvider
from mosaic_agent.load import load_palette
from mosaic_agent.loop import run_agent_loop
from mosaic_agent.models import PaletteDB, ProjectBrief, ReferenceImageRole
from mosaic_agent.palette_compiler import compile_palette_map
from mosaic_agent.providers.openai_edit import OpenAIImageEditProvider
from mosaic_agent.session_models import EditTarget, GenerationRun, InteractiveSession, ReferenceAsset
from mosaic_agent.tile_map_models import (
    BoundarySmoothing,
    EdgeFollowing,
    FlowStrength,
    Granularity,
    PaletteCompileRequest,
    PhysicalScaleBasis,
    ShapeStyle,
    TesseraCompileOptions,
)
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


CompileSourceChoice = Literal["upload", "latest_variant", "base_canvas"]


def resolve_compile_source(
    session: InteractiveSession,
    source_choice: CompileSourceChoice,
    uploaded_source_path: str | None,
) -> Path:
    if source_choice == "upload":
        if not uploaded_source_path:
            raise ValueError("Upload a finalized source image before compiling.")
        source = Path(uploaded_source_path)
    elif source_choice == "latest_variant":
        image_paths = [
            image_path
            for generation in session.generation_runs
            for image_path in generation.image_paths
        ]
        if not image_paths:
            raise ValueError("No generated variant is available to compile.")
        source = Path(image_paths[-1])
    elif source_choice == "base_canvas":
        if session.edit_target is None:
            raise ValueError("No base canvas is available to compile.")
        source = Path(session.edit_target.base_image_path)
    else:
        raise ValueError(f"Unsupported compile source: {source_choice}")
    if not source.is_file():
        raise ValueError(f"Compile source image does not exist: {source}")
    return source


def compile_session_tile_map(
    session: InteractiveSession,
    *,
    source_choice: CompileSourceChoice,
    uploaded_source_path: str | None,
    compile_mask_path: str | None,
    whole_image: bool,
    max_colors: int | None,
    granularity: Granularity,
    min_region_area_px: int,
    boundary_smoothing: BoundarySmoothing,
    merge_tiny_regions: bool,
    physical_width_cm: float | None,
    physical_height_cm: float | None,
    out_root: str | Path = "runs/workbench",
    color_compactness: float = 5.0,
    minimum_color_area_cm2: float | None = None,
    physical_scale_basis: PhysicalScaleBasis = "mask_bbox",
    enable_tessera: bool = False,
    min_short_edge_mm: float = 8.0,
    target_short_edge_mm: float = 18.0,
    max_long_edge_mm: float = 55.0,
    preferred_aspect_ratio: float = 1.8,
    max_aspect_ratio: float = 4.0,
    flow_strength: FlowStrength = "medium",
    edge_following: EdgeFollowing = "medium",
    shape_style: ShapeStyle = "irregular",
    random_seed: int = 0,
    grout_width_mm: float = 2.0,
    max_tessera_count: int = 3000,
) -> InteractiveSession:
    if not session.selected_palette_ids:
        raise ValueError("Select at least one palette color before compiling.")
    source = resolve_compile_source(session, source_choice, uploaded_source_path)
    if whole_image:
        mask_path = None
    elif compile_mask_path:
        mask_path = compile_mask_path
    elif session.edit_target is not None:
        mask_path = session.edit_target.mask_image_path
    else:
        mask_path = None

    if enable_tessera and (physical_width_cm is None or physical_height_cm is None):
        raise ValueError(
            "Physical width and height are required when tessera subdivision is enabled."
        )
    tessera_options = None
    if enable_tessera:
        tessera_options = TesseraCompileOptions(
            physical_scale_basis=physical_scale_basis,
            min_short_edge_mm=min_short_edge_mm,
            target_short_edge_mm=target_short_edge_mm,
            max_long_edge_mm=max_long_edge_mm,
            preferred_aspect_ratio=preferred_aspect_ratio,
            max_aspect_ratio=max_aspect_ratio,
            flow_strength=flow_strength,
            edge_following=edge_following,
            shape_style=shape_style,
            random_seed=random_seed,
            grout_width_mm=grout_width_mm,
            max_tessera_count=max_tessera_count,
        )

    run_number = len(session.compile_runs) + 1
    output_dir = Path(out_root) / session.session_id / "compilations" / f"run_{run_number:02d}"
    request = PaletteCompileRequest(
        source_image_path=str(source),
        mask_image_path=mask_path,
        palette_db_path=session.palette_db_path,
        selected_palette_ids=session.selected_palette_ids,
        max_colors=max_colors,
        granularity=granularity,
        min_region_area_px=min_region_area_px,
        minimum_color_area_cm2=minimum_color_area_cm2,
        color_compactness=color_compactness,
        boundary_smoothing=boundary_smoothing,
        merge_tiny_regions=merge_tiny_regions,
        strict_palette=True,
        physical_width_cm=physical_width_cm,
        physical_height_cm=physical_height_cm,
        physical_scale_basis=physical_scale_basis,
        tessera_options=tessera_options,
        output_dir=str(output_dir),
    )
    result = compile_palette_map(request)
    return session.model_copy(
        update={
            "accepted_source_image_path": str(source),
            "compile_runs": [*session.compile_runs, result],
            "latest_compile_result": result,
        }
    )


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
