# Mosaic Design Agent Seed

This repo seed is for building a first-night prototype of a human-in-the-loop mosaic ideation agent for Yael's broken-tile public-art workflow.

The goal is not to implement the mosaic compiler yet. The first build should prove an agentic design loop:

1. collect a project brief from the artist/user;
2. ground itself in a text-only tile palette DB;
3. ask missing questions instead of hallucinating;
4. call visual ideation tools through swappable adapters;
5. return structured ideation packages: composition briefs, image-generation prompts, palette constraints, critique notes, and next questions;
6. run the same loop in stub mode for fast smoke testing and real mode for tomorrow's Yael experiment.

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
Add OpenAI Agents SDK orchestration with function tools for palette lookup, question generation, concept planning, critique, and artifact export.

### Phase 3 — Image provider adapter
Add provider abstraction:

- `StubImageProvider`
- `OpenAIImageProvider`
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
  --mode stub \
  --allow-assumptions \
  --out runs/demo_001
```

Expected outputs:

- `runs/demo_001/concept_package.json`
- `runs/demo_001/artist_questions.md`
- `runs/demo_001/image_prompts.md`
- `runs/demo_001/critique.md`

Stub mode makes no external API calls. If critical brief fields are missing and `--allow-assumptions` is not passed, the command writes `artist_questions.md` and stops before generating concepts. `run_trace.json` is not written by default in stub mode; platform traces or a later explicit trace mode can cover automated runs.

## Visual contact sheet

Generate the full visual artifact set with deterministic placeholder images:

```bash
python -m mosaic_agent.demo \
  --palette examples/palette_db.example.json \
  --brief examples/project_brief.example.json \
  --mode stub \
  --allow-assumptions \
  --out runs/visual_001_stub
```

Generate real OpenAI image variants when `OPENAI_API_KEY` is available:

```bash
python -m mosaic_agent.demo \
  --palette examples/palette_db.example.json \
  --brief examples/project_brief.example.json \
  --mode openai-image \
  --allow-assumptions \
  --out runs/visual_001
```

`--mode gemini-image` uses `GEMINI_API_KEY` or `GOOGLE_API_KEY`. Missing keys fail with a clear provider configuration message. Provider-side failures, such as billing limits, are reported without a Python stack trace.

Visual runs write:

- `contact_sheet.html`
- `visual_manifest.json`
- six `images/concept_XX_variant_YY.png` files
- refreshed `image_prompts.md`, `critique.md`, and `artist_questions.md`

Run tests with:

```bash
pytest
```

## Seed contents

- `docs/`: design and architecture notes.
- `research/`: researched SDK/tool landscape.
- `schemas/`: JSON contracts for palette, brief, concept package, and run traces.
- `agentic_skills/`: skill-style instructions for Codex/Claude-style agents.
- `prompts/`: system prompts and Codex handoff prompt.
- `examples/`: sample text-only palette and project brief.
- `assets/reference_images/`: the mosaic image from the current conversation.
