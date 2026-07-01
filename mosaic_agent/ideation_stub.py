from __future__ import annotations

from mosaic_agent.critique import build_stub_critique
from mosaic_agent.models import Concept, ImageGenerationRequest, ImagePrompts, PaletteDB, ProjectBrief
from mosaic_agent.palette import select_existing_tile_ids, validate_tile_ids
from mosaic_agent.providers.base import ImageProvider


COMMON_NEGATIVE_PROMPT = (
    "Avoid colors outside the supplied tile palette, tiny details, photorealistic printed text, "
    "smooth digital gradients, perfect pixel-grid tessellation, and generic stock-art symbols."
)


def generate_stub_concepts(brief: ProjectBrief, palette: PaletteDB, image_provider: ImageProvider) -> list[Concept]:
    concepts = [
        _desert_sunrise(brief, palette, image_provider),
        _path_into_community(brief, palette, image_provider),
        _typography_ribbon(brief, palette, image_provider),
    ]
    for concept in concepts:
        validate_tile_ids(concept.palette_tile_ids, palette)
    return concepts


def _required_text(brief: ProjectBrief) -> str:
    return ", ".join(brief.required_text) if brief.required_text else "artist-confirmed welcome text"


def _build_prompts(name: str, brief: ProjectBrief, palette: PaletteDB, composition_hint: str) -> ImagePrompts:
    palette_lines = ", ".join(f"{tile.tile_id} {tile.hex}" for tile in palette.tiles)
    openai = (
        f"Proposal render for a broken-tile public mosaic called '{name}' for {brief.location}. "
        f"Intent: {brief.intent} Composition: {composition_hint} "
        f"Required Hebrew text treated as locked, hand-drawn mosaic geometry: {_required_text(brief)}. "
        f"Use only these palette tile IDs and colors: {palette_lines}. "
        "Show broad shard regions, readable lettering, handmade irregularity, and a natural stone face."
    )
    gemini = (
        f"Create a mosaic concept study for '{name}' on a large entrance stone. "
        f"Palette locked to: {palette_lines}. "
        f"Text must remain legible: {_required_text(brief)}. "
        f"Composition notes: {composition_hint} Keep details coarse enough for broken tile."
    )
    return ImagePrompts(openai=openai, gemini_nano_banana=gemini, negative_prompt=COMMON_NEGATIVE_PROMPT)


def _image_result(provider: ImageProvider, concept_id: str, prompts: ImagePrompts) -> list[dict[str, object]]:
    request = ImageGenerationRequest(
        provider="stub",
        concept_id=concept_id,
        prompt=prompts.openai,
        negative_prompt=prompts.negative_prompt,
    )
    return [provider.generate(request).model_dump(mode="json")]


def _desert_sunrise(brief: ProjectBrief, palette: PaletteDB, image_provider: ImageProvider) -> Concept:
    name = "Desert Sunrise Welcome"
    concept_id = "concept_01_desert_sunrise_welcome"
    tile_ids = select_existing_tile_ids(
        [
            "terracotta_orange_01",
            "burnt_orange_02",
            "dusty_pink_01",
            "lavender_gray_01",
            "sun_yellow_01",
            "cream_01",
            "sand_01",
            "off_white_01",
            "dark_brown_01",
            "turquoise_01",
        ],
        palette,
    )
    composition = (
        "A broad desert horizon wraps the stone, with a rising sun arc behind the welcome text. "
        "Warm sky bands move from sand and terracotta into dusty pink and lavender gray, while cream/off-white "
        "lettering sits in a stable central field."
    )
    prompts = _build_prompts(name, brief, palette, composition)
    return Concept(
        concept_id=concept_id,
        name=name,
        intent="Make the town entrance feel warm, local, optimistic, and immediately readable from the road.",
        composition=composition,
        locked_elements=[f"Hebrew text: {_required_text(brief)}", "Large sunrise arc", "High-contrast lettering field"],
        flexible_elements=["Exact sky band count", "Sun position", "Small desert texture accents"],
        mosaic_grammar=(
            "Use coarse shard bands for sky and desert, radial flow around the sun, and clean dark-brown shadowing "
            "only where needed to protect letter readability."
        ),
        palette_tile_ids=tile_ids,
        image_prompts=prompts,
        image_results=_image_result(image_provider, concept_id, prompts),
        critique=build_stub_critique(name, brief),
    )


def _path_into_community(brief: ProjectBrief, palette: PaletteDB, image_provider: ImageProvider) -> Concept:
    name = "Path Into Community"
    concept_id = "concept_02_path_into_community"
    tile_ids = select_existing_tile_ids(
        [
            "sand_01",
            "cream_01",
            "terracotta_orange_01",
            "burnt_orange_02",
            "olive_green_01",
            "deep_green_01",
            "turquoise_01",
            "pale_mint_01",
            "dark_brown_01",
            "off_white_01",
            "sun_yellow_01",
        ],
        palette,
    )
    composition = (
        "A light cream path enters from the lower edge and curves toward the Hebrew welcome, with local vegetation "
        "and desert color fields on both sides. The path is the main shape, not a detailed scene."
    )
    prompts = _build_prompts(name, brief, palette, composition)
    return Concept(
        concept_id=concept_id,
        name=name,
        intent="Frame the entrance as an invitation into a living community while staying buildable on an irregular stone.",
        composition=composition,
        locked_elements=[f"Hebrew text: {_required_text(brief)}", "Single broad path gesture", "Clear entrance direction"],
        flexible_elements=["Amount of vegetation", "Path width", "Accent placement"],
        mosaic_grammar=(
            "Align shard flow along the path curve. Use high-inventory sand and cream for large areas, with greens "
            "and turquoise reserved for accents and boundary highlights."
        ),
        palette_tile_ids=tile_ids,
        image_prompts=prompts,
        image_results=_image_result(image_provider, concept_id, prompts),
        critique=build_stub_critique(name, brief),
    )


def _typography_ribbon(brief: ProjectBrief, palette: PaletteDB, image_provider: ImageProvider) -> Concept:
    name = "Typography Stone Ribbon"
    concept_id = "concept_03_typography_stone_ribbon"
    tile_ids = select_existing_tile_ids(
        [
            "off_white_01",
            "cream_01",
            "dark_brown_01",
            "deep_blue_01",
            "terracotta_orange_01",
            "burnt_orange_02",
            "lavender_gray_01",
            "sand_01",
            "turquoise_01",
            "pale_mint_01",
        ],
        palette,
    )
    composition = (
        "The welcome text becomes the main design, set into a sweeping ribbon of cream and off-white stones. "
        "Terracotta, lavender, blue, and turquoise bands frame the ribbon and adapt to the stone's outline."
    )
    prompts = _build_prompts(name, brief, palette, composition)
    return Concept(
        concept_id=concept_id,
        name=name,
        intent="Prioritize text survivability and a strong graphic entrance identity while preserving handmade tile flow.",
        composition=composition,
        locked_elements=[f"Hebrew text: {_required_text(brief)}", "Ribbon baseline", "Letter stroke contrast"],
        flexible_elements=["Ribbon thickness", "Color band sequence", "Accent rhythm around the stone edge"],
        mosaic_grammar=(
            "Treat letters as locked geometry with wide strokes. Let surrounding ribbon bands carry motion, using "
            "dark brown sparingly for contrast and avoiding small decorative symbols."
        ),
        palette_tile_ids=tile_ids,
        image_prompts=prompts,
        image_results=_image_result(image_provider, concept_id, prompts),
        critique=build_stub_critique(name, brief),
    )
