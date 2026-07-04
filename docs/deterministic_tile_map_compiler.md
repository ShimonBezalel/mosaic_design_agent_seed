# Deterministic Tile Map Compiler

## Purpose

This compiler is prepress for mosaic. It converts a finalized 2D image into broad, numbered color regions constrained to tile colors that exist in the studio palette database. An optional second layer subdivides those immutable color regions into physically scaled tessera planning geometry.

Generated maps are planning aids. They are not construction-ready without artist review.

## Inputs

- finalized RGB-compatible source image;
- optional work-area mask;
- palette database and selected tile IDs;
- granularity and cleanup controls;
- optional physical width and height plus full-image or mask-bbox scale basis;
- optional color compactness, physical minimum color area, and tessera controls.

An empty selected-ID list means every palette color at the backend API. The workbench requires an explicit selection so accidental use of unavailable stock is less likely.

## Algorithm

### 1. Normalize Source And Mask

The source becomes RGB. Images larger than 1400 pixels on their longest side resize once with Lanczos. Outputs remain at working resolution and QA records both sizes.

RGBA masks use alpha below 128 as the work area. Masks without alpha use grayscale at or above 128, so white means work and black means outside. Mask resizing uses nearest-neighbor. An absent mask means the whole image; an empty work area is rejected.

### 2. Load The Selected Studio Palette

Palette IDs must be unique and selected IDs must exist. Hex values must be six-digit RGB values. Tiles are sorted by `tile_id` for stable tie-breaking, then converted to CIE Lab with `skimage.color.rgb2lab`.

### 3. Smooth For Region Formation

Boundary smoothing applies a deterministic Gaussian blur to source color before segmentation and mean-color calculation:

- none: sigma 0;
- light: sigma 0.8;
- medium: sigma 1.5.

The binary mask is never blurred.

### 4. Segment Into Blotches

Mask-aware SLIC creates superpixels inside the work area. Segment targets scale from 120 coarse, 300 medium, or 650 fine regions at one megapixel, with practical bounds. An explicit target can override granularity. Compactness is exposed through organic (`2`), balanced (`5`), and regular (`12`) color-shape controls.

SLIC has no random input. If it cannot produce valid labels, a deterministic rectangular grid fallback runs and QA records the fallback.

### 5. Match Segments To Real Tiles

Each segment's mean Lab color is compared with every selected tile using CIEDE2000. The nearest actual tile wins. No k-means center or other invented color can enter the final map.

### 6. Apply Optional Maximum Color Count

Initial segment assignments measure pixel demand for each selected tile. When `max_colors` is smaller than the selection, the highest-demand tiles remain, ties break by `tile_id`, and all segments are reassigned using CIEDE2000 against that reduced real-tile set. QA lists dropped IDs.

### 7. Form Connected Paint Regions

Four-way connected components of the same tile become regions. Diagonal contact alone does not merge regions. IDs are reassigned stably from top to bottom and left to right using bounds, centroid, and tile identity.

### 8. Merge Tiny Regions

When enabled, regions below the minimum area merge into an adjacent region. Candidate ordering is deterministic:

1. lowest color penalty for the adjacent tile;
2. largest shared boundary;
3. largest adjacent region area;
4. smallest stable region ID.

The compiler relabels same-color components after each pass and stops at convergence or a 100-pass safety cap. An isolated tiny region remains with a warning. Cleanup cannot change masked pixel count.

### 9. Account And Render

Final records include tile ID, pixels, bounds, centroid, mean source RGB/Lab, Delta E, and neighbors. Legend counts and percentages use only masked pixels.

When both physical dimensions are present, the selected scale basis determines pixel size:

```text
mm_per_px_x = physical_width_mm / basis_width_px
mm_per_px_y = physical_height_mm / basis_height_px
pixel_area_cm2 = (mm_per_px_x * mm_per_px_y) / 100
```

For `full_image`, basis dimensions are the working raster. For `mask_bbox`, they are the inclusive work-mask bounds. A physical minimum color area converts to pixels and overrides the legacy pixel cleanup threshold.

The compiler produces exact-color flat maps, numbered/outlined region maps, source boundary overlays, contour SVG, CSV tables, QA JSON, and a static HTML report.

### 10. Optionally Subdivide Into Tesserae

Tessera subdivision consumes the authoritative in-memory mask, tile-index map, and color-region map. It never rebuilds regions from rendered PNGs.

Sobel edge tangents produce an axial flow field with confidence. Low-confidence regions fall back to their physical PCA major axis. Deterministic physically oriented lattice seeds target `short_edge_mm**2 * preferred_aspect_ratio` area. Per-region anisotropic nearest-seed assignment creates flow-oriented pieces without crossing color boundaries. Disconnected fragments are split and tiny fragments merge to adjacent pieces when possible.

The tessera layer is optional. Disabled runs retain the original artifact set and do not instantiate the tessera engine. See [physical_tessera_subdivision.md](physical_tessera_subdivision.md) for controls, workflow, safeguards, and limitations.

### 11. Sign Deterministic Output

SHA-256 covers the complete tile index map, region ID map, work mask, selected/effective palette IDs, normalized parameters, and working dimensions. Paths, timestamps, and output directories are excluded. Identical input content and parameters therefore produce the same signature in different output directories.

## QA Checks

`qa_report.json` includes:

- masked, region, and color counts;
- parameters and warnings;
- worst regions by Delta E;
- tiny regions remaining;
- colors used outside the selected palette, expected to be empty;
- legend and region area-sum checks;
- original/working dimensions and scale;
- deterministic signature.

Enabled runs also write `tessera_qa_report.json` with exact coverage, outside-mask count, parent-boundary crossing count, tile inheritance, count cap, physical settings, area/aspect distributions, warnings, and a tessera signature.

## Performance

The local prototype caps the longest working side at 1400 pixels. Typical color maps compile in seconds. Tessera runtime and export size scale with working pixels and piece count; the explicit count cap defaults to 3,000 and can be raised to 10,000 deliberately.

## Known Limitations

- This is not a construction-ready mosaic plan.
- Region boundaries require artist review.
- Tile availability quantities depend on accurate palette metadata.
- CIEDE2000 on digital color may not match glazed ceramic under installation lighting.
- Tessera geometry is a deterministic visual subdivision, not an exact fracture, cutting, or installation solution.
- Text and lettering require manual design.
- Physical area estimates require accurate dimensions.
- Contour SVG is approximate planning geometry, not fabrication CAD.

## Possible Next Improvements

- palette entries with measured Lab values from photographed/calibrated physical samples;
- artist-assisted region split, merge, and tile reassignment tools;
- inventory quantities and shortage warnings;
- better label placement for narrow or concave regions;
- distance-to-boundary seed heuristics for critical lettering and reserved fields;
- artist edits for tessera split, merge, orientation, and local scale;
- inventory-aware piece counts and cutting-loss estimates.
