from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import Field

from mosaic_agent.models import Concept, ProjectBrief, ReferenceImageRole, StrictModel
from mosaic_agent.tile_map_models import PaletteCompileResult


class ReferenceAsset(StrictModel):
    asset_id: str
    path: str
    role: ReferenceImageRole
    notes: str = ""


class EditTarget(StrictModel):
    base_image_path: str
    mask_image_path: str
    mode: Literal["inpaint", "full_edit", "reference_only"] = "inpaint"
    overlay_preview_path: str = ""


class GenerationRun(StrictModel):
    concept_id: str
    provider: str
    prompt: str
    image_paths: list[str] = Field(default_factory=list)
    mode: Literal["inpaint", "full_edit", "reference_only"] = "inpaint"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    revision_notes: str = ""
    metadata: dict[str, object] = Field(default_factory=dict)


class InteractiveSession(StrictModel):
    session_id: str
    brief: ProjectBrief
    palette_db_path: str
    selected_palette_ids: list[str] = Field(default_factory=list)
    reference_assets: list[ReferenceAsset] = Field(default_factory=list)
    edit_target: EditTarget | None = None
    concepts: list[Concept] = Field(default_factory=list)
    selected_concept_id: str | None = None
    generation_runs: list[GenerationRun] = Field(default_factory=list)
    accepted_source_image_path: str | None = None
    compile_runs: list[PaletteCompileResult] = Field(default_factory=list)
    latest_compile_result: PaletteCompileResult | None = None
    critique: list[str] = Field(default_factory=list)
    notes: str = ""
