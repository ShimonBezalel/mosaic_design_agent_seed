# Agentic Reference-Aware Ideation Design

## Correction

The current harness exports useful artifacts, but image modes still use deterministic concepts. The next version must split concept ideation from image generation:

- `--ideation-mode stub|openai`
- `--image-mode stub|openai-image|openai-responses-image|gemini-image`

Stub ideation keeps the deterministic concept set for CI. OpenAI ideation calls a vision/text-capable model and asks for structured concept JSON grounded in the project brief, palette DB, and short reference-image summaries.

## Data Flow

1. Load and validate brief and palette.
2. Validate all reference image paths in the brief.
3. If `ideation-mode=stub`, generate the current deterministic concepts.
4. If `ideation-mode=openai`, call the Responses API with structured JSON instructions and image inputs for references when present.
5. Limit concepts with `--concept-limit`.
6. Compile visual prompts using the concept, selected palette tiles, brief, and reference metadata.
7. Generate `--variants-per-concept` images with the selected image provider.
8. Export concept package, markdown files, manifest, images, and contact sheet.

## Image Input Support

`ImageGenerationRequest` gets:

- `input_image_paths: list[str]`
- `input_image_roles: list[str]`

Roles are one of:

- `artist_style_reference`
- `canvas_photo`
- `site_context`
- `palette_photo`
- `composition_sketch`
- `generated_brief_moodboard`

All local paths must exist before provider calls. The manifest records input references, and the contact sheet renders thumbnails grouped by role.

## Providers

`OpenAIImageProvider` remains the text-only Images API canary.

`OpenAIResponsesImageProvider` calls `/v1/responses` with:

- a mainline model from `--image-model` or env;
- `tools: [{"type": "image_generation", ...}]`;
- `tool_choice: {"type": "image_generation"}`;
- `input_text` prompt content;
- `input_image` items using local image files encoded as base64 data URLs.

It extracts the first `image_generation_call.result`, writes a PNG, and captures `revised_prompt` when present. Missing keys and provider/billing failures are reported without stack traces.

`gemini-image` keeps its adapter path and is not expanded beyond the existing best effort in this pass.

## Cost Controls

CLI flags:

- `--concept-limit`, default `3`
- `--variants-per-concept`, default `2`
- `--image-size`, default `1536x1024`
- `--image-quality`, default `low`
- `--image-model`, default from env or a sensible provider default

The real canary uses `concept-limit=1`, `variants-per-concept=1`, `quality=low`, and no more than one image generation call.

## Prompt Rules

The prompt compiler must ask for:

- public entrance stone concept render;
- broken ceramic tile mosaic;
- irregular hand-built shards;
- visible grout / negative space;
- broad readable forms from road distance;
- natural stone canvas;
- palette-constrained color language;
- proposal image, not exact construction plan.

If Hebrew text is requested, do not ask the image model to render final Hebrew. Ask for a high-contrast reserved lettering field, ribbon, or arc, with optional abstract placeholder blocks. Critique must state that Hebrew lettering must be manually redrawn/vectorized.

## Contact Sheet

The contact sheet shows a visible warning:

> Generated images are visual ideation only. They are not a construction-ready mosaic plan.

It shows input reference thumbnails first, grouped by role, then concepts and variants.

## Tests

Keep existing tests green. Add stub tests for:

- stub ideation plus stub image mode runs with no API keys;
- image input paths are validated;
- manifest includes input references;
- contact sheet shows reference thumbnails;
- concept limit and variants per concept work;
- real provider tests remain skipped unless env vars are set.
