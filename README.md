# Mosaic Design Agent Seed

This repo seed is for building a first-night prototype of a human-in-the-loop mosaic ideation agent for Yael's broken-tile public-art workflow.

The goal is not to implement the mosaic compiler yet. The first build should prove an agentic design loop:

1. collect a project brief from the artist/user;
2. ground itself in a text-only tile palette DB;
3. ask missing questions instead of hallucinating;
4. call visual ideation tools through swappable adapters;
5. return structured ideation packages: composition briefs, image-generation prompts, palette constraints, critique notes, and next questions;
6. run the same loop in stub mode for fast smoke testing and real mode for tomorrow's Yael experiment.

## Local Gradio workbench

Install the package and launch the interactive workbench:

```bash
python -m pip install -e .
python -m mosaic_workbench.app --demo
```

Open `http://127.0.0.1:7860`. Without `--demo`, the same command starts with an empty session:

```bash
python -m mosaic_workbench.app
```

The workbench supports:

- palette DB loading and working palette selection;
- brief entry without editing JSON;
- base canvas, site context, style reference, and composition sketch uploads;
- uploaded masks or browser-drawn masks;
- automatic PNG mask normalization, alpha-channel handling, and overlay preview;
- three stub or OpenAI-generated concept directions;
- concept selection;
- one or three masked edit variants;
- session export with brief, concept, prompts, critique, base image, mask, references, variants, and manifest.

Stub mode needs no API key. Real concept ideation and masked edits use:

```bash
export OPENAI_API_KEY="..."
```

Choose `openai` under **Ideation mode** for real concept planning and `openai-edit` under **Image edit mode** for a real masked Image API edit.

Mask rules:

- the normalized mask always matches the base image dimensions;
- uploaded alpha masks use transparent pixels as the editable region;
- uploaded black/white masks use white as the editable region;
- browser-drawn strokes become the editable region;
- the normalized mask is saved as an RGBA PNG.

Generated images are visual ideation only. They are not a construction-ready mosaic plan. Hebrew lettering is deliberately left as a blank high-contrast field for manual drawing or vectorization.

## Recommended runtime choice

Use OpenAI Agents SDK as the initial runtime. Reasons:

- Python-first implementation path for a local prototype.
- Native agent concepts: agents, tools, handoffs, sessions, guardrails, tracing.
- Good fit for structured outputs and trace-driven debugging.
- OpenAI image generation can run through the Responses API as a built-in tool, while Gemini/Nano Banana can be wrapped as a custom function tool.

Keep the tool layer provider-agnostic so Anthropic Claude Agent SDK can be swapped in later. Anthropic is especially attractive for Claude Code-style repo automation, skills, subagents, and MCP-heavy workflows; but for this particular product runtime, OpenAI is likely the faster first build.

## Non-goals for the first build

- No full mosaic tessellation compiler yet.
- No AR/tablet field execution.
- No automatic 3D stone scan.
- No claim that the generated image is physically executable.
- No unreviewed autonomous publishing or spending.

## Suggested implementation phases for Codex

### Phase 0 — Repo skeleton and contracts
Create a small Python package with Pydantic models matching `schemas/` and a CLI entrypoint.

### Phase 1 — Stub loop
Make the agent run with deterministic fake tool responses. It should pass smoke tests without API keys.

### Phase 2 — OpenAI real loop
Add OpenAI Responses API orchestration for structured concept planning with optional reference images, while keeping the provider layer narrow and testable.

### Phase 3 — Image provider adapter
Add provider abstraction:

- `StubImageProvider`
- `OpenAIImageProvider`
- `OpenAIResponsesImageProvider`
- `GeminiNanoBananaProvider`

Only the stub provider is required for the first CI pass.

### Phase 4 — Tomorrow demo mode
Add one command that runs an interactive session using `examples/palette_db.example.json` and exports a timestamped concept package.

## Immediate demo command target

Run the deterministic stub loop with no API keys:

```bash
python -m mosaic_agent.demo \
  --palette examples/palette_db.example.json \
  --brief examples/project_brief.example.json \
  --ideation-mode stub \
  --image-mode stub \
  --allow-assumptions \
  --out runs/demo_001
```

Expected outputs:

- `runs/demo_001/concept_package.json`
- `runs/demo_001/artist_questions.md`
- `runs/demo_001/image_prompts.md`
- `runs/demo_001/critique.md`
- `runs/demo_001/contact_sheet.html`
- `runs/demo_001/visual_manifest.json`

Stub mode makes no external API calls. If critical brief fields are missing and `--allow-assumptions` is not passed, the command writes `artist_questions.md` and stops before generating concepts. `run_trace.json` is not written by default in stub mode; platform traces or a later explicit trace mode can cover automated runs.

## Visual contact sheet

Generate the full visual artifact set with deterministic placeholder images:

```bash
python -m mosaic_agent.demo \
  --palette examples/palette_db.example.json \
  --brief examples/project_brief.example.json \
  --ideation-mode stub \
  --image-mode stub \
  --allow-assumptions \
  --out runs/visual_001_stub
```

Generate real OpenAI image variants when `OPENAI_API_KEY` is available:

```bash
python -m mosaic_agent.demo \
  --palette examples/palette_db.example.json \
  --brief examples/project_brief.example.json \
  --ideation-mode stub \
  --image-mode openai-image \
  --allow-assumptions \
  --concept-limit 1 \
  --variants-per-concept 1 \
  --image-quality low \
  --image-size 1024x1024 \
  --out runs/visual_001
```

Generate a reference-aware canary with OpenAI ideation and the Responses image tool:

```bash
python -m mosaic_agent.demo \
  --palette examples/palette_db.example.json \
  --brief examples/real_image_fixtures/briefs/project_brief.real_image_fixture.json \
  --ideation-mode openai \
  --image-mode openai-responses-image \
  --allow-assumptions \
  --concept-limit 1 \
  --variants-per-concept 1 \
  --image-quality low \
  --image-size 1536x1024 \
  --out runs/openai_reference_canary_001
```

`--image-mode openai-image` uses the Images API for text-only canaries. `--image-mode openai-responses-image` uses the Responses API image generation tool and passes reference images as base64 input images. `--image-mode gemini-image` uses `GEMINI_API_KEY` or `GOOGLE_API_KEY`. Missing keys fail with a clear provider configuration message. Provider-side failures, such as billing limits, are reported without a Python stack trace.

`--mode` still exists as a legacy shortcut and maps to `--ideation-mode stub` plus the selected image mode. Prefer the split flags for new work.

Visual runs write:

- `contact_sheet.html`
- `visual_manifest.json`
- six `images/concept_XX_variant_YY.png` files
- refreshed `image_prompts.md`, `critique.md`, and `artist_questions.md`

Run tests with:

```bash
python -m pytest
```

## Seed contents

- `docs/`: design and architecture notes.
- `research/`: researched SDK/tool landscape.
- `schemas/`: JSON contracts for palette, brief, concept package, and run traces.
- `agentic_skills/`: skill-style instructions for Codex/Claude-style agents.
- `prompts/`: system prompts and Codex handoff prompt.
- `examples/`: sample text-only palette and project brief.
- `assets/reference_images/`: the mosaic image from the current conversation.
