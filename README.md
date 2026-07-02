# Mosaic Studio Workbench

The workbench now supports optional AI ideation, but the core path is finalized image -> deterministic studio-palette tile map -> exportable paint-by-color bundle.

The product has three stages:

1. **Optional ideation and masked editing** for producing a visually accepted source image.
2. **Deterministic palette compilation** for converting that image into broad regions using only real studio tile IDs.
3. **Optional mosaic preview**, deferred until it can consume the deterministic map without changing it.

The compile stage works offline, needs no API key, and never asks a generative model to choose final colors.

## Launch

```bash
python -m pip install -e .
python -m mosaic_workbench.app --demo
```

Open `http://127.0.0.1:7860`. Start without demo inputs using:

```bash
python -m mosaic_workbench.app
```

## Compile To Tile Map

Open **5. Compile to Tile Map** and:

1. Load a palette DB and select the tile colors actually available in the studio.
2. Choose an uploaded finalized image, the latest generated variant, or the base canvas.
3. Use the session mask, upload a compile-specific mask, or enable whole-image mode.
4. Set granularity, maximum colors, minimum region area, and boundary smoothing.
5. Optionally enter accurate physical width and height for area estimates.
6. Click **Compile to Tile Map**.
7. Review the flat palette map, numbered regions, boundary overlay, legend, and QA warnings.
8. Export the compile bundle or the complete session.

Ideation is not required. A finalized image can be uploaded and compiled directly without generating concepts.

### Palette Discipline

The compiler converts source colors to CIE Lab and uses CIEDE2000 perceptual distance. Every final color is an actual selected `tile_id` from the palette DB. `max_colors` may remove low-demand selected colors, but it never creates a cluster-center color.

Inside the work area, `palette_map.png` contains only exact palette hex colors. The QA report checks for palette violations and records a deterministic signature.

### Mask Convention

- RGBA masks: alpha below 128 is the work area; opaque pixels are outside.
- Masks without alpha: white is the work area; black is outside.
- Masks resize with nearest-neighbor so hard boundaries remain hard.
- No mask or whole-image mode compiles every source pixel.
- Browser-drawn masks from the ideation stage are normalized to the same RGBA convention.

### Controls

- **Granularity:** coarse, medium, or fine SLIC segment target.
- **Max colors:** optional deterministic reduction within selected tiles.
- **Minimum region area:** merge smaller connected regions into an adjacent region.
- **Boundary smoothing:** none, light, or medium source smoothing before segmentation.
- **Merge tiny regions:** enable deterministic region cleanup.
- **Strict palette:** locked on in this version.
- **Physical dimensions:** optional width and height for square-centimeter estimates.

Images with a side longer than 1400 pixels compile at a proportional working resolution. Reports record original and working dimensions; outputs are not enlarged back to imply precision that was not calculated.

## Compile Artifacts

Every compile bundle contains:

- `source_image.png`
- `mask.png`
- `palette_map.png`
- `region_labels.png`
- `region_boundaries.png`
- `regions.svg`
- `legend.csv`
- `regions.csv`
- `qa_report.json`
- `compile_report.html`
- `compile_request.json`

Full session export also includes available brief, concept, reference, edit, and generated-variant artifacts plus every compile run.

Generated maps are planning aids. They are not construction-ready without artist review.

## Compile Demo

The checked-in fixture at `examples/tile_compile_demo/` contains four broad regions, one tiny color island, and a mask excluding the right strip.

Launch the workbench, choose **Upload finalized source image**, then use:

- source: `examples/tile_compile_demo/source_image.png`
- mask: `examples/tile_compile_demo/mask.png`
- palette: `examples/tile_compile_demo/palette_db.json`
- granularity: `coarse`
- max colors: `4`
- minimum region area: `120`
- smoothing: `light`

The expected behavior is documented in `examples/tile_compile_demo/expected_notes.md`.

## Optional Ideation

The earlier concept and masked-edit workflow remains available:

- brief and palette entry without editing JSON;
- base canvas, site context, style reference, and sketch uploads;
- uploaded or browser-drawn masks;
- deterministic stub or OpenAI concept directions;
- stub or OpenAI masked variants;
- reference-aware visual contact-sheet CLI.

Stub modes require no API key. Real concept ideation and masked edits use `OPENAI_API_KEY`. Choose `openai` under **Ideation mode** and `openai-edit` under **Image edit mode**.

The offline visual CLI remains:

```bash
python -m mosaic_agent.demo \
  --palette examples/palette_db.example.json \
  --brief examples/project_brief.example.json \
  --ideation-mode stub \
  --image-mode stub \
  --allow-assumptions \
  --out runs/visual_001_stub
```

Generated images are visual ideation only. Hebrew lettering is deliberately reserved as a blank field for manual drawing or vectorization.

## Tests

```bash
python -m pytest
```

Compiler, export, and workbench tests use synthetic images and make no network calls. Paid-provider canaries remain opt-in through their existing environment flags.

## Algorithm

See [docs/deterministic_tile_map_compiler.md](docs/deterministic_tile_map_compiler.md) for segmentation, color matching, cleanup, accounting, signatures, and known limitations.

## Known Limitations

- This is not a construction-ready mosaic plan.
- Region boundaries require artist review.
- Tile availability quantities are only as good as palette DB metadata.
- Perceptual nearest color may not match physical ceramic appearance under real light.
- Broken-tile shape layout is not solved yet.
- Text and lettering should be designed manually.
- Physical area estimates require accurate dimensions.
- SVG contours are planning geometry, not CAD-grade fabrication paths.

## Repository Layout

- `mosaic_agent/`: deterministic compiler and optional ideation providers.
- `mosaic_workbench/`: local Gradio workbench and session export.
- `tests/`: offline deterministic and opt-in provider tests.
- `examples/`: palette, brief, workbench, reference-image, and compile fixtures.
- `docs/`: architecture, contracts, compiler design, and implementation notes.
- `schemas/`: JSON contracts for the original agent loop.

Generated files belong under `runs/` and are intentionally not committed.
