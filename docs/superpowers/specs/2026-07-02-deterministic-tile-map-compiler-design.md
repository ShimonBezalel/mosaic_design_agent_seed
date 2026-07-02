# Deterministic Tile Map Compiler Design

## Product Direction

The workbench has three stages:

1. Optional AI ideation and masked editing.
2. Deterministic compilation of a finalized image into a studio-palette tile map.
3. Optional mosaic preview, deferred beyond this milestone.

Stage 2 is the core product. It accepts an image from any source and produces a paint-by-color planning bundle without calling a generative model or inventing final colors. Existing ideation and image-editing behavior remains available but is not required before compilation.

Every report and workbench result states:

> Generated maps are planning aids. They are not construction-ready without artist review.

## Architecture

The deterministic backend is isolated from Gradio:

- `mosaic_agent/tile_map_models.py` owns typed requests, region records, color usage, and results.
- `mosaic_agent/region_map.py` owns mask decoding, color conversion, segmentation, palette assignment, connected components, adjacency, and tiny-region cleanup.
- `mosaic_agent/palette_compiler.py` validates a request, orchestrates the array pipeline, computes accounting and the deterministic signature, and returns a result.
- `mosaic_agent/tile_map_export.py` renders PNG, SVG, CSV, JSON, and HTML artifacts from compiled arrays and records.
- `mosaic_workbench/controllers.py` resolves a source choice, creates a request, invokes the compiler, and appends the result to the interactive session.
- `mosaic_workbench/app.py` adds the compile tab and presents controller outputs. It contains no compilation logic.

The compiler depends on Pillow, NumPy, and scikit-image. CSV output uses the standard library rather than pandas.

## Data Contracts

`PaletteCompileRequest` contains the fields named in the product objective. It rejects missing files, duplicate selected IDs, non-positive dimensions and region areas, invalid limits, and `strict_palette=False`. An empty selected palette means all palette tiles, but the workbench requires at least one selected tile so user intent remains explicit.

`ColorUsage`, `RegionRecord`, and `PaletteCompileResult` use Pydantic and the existing strict-model convention. Paths in a compile result point at complete artifacts. Compile results serialize directly into `InteractiveSession`.

`InteractiveSession` adds:

- `accepted_source_image_path: str | None`
- `compile_runs: list[PaletteCompileResult]`
- `latest_compile_result: PaletteCompileResult | None`

Repeated compilations append immutable result records. The latest result is also stored directly for convenient UI rendering.

## Input Normalization

The source is converted to RGB. If its longest side exceeds 1400 pixels, it is resized once with Lanczos while preserving aspect ratio. Generated maps remain at this working resolution; they are not enlarged back to the source dimensions. The QA report records original dimensions, working dimensions, and scale factor.

Mask semantics match the existing edit workflow:

- alpha mask: alpha below 128 is work area;
- mask without meaningful alpha: grayscale at or above 128 is work area;
- absent mask: the whole image is work area.

The mask is resized to working dimensions using nearest-neighbor. A mask with no work pixels is an error. When no mask is supplied, the compiler synthesizes a normalized RGBA mask whose alpha is zero everywhere. Every run therefore has a portable `mask.png`. Outside-mask pixels are excluded from all segmentation statistics and accounting.

## Palette Discipline and Color Matching

Palette loading reuses `PaletteDB`. Selected IDs are validated against the database and retain stable `tile_id` ordering. Tile hex strings must be six-digit RGB values, with an optional leading `#`.

Tile colors and source pixels are converted to CIE Lab with `skimage.color.rgb2lab`. Assignment uses `deltaE_ciede2000`. Final tile IDs always come from the selected palette.

When `max_colors` is smaller than the selected palette:

1. Initial segments are assigned against all selected colors.
2. Demand is the sum of segment pixel counts assigned to each tile.
3. The highest-demand tiles are retained, with `tile_id` ascending as the stable tie-breaker.
4. Every segment is reassigned against the retained set.
5. QA reports which selected colors were dropped.

No cluster center becomes a final color.

## Segmentation

Boundary smoothing is deterministic source preprocessing before segmentation and mean-color calculation:

- `none`: no blur;
- `light`: Gaussian sigma 0.8;
- `medium`: Gaussian sigma 1.5.

The binary mask itself is never blurred.

SLIC runs with `start_label=1`, `convert2lab=False`, the normalized Lab image, and the work mask. Segment targets are derived from granularity at one megapixel and scaled by the square root of image area:

- coarse: 120;
- medium: 300;
- fine: 650.

Targets are clamped to 20 through 1200 and cannot exceed the number of work pixels. `target_region_count` overrides the derived target within the same bounds. SLIC uses fixed parameters and no random state.

If SLIC raises an error or produces no valid labels, a deterministic rectangular grid fallback assigns mask pixels to cells sized from the target count. QA records fallback use.

Each initial segment receives the nearest selected tile by mean source Lab. Stable palette order breaks exact distance ties.

## Region Cleanup

After tile assignment, connected components of equal tile ID inside the mask become paint regions. Connectivity is four-way so diagonal touches do not imply physical adjacency.

Regions are ordered by `(bbox_y1, bbox_x1, centroid_y, centroid_x, tile_id)` and receive consecutive one-based IDs. This ordering is recomputed after cleanup.

When tiny merging is enabled, regions below `min_region_area_px` are processed from smallest area, then stable region ID. Candidate neighbors share a four-way boundary. A tiny region is reassigned to the neighbor selected by:

1. lowest CIEDE2000 penalty between the tiny region's source mean and the neighbor tile;
2. largest shared boundary;
3. largest neighbor area;
4. smallest stable neighbor ID.

After each pass, adjacent equal-color components are relabeled. Processing repeats until every mergeable region meets the threshold or 100 passes have completed. Isolated tiny regions remain and produce warnings. Masked pixel count cannot change.

## Accounting and Deterministic Signature

Color usage is aggregated from final regions. Pixel counts and percentages use only work-area pixels. Region delta E is calculated from each region's source mean Lab to its assigned tile Lab; color mean delta E is pixel-weighted and max delta E is the worst region.

Physical area is available only when both width and height are supplied. Pixel area is `(width_cm * height_cm) / (working_width * working_height)`, so masked and region area estimates correctly account for mask coverage.

The deterministic SHA-256 signature includes:

- tile index map inside the mask;
- final region ID map inside the mask;
- ordered selected and effective palette IDs;
- normalized compilation parameters;
- working dimensions.

Paths, timestamps, output directory, and run ID are excluded. Identical inputs and parameters therefore produce identical signatures across output directories.

## Artifacts

Each compilation directory contains:

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

The palette map uses exact tile RGB values inside the work mask and a dimmed source outside it. Labels use outlined numeric text at region centroids. Boundary previews overlay final region boundaries on the source. SVG paths come from `skimage.measure.find_contours`; disconnected contours remain grouped under the same region metadata.

The HTML report uses relative artifact paths and includes source, mask preview, all map previews, legend, parameters, warnings, and the disclaimer. QA includes area-sum checks, worst color matches, remaining tiny regions, selected-palette violations (which must be empty), resize information, and signature.

Compile bundle export archives exactly these artifacts. Full session export copies every compile run under `compile_runs/run_XX/` and records them in its manifest. Full export no longer requires a selected concept when the session contains a valid compile result, allowing the deterministic path to stand alone.

## Workbench Flow

Tab `5. Compile to Tile Map` supports source choices:

- uploaded finalized image;
- latest generated variant;
- base canvas.

The controller reports a friendly error when the chosen source is unavailable. Compile-specific mask upload overrides the normalized session mask. Whole-image mode ignores both. Selected palette IDs come from the first tab and are shown as swatches.

Controls are granularity, optional max colors, minimum region area, boundary smoothing, tiny-region merging, locked strict-palette mode, and optional physical dimensions. Compile outputs show the three raster previews, a legend table, QA warnings, the report, and a downloadable archive.

Concept summaries become scan-oriented: name, one-line thesis, palette IDs, and selector remain visible; composition and risks move into an HTML details disclosure.

## Errors and Limits

Backend errors are typed as `ValueError` with actionable messages. Gradio converts them to `gr.Error` without a traceback. Important cases include missing source, missing palette selection, invalid palette hex, empty work mask, unavailable latest variant, and unsupported non-strict compilation.

If final region count exceeds 600, QA warns that labels may be difficult to use and recommends coarser granularity or a larger minimum region area. Very large input resizing also produces a warning.

## Testing Strategy

Synthetic fixtures directly test color matching, palette restrictions, alpha and black/white masks, nearest-neighbor mask resizing, whole-image mode, segmentation, repeated signatures, granularity, tiny-region cleanup, connected regions, area accounting, artifact contents, source resolution, workbench source choices, archives, and existing behavior.

At least 35 deterministic compiler/export/workbench tests are added, including fixed-seed randomized invariant tests. Tests make no network calls and do not require API keys. Every production behavior is introduced through a failing test before implementation.

A checked-in `examples/tile_compile_demo/` fixture contains broad regions, a mergeable island, an excluded mask area, a palette database, and expected notes.

## Known Limitations

- The output is not a construction-ready mosaic plan.
- Region boundaries require artist review.
- Palette inventory quantities are only as accurate as palette metadata.
- Perceptual nearest color may not match ceramic appearance under real lighting.
- Broken-tile shape layout is not solved.
- Text and lettering must be designed manually.
- Physical estimates require accurate dimensions.
- Contour SVG is useful for planning but is not CAD-grade.

## Deferred Work

This milestone does not add tile tessellation, mosaic shard simulation, AR, cloud services, authentication, or generative decisions to the compile stage. A later optional preview may consume the deterministic map but must never modify it.
