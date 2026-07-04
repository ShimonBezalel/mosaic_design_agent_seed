# Mosaic Studio Workbench

The core path is finalized image -> deterministic studio-palette color regions -> optional physically scaled tessera subdivision -> exportable planning bundle.

The product has three stages:

1. **Optional ideation and masked editing** for producing a visually accepted source image.
2. **Deterministic palette compilation** for converting that image into broad regions using only real studio tile IDs.
3. **Optional tessera subdivision** for smaller flow-oriented shard planning inside the immutable color regions.

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
4. Set color granularity, shape regularity, maximum colors, optional minimum color area, and boundary smoothing.
5. Enter accurate physical dimensions and select whether they describe the full image or masked field.
6. Optionally enable tessera subdivision and set physical edge, aspect, flow, style, seed, grout-preview, and count-cap controls.
7. Click **Compile to Tile Map**.
8. Review color regions first, then tessera previews and both QA summaries.
9. Export the compile bundle or the complete session.

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
- **Minimum color area:** optional physical cleanup threshold in square centimeters.
- **Color shape regularity:** organic, balanced, or regular SLIC compactness.
- **Boundary smoothing:** none, light, or medium source smoothing before segmentation.
- **Merge tiny regions:** enable deterministic region cleanup.
- **Strict palette:** locked on in this version.
- **Physical dimensions:** width, height, and full-image or mask-bbox basis.
- **Tessera dimensions:** minimum/target short edge and maximum long edge in millimeters.
- **Tessera form:** preferred/maximum aspect, flow strength, edge following, and shape style.
- **Tessera reproducibility:** explicit seed, grout preview width, and maximum count.

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

When tessera subdivision is enabled, the same bundle also contains:

- `tessera_map.png`
- `tessera_boundaries.png`
- `tessera.svg`
- `tessera.csv`
- `tessera_qa_report.json`

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

For a physical tessera example on a 200 x 200 cm field, start with 8 / 18 / 55 mm edges, aspect 1.8 / 4.0, medium flow, irregular style, and a 7,500 count cap. This requests about 6,860 pieces and requires at least that many work pixels. Keep the default 3,000 cap by raising the target short edge to about 28 mm.

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

See [docs/deterministic_tile_map_compiler.md](docs/deterministic_tile_map_compiler.md) for color compilation and [docs/physical_tessera_subdivision.md](docs/physical_tessera_subdivision.md) for physical scale, flow, subdivision, safeguards, and Yael's review workflow.

## Known Limitations

- This is not a construction-ready mosaic plan.
- Region boundaries require artist review.
- Tile availability quantities are only as good as palette DB metadata.
- Perceptual nearest color may not match physical ceramic appearance under real light.
- Tessera geometry is a planning subdivision, not a fracture, cutting, or installation plan.
- Text and lettering should be designed manually.
- Physical area estimates require accurate dimensions.
- SVG contours are planning geometry, not CAD-grade fabrication paths.
- Small physical targets require sufficient source resolution and can produce large exports.

## Repository Layout

- `mosaic_agent/`: deterministic compiler and optional ideation providers.
- `mosaic_workbench/`: local Gradio workbench and session export.
- `tests/`: offline deterministic and opt-in provider tests.
- `examples/`: palette, brief, workbench, reference-image, and compile fixtures.
- `docs/`: architecture, contracts, compiler design, and implementation notes.
- `schemas/`: JSON contracts for the original agent loop.

Generated files belong under `runs/` and are intentionally not committed.
