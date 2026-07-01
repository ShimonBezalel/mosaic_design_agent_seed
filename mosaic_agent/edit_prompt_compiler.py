from __future__ import annotations

from mosaic_agent.models import Concept, PaletteDB, ProjectBrief
from mosaic_agent.palette import validate_tile_ids


def compile_edit_prompt(
    concept: Concept,
    brief: ProjectBrief,
    palette: PaletteDB,
    *,
    revision_notes: str = "",
) -> str:
    validate_tile_ids(concept.palette_tile_ids, palette)
    tiles_by_id = {tile.tile_id: tile for tile in palette.tiles}
    palette_text = "; ".join(
        f"{tiles_by_id[tile_id].name} ({tiles_by_id[tile_id].hex})"
        for tile_id in concept.palette_tile_ids
    )
    lettering = _lettering_rule(brief)
    revision = f" Requested revision: {revision_notes.strip()}." if revision_notes.strip() else ""
    return (
        "Edit only the transparent masked region of the supplied base image and preserve the unmasked stone, "
        "camera viewpoint, surrounding site, lighting, and proportions. Create a public entrance stone proposal "
        f"for the concept '{concept.name}'. Concept thesis: {concept.intent} Composition: {concept.composition} "
        "Render a broken ceramic tile mosaic with irregular hand-built shards, visible grout and negative space, "
        "broad readable forms from road distance, and a palette-constrained design language. "
        f"Use only these palette colors: {palette_text}. {lettering} "
        "Keep the result handmade and executable in spirit, while clearly treating it as a proposal image, not "
        f"an exact construction plan.{revision}"
    )


def _lettering_rule(brief: ProjectBrief) -> str:
    if _has_hebrew_text(brief):
        return (
            "Do not render Hebrew letters, fake Hebrew, pseudo-text, pseudo-Hebrew, glyph-like marks, or any "
            "written characters. Reserve a completely blank high-contrast lettering field, ribbon, or arc for "
            "manual lettering later."
        )
    if brief.required_text:
        return (
            "Do not render final lettering or pseudo-text. Reserve a completely blank high-contrast lettering "
            "field for manual lettering later."
        )
    return "Do not add text or pseudo-text."


def _has_hebrew_text(brief: ProjectBrief) -> bool:
    return any("\u0590" <= char <= "\u05FF" for text in brief.required_text for char in text)
