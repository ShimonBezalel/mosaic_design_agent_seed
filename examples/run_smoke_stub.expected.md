# Stub Smoke Expected Behavior

Given:

- `examples/palette_db.example.json`
- `examples/project_brief.example.json`
- mode `stub`

The program should:

1. Load both JSON files.
2. Validate schemas.
3. Notice that exact stone dimensions are missing.
4. Continue only if configured with `--allow-assumptions`, otherwise return questions.
5. Produce 3 concept directions.
6. Use only tile IDs from the palette DB.
7. Export JSON and Markdown artifacts.
8. Make zero external API calls.

Acceptable concepts for smoke:

- desert sunrise / horizon arc;
- typography-led welcome stone;
- community path / local landscape.
