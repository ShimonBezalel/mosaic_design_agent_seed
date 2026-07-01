# Mosaic Design Agent — Design Brief

## Product thesis

A mosaic design agent for Yael should not pretend to be the artist. It should act like a disciplined studio assistant: collect intent, respect the tile palette, ask for missing constraints, generate controlled ideation packages, critique readability/buildability, and prepare material for a human design session.

## First-night goal

Build an agentic loop that can be tested tomorrow with Yael.

The loop should:

1. ingest a project brief;
2. inspect the palette DB;
3. identify missing constraints;
4. ask clarifying questions;
5. produce several ideation directions;
6. generate prompts for image tools;
7. critique each direction against mosaic-specific constraints;
8. export a structured concept package.

## What the agent produces

The first output is not a final mosaic. It is an ideation package:

- one-line concept name;
- artistic intent;
- composition sketch in words;
- foreground/midground/background regions;
- candidate palette subset from Yael's actual tiles;
- mosaic grammar: coarse/fine areas, flow, borders, text preservation;
- image-generation prompts for tools like Nano Banana or OpenAI image generation;
- negative prompts / avoid-list;
- critique notes;
- questions for Yael;
- next revision plan.

## Important distinction

Proposal render: used for taste, client approval, exploration.

Execution plan: used to build the physical mosaic.

The first agent produces proposal/ideation artifacts, but should keep a clear path toward execution planning later.

## Why a text-only palette DB is enough at first

The agent does not need a tile image to reason about color constraints. A curated DB with IDs, hex codes, names, rough inventory, and material notes is enough for ideation.

Example tile record:

```json
{
  "tile_id": "orange_terracotta_01",
  "name": "terracotta orange",
  "hex": "#C9552B",
  "inventory_level": "high",
  "surface": "matte",
  "notes": "good for desert ground and warm borders"
}
```

Later, photos can improve color calibration and material rendering, but they are not required for tomorrow.

## Core failure modes to avoid

- Pretty image that ignores actual palette.
- Tiny visual details impossible in broken tiles.
- Text that looks good in generated image but fails in mosaic.
- Too many colors for field execution.
- No explicit distinction between locked regions and flexible artistic regions.
- Agent overconfidently fabricating missing context.

## First demo success criterion

A successful demo is when Yael says one of these:

- "This asks the right questions."
- "This feels like it understands my workflow."
- "This gives me directions I can react to."
- "This could save me time preparing options for a public project."

The generated visuals may be imperfect. The loop should still feel useful.
