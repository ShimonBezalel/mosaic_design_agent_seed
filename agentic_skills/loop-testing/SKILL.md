---
name: loop-testing
description: Use when building or modifying the mosaic design agent loop; requires stub tests before real API calls.
---

# Loop Testing

## Purpose

Make the design-agent loop testable, inspectable, and safe before real image/model calls.

## Non-negotiables

- Stub mode must work with no API keys.
- Tests must validate schemas.
- Tests must verify that selected tile IDs exist in the palette DB.
- Tests must verify that missing critical fields produce questions.
- Real image generation must be behind an explicit provider flag.
- Every run must export artifacts and a local trace file.

## Development order

1. Define models.
2. Validate examples.
3. Implement stub tools.
4. Implement loop orchestration.
5. Write smoke tests.
6. Only then add real model/image providers.

## Smoke-test command shape

```bash
python -m mosaic_agent.demo --mode stub --palette examples/palette_db.example.json --brief examples/project_brief.example.json --out runs/smoke
```

## Test assertions

- output JSON parses;
- concept count is configurable;
- no external network call in stub mode;
- no hallucinated tile IDs;
- questions are exported separately;
- failures are structured.
