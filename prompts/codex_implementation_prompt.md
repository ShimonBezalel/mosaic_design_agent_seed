# Codex Implementation Prompt

You are implementing the first prototype of `mosaic_design_agent_seed`.

Do not build the full mosaic compiler. Do not overbuild UI. Your job is to make the agentic loop real, testable, and safe.

## Read first

- `README.md`
- `docs/design_brief.md`
- `docs/architecture.md`
- `docs/agent_loop_spec.md`
- `docs/testing_strategy.md`
- `schemas/*.json`
- `agentic_skills/*/SKILL.md`

## Goal

Create a Python package that supports:

```bash
python -m mosaic_agent.demo \
  --palette examples/palette_db.example.json \
  --brief examples/project_brief.example.json \
  --mode stub \
  --allow-assumptions \
  --out runs/demo_001
```

## Required outputs

- `concept_package.json`
- `artist_questions.md`
- `image_prompts.md`
- `critique.md`
- `run_trace.json`

## Implementation constraints

- Test-first.
- Stub mode first.
- No external API calls in stub mode.
- Use Pydantic models or equivalent typed validation.
- Validate schema examples.
- All selected tile IDs must come from the palette DB.
- Missing critical fields should produce questions unless `--allow-assumptions` is set.
- Keep image generation behind provider interfaces.
- Do not commit generated run artifacts unless explicitly asked.

## Suggested package layout

```text
mosaic_agent/
  __init__.py
  models.py
  load.py
  palette.py
  intake.py
  ideation_stub.py
  critique.py
  export.py
  demo.py
  providers/
    __init__.py
    base.py
    stub.py
    openai_image.py
    gemini_nano_banana.py

tests/
  test_schemas.py
  test_palette_grounding.py
  test_missing_questions.py
  test_stub_loop.py
```

## Stub concept behavior

For the sample brief, generate three deterministic concepts:

1. Desert Sunrise Welcome
2. Path Into Community
3. Typography Stone Ribbon

Each concept must use 8–14 palette tile IDs, include prompts, and include a critique.

## Done definition

- `pytest` passes.
- Stub demo command runs.
- Output artifacts are created.
- No API keys are required.
- README has a short usage section.
