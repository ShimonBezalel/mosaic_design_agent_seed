# AGENTS.md — Mosaic Design Agent Seed

## Mission

Implement a small, testable, provider-agnostic agentic loop for mosaic ideation. The first version must work in stub mode without external APIs.

## Read order

1. `README.md`
2. `docs/design_brief.md`
3. `docs/agent_loop_spec.md`
4. `docs/testing_strategy.md`
5. `prompts/codex_implementation_prompt.md`
6. `agentic_skills/*/SKILL.md`

## Engineering rules

- Prefer simple Python and Pydantic.
- Keep the runtime decoupled from image providers.
- No external API calls in tests.
- No image generation unless explicitly configured.
- Write tests before real integrations.
- Validate JSON examples.
- Export local artifacts from every demo run.
- Never invent tile IDs.

## Suggested first task

Build the schema validation and stub demo loop. Stop before adding real model/API calls.
