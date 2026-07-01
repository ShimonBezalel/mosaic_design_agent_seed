from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mosaic_agent.reference_images import ensure_reference_images_exist


ReferenceImageRole = Literal[
    "artist_style_reference",
    "canvas_photo",
    "site_context",
    "palette_photo",
    "composition_sketch",
    "generated_brief_moodboard",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Canvas(StrictModel):
    type: str
    width_cm: float | None = None
    height_cm: float | None = None
    depth_cm: float | None = None
    shape_notes: str = ""
    photo_paths: list[str] = Field(default_factory=list)


class ProjectBrief(StrictModel):
    project_name: str
    location: str
    intent: str
    required_text: list[str] = Field(default_factory=list)
    desired_mood: list[str] = Field(default_factory=list)
    must_include: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    viewing_distance_m: float | None = None
    granularity: Literal["coarse", "medium", "fine", "mixed", "unknown"] = "unknown"
    canvas: Canvas
    reference_image_paths: list[str] = Field(default_factory=list)
    reference_image_roles: list[ReferenceImageRole] = Field(default_factory=list)
    desired_outputs: list[
        Literal["questions", "concepts", "image_prompts", "image_renders", "critique", "execution_notes"]
    ]
    notes: str = ""

    @model_validator(mode="after")
    def default_and_validate_reference_roles(self) -> "ProjectBrief":
        if self.reference_image_paths and not self.reference_image_roles:
            self.reference_image_roles = ["artist_style_reference" for _ in self.reference_image_paths]
        if len(self.reference_image_roles) != len(self.reference_image_paths):
            raise ValueError("reference_image_roles must match reference_image_paths length")
        return self


class Tile(StrictModel):
    tile_id: str
    name: str
    hex: str
    inventory_level: Literal["low", "medium", "high", "unknown"]
    surface: Literal["matte", "gloss", "mixed", "unknown"] = "unknown"
    material: str = ""
    break_profile: Literal["large", "medium", "small", "splintery", "mixed", "unknown"] = "unknown"
    preferred_uses: list[str] = Field(default_factory=list)
    avoid_uses: list[str] = Field(default_factory=list)
    notes: str = ""


class PaletteDB(StrictModel):
    version: str
    source: str = ""
    notes: str = ""
    tiles: list[Tile]

    @field_validator("tiles")
    @classmethod
    def require_unique_tile_ids(cls, tiles: list[Tile]) -> list[Tile]:
        ids = [tile.tile_id for tile in tiles]
        duplicates = sorted({tile_id for tile_id in ids if ids.count(tile_id) > 1})
        if duplicates:
            raise ValueError(f"duplicate tile IDs: {', '.join(duplicates)}")
        return tiles


class ImagePrompts(StrictModel):
    openai: str = ""
    gemini_nano_banana: str = ""
    negative_prompt: str = ""


class ImageGenerationRequest(StrictModel):
    provider: str
    concept_id: str
    variant_id: str = "variant_01"
    prompt: str
    negative_prompt: str = ""
    input_image_paths: list[str] = Field(default_factory=list)
    input_image_roles: list[ReferenceImageRole] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_input_images(self) -> "ImageGenerationRequest":
        if self.input_image_paths and not self.input_image_roles:
            self.input_image_roles = ["artist_style_reference" for _ in self.input_image_paths]
        if len(self.input_image_roles) != len(self.input_image_paths):
            raise ValueError("input_image_roles must match input_image_paths length")
        ensure_reference_images_exist(self.input_image_paths)
        return self


class ImageGenerationResult(StrictModel):
    provider: str
    concept_id: str
    variant_id: str = "variant_01"
    status: str
    image_path: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class CritiqueScores(StrictModel):
    palette_adherence: int = Field(ge=1, le=5)
    distance_readability: int = Field(ge=1, le=5)
    tile_buildability: int = Field(ge=1, le=5)
    text_survivability: int = Field(ge=1, le=5)
    style_fit: int = Field(ge=1, le=5)
    novelty: int = Field(ge=1, le=5)


class Critique(StrictModel):
    scores: CritiqueScores
    notes: list[str]
    risks: list[str]


class Concept(StrictModel):
    concept_id: str
    name: str
    intent: str
    composition: str
    locked_elements: list[str] = Field(default_factory=list)
    flexible_elements: list[str] = Field(default_factory=list)
    mosaic_grammar: str = ""
    palette_tile_ids: list[str]
    image_prompts: ImagePrompts
    image_results: list[dict[str, Any]] = Field(default_factory=list)
    critique: Critique


class ConceptPackage(StrictModel):
    run_id: str
    project_name: str
    mode: Literal[
        "stub",
        "real_model_stub_images",
        "real_images",
        "openai-image",
        "openai-responses-image",
        "gemini-image",
    ] = "stub"
    ideation_mode: Literal["stub", "openai"] = "stub"
    image_mode: Literal["stub", "openai-image", "openai-responses-image", "gemini-image"] = "stub"
    assumptions: list[str]
    questions: list[str]
    palette_summary: str = ""
    concepts: list[Concept]
    recommended_next_step: str


class VisualCritique(StrictModel):
    strongest_visual_idea: str
    palette_fit: str
    feasibility_for_broken_tiles: str
    readability_from_distance: str
    text_risk: str
    ask_yael: str


class VisualManifestImage(StrictModel):
    provider: str
    concept_id: str
    concept_name: str
    variant_id: str
    image_path: str
    prompt: str
    negative_prompt: str
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    critique: VisualCritique


class VisualManifestInputReference(StrictModel):
    role: ReferenceImageRole
    source_path: str
    image_path: str


class VisualManifest(StrictModel):
    run_id: str
    provider: str
    ideation_mode: Literal["stub", "openai"] = "stub"
    image_mode: Literal["stub", "openai-image", "openai-responses-image", "gemini-image"] = "stub"
    project_name: str
    location: str
    reference_image_paths: list[str] = Field(default_factory=list)
    input_references: list[VisualManifestInputReference] = Field(default_factory=list)
    images: list[VisualManifestImage]


class RunTraceEvent(StrictModel):
    event_type: str
    timestamp: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)


class RunTrace(StrictModel):
    run_id: str
    events: list[RunTraceEvent]
