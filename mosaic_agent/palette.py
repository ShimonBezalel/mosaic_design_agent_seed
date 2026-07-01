from __future__ import annotations

from collections import defaultdict

from mosaic_agent.models import PaletteDB


def palette_tile_ids(palette: PaletteDB) -> set[str]:
    return {tile.tile_id for tile in palette.tiles}


def validate_tile_ids(tile_ids: list[str], palette: PaletteDB) -> None:
    missing = sorted(set(tile_ids) - palette_tile_ids(palette))
    if missing:
        raise ValueError(f"selected tile IDs are not in palette DB: {', '.join(missing)}")


def summarize_palette(palette: PaletteDB) -> str:
    by_inventory: dict[str, list[str]] = defaultdict(list)
    for tile in palette.tiles:
        by_inventory[tile.inventory_level].append(f"{tile.tile_id} ({tile.name}, {tile.hex})")

    parts: list[str] = []
    for level in ["high", "medium", "low", "unknown"]:
        tiles = by_inventory.get(level)
        if tiles:
            parts.append(f"{level}: {', '.join(tiles)}")
    return "; ".join(parts)


def select_existing_tile_ids(preferred_ids: list[str], palette: PaletteDB, minimum: int = 8) -> list[str]:
    available = palette_tile_ids(palette)
    selected = [tile_id for tile_id in preferred_ids if tile_id in available]

    for tile in palette.tiles:
        if len(selected) >= minimum:
            break
        if tile.tile_id not in selected:
            selected.append(tile.tile_id)

    if len(selected) < minimum:
        raise ValueError(f"palette must contain at least {minimum} tiles for stub concept generation")
    return selected
