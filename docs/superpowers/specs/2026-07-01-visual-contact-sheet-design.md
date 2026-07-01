# Visual Contact Sheet Design

## Goal

Add a thin visual ideation pass to the existing deterministic concept loop. A single command should generate six proposal images, a static contact sheet, and a manifest from the palette DB, project brief, reference image paths, and selected image provider.

## Command

```bash
python -m mosaic_agent.demo \
  --palette examples/palette_db.example.json \
  --brief examples/project_brief.example.json \
  --mode openai-image \
  --allow-assumptions \
  --out runs/visual_001
```

Supported modes:

- `stub`: deterministic placeholder PNGs, no API key, no network calls.
- `openai-image`: real OpenAI image adapter. If `OPENAI_API_KEY` is absent, fail with a clear CLI message.
- `gemini-image`: real Gemini image adapter. If a Gemini API key is absent, fail with a clear CLI message.

Real image modes call the provider immediately when credentials are present. Each run generates exactly two variants for each of the three existing concepts.

## Architecture

Keep `mosaic_agent.demo` as the only CLI entrypoint. The run still loads the brief and palette, checks missing critical fields, generates the three deterministic concept directions, and exports the existing markdown artifacts.

Add these focused modules:

- `prompt_compiler.py`: compiles each concept into provider-ready visual prompts using only the selected palette tiles.
- `visual.py`: coordinates variant generation, records manifest entries, and calls contact sheet export.
- provider adapters: `StubImageProvider`, `OpenAIImageProvider`, and `GeminiNanoBananaProvider` share one interface that writes image files and returns metadata.

The provider interface should accept a prompt request and output path. This is clearer than returning opaque metadata and lets tests verify file artifacts directly.

## Prompt Requirements

Every visual prompt includes:

- selected palette tile names and hex colors from the actual palette DB;
- broken ceramic tile mosaic aesthetic;
- public entrance stone / natural canvas context;
- large-scale readability;
- visible grout and negative space;
- hand-built, irregular, executable proposal language;
- warning that this is a proposal image, not a final construction plan;
- negative guidance to avoid pixel art, photomosaic, overly tiny details, and non-palette colors.

If Hebrew lettering is in `required_text`, include the text in the prompt. Also add critique text that AI-generated lettering may be unreliable and should be manually redrawn/vectorized.

Reference image paths from the brief are included as context strings in the prompt. The first implementation does not need provider-specific image upload or edit flows.

## Outputs

Each run writes:

- `concept_package.json`
- `artist_questions.md`
- `image_prompts.md`
- `critique.md`
- `contact_sheet.html`
- `visual_manifest.json`
- `images/concept_01_variant_01.png`
- `images/concept_01_variant_02.png`
- `images/concept_02_variant_01.png`
- `images/concept_02_variant_02.png`
- `images/concept_03_variant_01.png`
- `images/concept_03_variant_02.png`

`visual_manifest.json` is the authoritative index for generated images. It records provider mode, concept ID/name, variant ID, prompt text, relative image path, status, and provider metadata.

## Contact Sheet

The contact sheet is static HTML with no frontend framework. It shows:

- brief summary;
- palette swatches;
- generated images grouped by concept;
- prompt details under each image;
- critique sections;
- questions for Yael.

Styling should be minimal and readable. It is an inspection artifact, not a polished application.

## Critique

Each image/concept gets short critique fields:

- strongest visual idea;
- palette fit;
- feasibility for broken tiles;
- readability from distance;
- text risk;
- what to ask Yael.

The first implementation can derive these deterministically from the concept and prompt, not from computer vision.

## Testing

Keep all existing tests. Add stub-mode tests that prove:

- `contact_sheet.html` exists;
- six placeholder PNG files exist;
- `visual_manifest.json` lists all six image paths;
- concept palette IDs are still grounded in the palette DB;
- prompt compiler includes palette names and hex values;
- real provider tests are skipped unless the matching environment variables exist.

## Explicit Non-Goals

- No mosaic compiler.
- No AR/tablet workflow.
- No elaborate report styling.
- No provider-specific reference image upload in the first pass.
- No fake SVG artwork beyond deterministic stub placeholders.
