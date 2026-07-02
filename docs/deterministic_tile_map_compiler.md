# Deterministic Tile Map Compiler

## Purpose

This compiler is prepress for mosaic. It converts a finalized 2D image into broad, numbered color regions constrained to tile colors that exist in the studio palette database. It does not generate art, invent final colors, or arrange individual broken shards.

Generated maps are planning aids. They are not construction-ready without artist review.

## Inputs

- finalized RGB-compatible source image;
- optional work-area mask;
- palette database and selected tile IDs;
- granularity and cleanup controls;
- optional physical width and height.

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

Mask-aware SLIC creates superpixels inside the work area. Segment targets scale from 120 coarse, 300 medium, or 650 fine regions at one megapixel, with practical bounds. An explicit target can override granularity.

SLIC has fixed parameters and no random input. If it cannot produce valid labels, a deterministic rectangular grid fallback runs and QA records the fallback.

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

When both physical dimensions are present, each working pixel represents:

```text
(physical width cm * physical height cm) / (working width px * working height px)
```

The compiler produces exact-color flat maps, numbered/outlined region maps, source boundary overlays, contour SVG, CSV tables, QA JSON, and a static HTML report.

### 10. Sign Deterministic Output

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

## Performance

The local prototype caps the longest working side at 1400 pixels. Typical images compile in seconds. Coarser granularity and larger minimum regions reduce both runtime and artist review load.

## Known Limitations

- This is not a construction-ready mosaic plan.
- Region boundaries require artist review.
- Tile availability quantities depend on accurate palette metadata.
- CIEDE2000 on digital color may not match glazed ceramic under installation lighting.
- Individual broken-tile shapes, grout widths, and tessellation are not solved.
- Text and lettering require manual design.
- Physical area estimates require accurate dimensions.
- Contour SVG is approximate planning geometry, not fabrication CAD.

## Possible Next Improvements

- palette entries with measured Lab values from photographed/calibrated physical samples;
- artist-assisted region split, merge, and tile reassignment tools;
- inventory quantities and shortage warnings;
- better label placement for narrow or concave regions;
- optional shard preview generated strictly from the immutable region map.
