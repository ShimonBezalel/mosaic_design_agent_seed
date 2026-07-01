---
name: palette-grounding
description: Use when an agent must constrain mosaic ideation to a real text-only tile palette database.
---

# Palette Grounding

## Purpose

Prevent visual hallucination by grounding concept directions in the available tile palette.

## Rules

- Never invent tile colors.
- Use tile IDs from the palette DB in every concept.
- Prefer high-inventory tiles for large regions.
- Use low-inventory tiles only as accents or highlights.
- Prefer off-white/cream/high-contrast colors for Hebrew lettering.
- Do not propose fine gradients unless the palette has enough adjacent colors.
- If a concept requires unavailable colors, either remap to nearest available tile or flag the issue.

## Process

1. Summarize palette by hue family and inventory level.
2. Select 8–14 candidate tiles for each concept.
3. Explain why each family is used.
4. Flag missing colors.
5. Check that all referenced tile IDs exist.

## Output format

```json
{
  "palette_summary": "...",
  "selected_tile_ids": [],
  "large_region_tile_ids": [],
  "accent_tile_ids": [],
  "lettering_tile_ids": [],
  "warnings": []
}
```
