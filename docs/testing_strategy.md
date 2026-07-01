# Testing Strategy

## Principle

The first build should be testable without model calls and without image API credentials.

## Test layers

### 1. Schema tests
Validate example files against schemas.

### 2. Palette grounding tests
Input: brief asks for blue/orange/green desert palette.
Expected: selected tiles come only from palette DB.

### 3. Missing-question tests
Input: no required text and no canvas dimensions.
Expected: agent asks questions before generating final concepts.

### 4. Stub loop smoke test
Input: complete example brief and palette.
Expected files:

- `concept_package.json`
- `artist_questions.md`
- `image_prompts.md`
- `critique.md`

Expected properties:

- exactly 3 concepts by default;
- each concept has a palette subset;
- no palette IDs outside the DB;
- at least one critique note per concept;
- no real API calls.

### 5. Real loop smoke test
Run with real model but stub image provider.
Expected:

- model produces valid structured output;
- all tool calls are traced/logged;
- output remains JSON-parseable.

### 6. Real image integration test
Run one concept through one image provider after explicit env/API setup.
Expected:

- image result metadata saved;
- prompt saved;
- failures become structured errors, not crashes.

## Suggested pytest names

```text
tests/test_schemas.py
tests/test_palette_grounding.py
tests/test_missing_questions.py
tests/test_stub_loop.py
tests/test_export_artifacts.py
```

## Goldens

Keep one golden output for the sample brief. Use it for smoke only; don't overfit exact prose.

Check structural invariants, not exact wording.
