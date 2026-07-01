from __future__ import annotations

from dataclasses import dataclass

from mosaic_agent.models import Concept, PaletteDB, ProjectBrief, Tile
from mosaic_agent.palette import validate_tile_ids


@dataclass(frozen=True)
class CompiledVisualPrompt:
    prompt: str
    negative_prompt: str
    has_hebrew_text: bool


def compile_visual_prompt(
    concept: Concept,
    brief: ProjectBrief,
    palette: PaletteDB,
    *,
    variant_index: int,
) -> CompiledVisualPrompt:
    validate_tile_ids(concept.palette_tile_ids, palette)
    selected_tiles = _selected_tiles(concept, palette)
    palette_text = "; ".join(f"{tile.name} ({tile.hex}) [{tile.tile_id}]" for tile in selected_tiles)
    required_text = ", ".join(brief.required_text) if brief.required_text else "no confirmed lettering"
    reference_text = ", ".join(brief.reference_image_paths) if brief.reference_image_paths else "none"
    variant_direction = _variant_direction(variant_index)
    has_hebrew = _has_hebrew_text(brief)

    prompt = (
        f"Create variant {variant_index} of a proposal image, not a final exact construction plan, for a "
        f"broken ceramic tile mosaic concept named '{concept.name}'. The work is for a public entrance stone "
        f"at {brief.location}, using a natural canvas context and preserving large-scale readability from "
        f"approximately {brief.viewing_distance_m or 'unknown'} meters. "
        f"Design intent: {concept.intent} Composition: {concept.composition} Mosaic grammar: {concept.mosaic_grammar} "
        f"Use only these real palette colors from the palette DB by name and hex: {palette_text}. "
        f"Requested text/lettering to include as hand-drawn mosaic geometry: {required_text}. "
        f"Reference image paths available for context: {reference_text}. "
        f"{variant_direction} Make visible grout and negative-space part of the design. "
        f"Make the design feel hand-built, irregular, "
        f"and executable with broken ceramic tile, with broad readable shapes and controlled accents."
    )
    if has_hebrew:
        prompt += (
            " Hebrew lettering should be treated as approximate placement only; final lettering must be manually "
            "redrawn or vectorized by the artist."
        )

    negative_prompt = (
        "avoid pixel art; avoid photomosaic; avoid overly tiny details; avoid smooth digital gradients; "
        "avoid colors outside the supplied palette; avoid perfect machine-cut tessellation; "
        "avoid treating this as a final construction plan"
    )
    return CompiledVisualPrompt(prompt=prompt, negative_prompt=negative_prompt, has_hebrew_text=has_hebrew)


def _selected_tiles(concept: Concept, palette: PaletteDB) -> list[Tile]:
    tiles_by_id = {tile.tile_id: tile for tile in palette.tiles}
    return [tiles_by_id[tile_id] for tile_id in concept.palette_tile_ids]


def _variant_direction(variant_index: int) -> str:
    if variant_index == 1:
        return "Emphasize the full stone composition and road-distance silhouette."
    return "Emphasize material texture, shard flow, and color grouping while keeping the same concept."


def _has_hebrew_text(brief: ProjectBrief) -> bool:
    return any("\u0590" <= char <= "\u05FF" for text in brief.required_text for char in text)
