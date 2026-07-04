# Physical Tessera Subdivision

The workbench separates palette color regions from physically scaled tessera subdivision. The color map remains deterministic and palette-constrained; the tessera layer adds artist-controlled shard scale, orientation, and flow while preserving tile IDs.

Both layers are planning aids. Neither is a construction-ready cutting plan.

## Why There Are Two Layers

A color region answers: "Which studio tile color belongs here?" It is a connected paint-by-color area with one palette `tile_id`.

A tessera answers: "How might this color area break into installable pieces?" Every tessera belongs to exactly one color region and inherits its `tile_id`. Tessera subdivision never changes the palette map and cannot cross a color-region boundary.

This separation lets Yael adjust color composition independently from shard rhythm. Recompiling tesserae with a different seed, size, flow, or shape style does not rematch colors.

## Recommended Workflow

1. Compile and review the palette map, numbered color regions, legend, and color QA.
2. Correct the source, mask, selected palette, color compactness, or minimum color area until the broad color design is acceptable.
3. Enter measured physical dimensions and choose what they describe: the full source image or the masked field bounding box.
4. Enable tessera subdivision and set physical edge, aspect, flow, and style controls.
5. Review both the flat tessera map and the boundary overlay at installation viewing distance.
6. Inspect tessera QA and CSV warnings before using the output as an artist planning reference.
7. Redraw lettering, critical contours, and installation transitions manually.

## Physical Scale

The UI accepts centimeters and converts once to millimeters. For `full_image`, dimensions map to the working raster width and height. For `mask_bbox`, dimensions map to the inclusive bounding box of nonzero work-mask pixels.

```text
mm_per_px_x = physical_width_mm / basis_width_px
mm_per_px_y = physical_height_mm / basis_height_px
pixel_area_mm2 = mm_per_px_x * mm_per_px_y
```

Length controls use the appropriate axis. Area conversion uses the product of both axes. The geometric-mean scale is used only for grout preview width.

`mask_bbox` is the workbench default because artists commonly know the mosaic field dimensions rather than the dimensions of the surrounding photograph. Use `full_image` when the supplied dimensions describe the complete source frame.

If the requested physical piece count exceeds the explicit cap, compilation fails. If the working raster does not have at least one pixel per requested tessera, compilation also fails. Both failures require a larger physical target size, a higher explicit cap, or a higher-resolution source; the compiler does not silently change scale.

## Color-Area Controls

Mask-aware SLIC still forms the authoritative color regions. Color shape regularity maps to SLIC compactness:

- Organic: `2.0`
- Balanced: `5.0`
- Regular: `12.0`

An optional minimum color area in square centimeters converts through the selected physical scale and overrides the legacy internal pixel threshold. Color cleanup remains deterministic and palette-grounded.

## Flow And Piece Construction

The source is converted to grayscale. Sobel gradients define edge normals; their tangents define preferred shard direction. Axial orientations are smoothed in doubled-angle space so 0 and 180 degrees are equivalent. Low-gradient areas have low confidence and fall back to the physical major axis of the parent color region.

Target count per color region is:

```text
round(region_area_mm2 / (target_short_edge_mm**2 * preferred_aspect_ratio))
```

Seeds come from a deterministic, physically oriented lattice with SHA-256 jitter. Narrow regions receive major-axis support points. The user seed changes reproducible alternatives without introducing hidden randomness.

Each parent color region is assigned independently. A KD-tree finds nearby seeds, then an anisotropic metric favors each seed's flow direction and aspect ratio. Four-way connected components are enforced; tiny disconnected fragments merge along their largest shared boundary when possible and otherwise remain with QA warnings.

Shape styles affect lattice and metric behavior:

- `smooth`: lower variation and less elongation;
- `irregular`: moderate deterministic size and aspect variation;
- `angular`: 15-degree orientation quantization;
- `slivered`: stronger elongation up to the configured aspect cap.

## 200 x 200 cm Example

Launch the local workbench:

```bash
python -m mosaic_workbench.app --demo
```

For a two-meter-square field, start with:

- physical width and height: `200 cm`;
- scale basis: `mask_bbox` when the mask describes the full field;
- minimum short edge: `8 mm`;
- target short edge: `18 mm`;
- maximum long edge: `55 mm`;
- preferred / maximum aspect: `1.8 / 4.0`;
- flow / edge following: `medium / medium`;
- style: `irregular`;
- grout preview: `2 mm`;
- maximum tessera count: `7500`.

That target requests roughly 6,860 pieces over a full 4 m2 field. The source therefore needs at least that many work pixels. To retain the safer default cap of 3,000, raise the target short edge to about `28 mm` or reduce the physical work area.

## Outputs And QA

Enabled runs add:

- `tessera_map.png`: exact palette fills with grout-like preview boundaries;
- `tessera_boundaries.png`: source image with tessera boundaries;
- `tessera.svg`: raster-derived contour polygons with tessera, parent-region, and tile IDs;
- `tessera.csv`: area, centroid, orientation, edge estimates, aspect, and warnings;
- `tessera_qa_report.json`: coverage, containment, inheritance, cap, distribution, settings, scale, warnings, and signature.

The tessera signature covers final ID, parent, and tile maps, normalized controls, physical seed geometry, and seed. Paths and timestamps are excluded.

## Limitations

- Raster contours and PCA edge estimates are approximate planning geometry, not fabrication CAD.
- The algorithm does not model tile thickness, fracture mechanics, stock shape, cutting loss, substrate curvature, mortar, or installation order.
- Grout width changes rendering only; it does not shrink geometry or calculate grout volume.
- Source edges are a heuristic for visual flow, not a semantic understanding of anatomy, lettering, or structural lines.
- Very small requested pieces require enough source resolution and can produce large SVG/CSV files.
- Tessera warnings are review prompts, not automatic fabrication approval.
- Hebrew and other critical lettering must be manually redrawn or vectorized.
