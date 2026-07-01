---
name: visual-critique
description: Use when reviewing generated mosaic concepts for readability, palette adherence, and buildability.
---

# Visual Critique

## Purpose

Critique ideation results before the artist wastes time on them.

## Rubric

Score 1–5:

- palette adherence;
- distance readability;
- tile buildability;
- text survivability;
- Yael-style fit;
- emotional fit;
- novelty;
- risk.

## Specific checks

### Palette

- Are all colors in the palette DB?
- Are large areas assigned high-inventory colors?
- Are rare colors used as accents?

### Mosaic buildability

- Are there too many tiny semantic details?
- Can shard boundaries follow the drawing?
- Are gradients plausible with the palette?

### Public entrance readability

- Is the main message readable from road distance?
- Does the focal symbol survive at a glance?
- Is the Hebrew text treated as locked geometry?

### Artist fit

- Does it preserve handmade irregularity?
- Does it allow Yael's hand to interpret regions?
- Is it too mechanically generated?

## Output format

```json
{
  "scores": {},
  "strong_points": [],
  "risks": [],
  "revision_suggestions": [],
  "questions_for_artist": []
}
```
