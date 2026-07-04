# Physical Art-Following Tessera Subdivision Design

## Product Boundary

Mosaic Compiler M2 keeps the existing deterministic color-area compiler and adds a second deterministic subdivision layer. The outputs have different jobs:

- A `ColorRegion` is a larger paint-by-tile area assigned to one studio `tile_id`.
- A `Tessera` is a smaller possible broken-tile piece inside exactly one parent color region.

The tessera layer is optional. Disabling it produces the current M1 bundle unchanged. Enabling it requires physical dimensions and adds physically scaled shard previews and records. Neither layer is a construction-ready cutting plan.

## Considered Approaches

1. **Flow-oriented anisotropic nearest-seed assignment (selected).** Generate deterministic seeds per color region, shortlist nearby seeds with a KD-tree, then assign pixels using an ellipse-like distance aligned to local image flow. This produces compact or elongated pieces, preserves hard color-region boundaries, is deterministic, and needs no geometry dependency.
2. **Clipped oriented rectangles.** This gives explicit lengths but overlap/gap resolution recreates a raster assignment problem and creates unnatural clipping near complex boundaries.
3. **Geodesic watershed or contour tracing.** This follows edges well but makes physical size and aspect controls indirect and can fragment textured artwork.

M2 uses approach 1. SLIC remains responsible only for color areas.

## Architecture

New focused modules:

- `mosaic_agent/physical_scale.py`: derive pixel/mm transforms for full-image or mask-bbox dimensions and convert length/area controls.
- `mosaic_agent/flow_field.py`: gradient tangent field, confidence, dominant orientation, and PCA fallback.
- `mosaic_agent/tessera.py`: deterministic seeds, anisotropic assignment, connected-fragment cleanup, metrics, QA, and signatures.
- `mosaic_agent/tessera_export.py`: tessera PNG, SVG, CSV, and QA JSON rendering.

Existing modules retain their current ownership:

- `region_map.py` keeps SLIC color-area segmentation and gains a compactness parameter.
- `palette_compiler.py` orchestrates color compilation first, then optionally invokes the tessera engine using in-memory source, mask, tile-index, and region-ID arrays.
- `tile_map_export.py` writes existing color-area artifacts and conditionally extends the HTML report with tessera previews and links.
- Gradio and workbench controllers collect controls and display typed results; they contain no tessera geometry logic.

The compiler does not recover region IDs from rendered images. The in-memory arrays are authoritative during a run.

## Models

`PhysicalScale` records working image dimensions, supplied dimensions in millimeters, axis-specific mm/px and px/mm, and basis (`full_image` or `mask_bbox`). For mask-bbox scale, supplied dimensions map to the inclusive work-mask bounding box dimensions in working pixels.

`RegionRecord` remains import-compatible but becomes an alias for the clearer `ColorRegion` model.

`TesseraCompileOptions` is the nested optional configuration on `PaletteCompileRequest`. It contains:

- physical scale basis;
- minimum and target short edge;
- maximum long edge;
- preferred and maximum aspect ratios;
- flow strength and edge following;
- shape style;
- deterministic seed;
- grout preview width;
- maximum tessera count.

`TesseraCompileRequest` is the standalone typed contract with source, palette, optional map paths, physical dimensions, and the same controls. Integrated compilation creates it from the palette request and options, while passing authoritative arrays separately.

`TesseraRecord` and `TesseraCompileResult` contain the fields in the M2 objective. Polygon coordinates are contour points in working-image pixels. Result paths are optional only when tessera subdivision is disabled; an enabled successful result has every path populated.

`PaletteCompileResult` gains `tessera_result: TesseraCompileResult | None`. Existing serialized sessions remain valid because the field defaults to `None`.

## Physical Scale

Physical dimensions continue to enter the workbench in centimeters and are converted to millimeters exactly once.

For full-image basis:

```text
mm_per_px_x = physical_width_mm / working_image_width_px
mm_per_px_y = physical_height_mm / working_image_height_px
```

For mask-bbox basis, the denominators are work-mask bbox width and height. Coordinates remain in full working-image space; only the scale denominators change.

Length conversions remain axis-aware. Area conversion uses `mm_per_px_x * mm_per_px_y`. Minimum color area in cm2 converts through `100 mm2 per cm2` and overrides the legacy pixel minimum. If neither physical minimum nor physical dimensions are supplied, the existing pixel default remains for backward compatibility.

Tessera compilation fails with a friendly message unless both physical dimensions are positive.

## Color-Area Improvements

`PaletteCompileRequest.color_compactness` defaults to `5.0`. Gradio exposes:

- organic: 2.0;
- balanced: 5.0;
- regular: 12.0.

The value passes directly to SLIC. Deterministic grid fallback remains unchanged. Compactness affects only color-area segmentation, never tessera subdivision.

The SLIC segment target cap is retained for color areas because tessera scale no longer depends on color-region count. Fine physical pieces come from the second layer rather than forcing paint regions to become tiny.

## Flow Field

The source becomes grayscale. Sobel gradients produce edge normals; adding 90 degrees yields edge-tangent shard direction. Because orientation is axial (0 and 180 degrees are equivalent), smoothing averages doubled-angle vectors weighted by gradient magnitude:

```text
vx = gaussian(magnitude * cos(2 * tangent))
vy = gaussian(magnitude * sin(2 * tangent))
orientation = 0.5 * atan2(vy, vx)
confidence = hypot(vx, vy) / gaussian(magnitude)
```

Low-gradient pixels have low confidence. A region's fallback orientation is the major axis from PCA over its physical pixel coordinates. A one-pixel or isotropic region falls back to zero degrees deterministically.

Flow strength maps to 0.0, 0.35, 0.65, or 1.0 and blends local tangent orientation with region PCA in doubled-angle space. Edge-following maps to low/medium/high confidence sensitivity and also modestly increases seed density near strong edges.

## Deterministic Seed Generation

Target tessera area is:

```text
target_short_edge_mm ** 2 * preferred_aspect_ratio
```

Desired count per color region is region area in mm2 divided by target area, rounded and clamped to at least one. Regions smaller than one target area stay as one tessera. The global requested count cannot exceed `max_tessera_count` (default 3000); requests above the cap fail with an actionable message rather than silently changing physical scale.

Seeds come from a physical-coordinate lattice. Each cell receives deterministic hash jitter bounded to 25 percent of spacing. Candidates outside the parent region are rejected. If a narrow region has fewer candidates than desired, deterministic major-axis support points and farthest valid pixels are added. Candidate order and jitter hash include region ID, lattice coordinate, and user seed.

Identical arrays, controls, and seed therefore yield identical seed points.

## Tessera Assignment

Each seed gets:

- a local blended flow orientation;
- a deterministic aspect ratio variation around the preferred ratio;
- a style adjustment;
- short and long radii capped by minimum short edge, maximum long edge, and maximum aspect ratio.

Style behavior:

- irregular: moderate deterministic size/aspect variation;
- angular: orientation quantized to 15-degree increments;
- smooth: reduced variation;
- slivered: higher aspect ratios up to the configured cap.

For each color region, a `scipy.spatial.cKDTree` returns the nearest 12 seeds in physical XY space for each pixel. Only those candidates are evaluated with the seed's anisotropic metric:

```text
d2 = (parallel_mm / long_radius_mm) ** 2 + (perpendicular_mm / short_radius_mm) ** 2
```

Stable seed order breaks exact ties. Assignment runs independently inside each parent color region, so crossing a color boundary is impossible by construction.

Each seed assignment is split into four-way connected components. Small disconnected fragments below a conservative physical area threshold merge into the adjacent tessera with the largest shared boundary. Unmergeable fragments remain with warnings. Final tessera IDs are stable in parent-region and top-left order.

## Tessera Metrics

Area uses physical pixel area. Centroid is the pixel mean. Orientation and edge estimates come from PCA in millimeter coordinates:

```text
estimated_edge = sqrt(12 * covariance_eigenvalue)
```

The larger estimate is the long edge. Aspect ratio is long/short. Records warn when estimated short edge is below the requested minimum, long edge exceeds the maximum, aspect exceeds the cap, or a piece is too small for stable geometry.

These are raster/PCA estimates, not fabrication dimensions.

## Rendering And Export

Enabled tessera runs add:

- `tessera_map.png`: exact palette fills with grout-like dark boundaries;
- `tessera_boundaries.png`: source image with tessera boundaries;
- `tessera.svg`: contour polygons grouped by tessera and parent color region;
- `tessera.csv`: required metrics and warning column;
- `tessera_qa_report.json`: counts, invariants, distributions, warnings, settings, and signature.

Preview grout width converts from millimeters to pixels using the geometric mean scale. It changes only rendering, never assignment or metrics.

The compile HTML report conditionally shows both tessera previews and links all tessera files. ZIP and full-session export already copy every file in the compile directory, so enabled tessera files are included automatically.

## QA And Determinism

Tessera QA proves:

- tessera pixels equal work-mask pixels;
- no tessera pixel exists outside the mask;
- every tessera has one parent region;
- no tessera crosses a parent boundary;
- every tessera inherits its parent tile ID;
- requested count respects the configured cap.

The SHA-256 signature includes the final tessera ID map, parent-region map, tile IDs, physical scale, all tessera controls, and seed. Paths and timestamps are excluded.

## Workbench

The compile tab becomes two unframed sections:

### Color-Area Compilation

Existing source, mask, palette, color count, granularity, smoothing, and cleanup controls remain. Pixel minimum becomes an internal fallback. Visible controls add optional minimum color area in cm2 and color shape regularity.

### Tessera / Shard Subdivision

Visible controls are enable, physical scale basis, minimum/target edge, maximum long edge, preferred/maximum aspect, flow strength, edge following, shape style, preview grout width, seed, and maximum tessera count. Defaults match the M2 objective.

New outputs are tessera map, source boundary overlay, and QA summary. Existing color map, numbered color regions, boundaries, legend, report, and bundle remain.

UI copy says: "Color regions are the paint-by-tile areas. Tessera subdivision is a deterministic preview of possible broken-tile piece flow inside those areas. Artist review is required."

## Errors And Safeguards

Friendly errors cover missing dimensions, empty masks, invalid physical controls, impossible edge ordering, requested piece counts above the cap, and missing palette/region data. A target short edge must be at least the minimum short edge; maximum long edge must be at least the target short edge; preferred aspect cannot exceed max aspect.

The compiler retains the 1400-pixel working-size cap. Tessera processing uses KD-tree shortlists and region-local arrays. The default cap is 3000 pieces.

## Testing

Tests use small synthetic arrays and no network calls. Dedicated suites cover:

- full-image and mask-bbox physical scale;
- physical area conversion and missing-dimension errors;
- SLIC compactness propagation and deterministic output;
- vertical, horizontal, diagonal, flat, and PCA flow behavior;
- repeatable seeds, physical density, containment, and narrow regions;
- exact tessera coverage, no outside pixels, no color-boundary crossing, inherited tile IDs, anisotropic aspect, flow alignment, fragment handling, and signatures;
- all tessera export formats and conditional report links;
- workbench enabled/disabled paths and compile bundles;
- all existing M1 tests.

## Known Limitations

- Tessera polygons are raster-derived planning shapes, not cut lines.
- Minimum/maximum edges are PCA estimates and warnings, not hard geometric guarantees.
- Local flow is image-gradient driven and can follow texture noise despite smoothing.
- Grout is a preview overlay and does not subtract physical area.
- Lettering still needs protected/vector geometry for reliable final typography.
- Physical ceramic variation, thickness, break behavior, and inventory quantities are not modeled.
