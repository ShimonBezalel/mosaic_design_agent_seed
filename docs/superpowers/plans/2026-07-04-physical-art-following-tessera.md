# Physical Art-Following Tessera Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional deterministic, physically scaled, flow-oriented tessera subdivision layer inside the existing palette-constrained color-region map.

**Architecture:** Keep SLIC and connected cleanup as the color-area layer. Pass its in-memory source, mask, tile-index, and region-ID arrays into a separate physical-scale tessera engine that generates deterministic seeds, computes image-flow orientation, assigns pixels with an anisotropic KD-tree-shortlisted metric, and exports independent shard artifacts.

**Tech Stack:** Python 3.10+, Pydantic 2, NumPy, Pillow, scikit-image, SciPy, Gradio, pytest, standard-library CSV/JSON/SVG/ZIP.

---

## File Responsibilities

**Create:**

- `mosaic_agent/physical_scale.py`: full-image and mask-bbox millimeter transforms.
- `mosaic_agent/flow_field.py`: edge-tangent flow, confidence, regional orientation, PCA fallback, axial blending.
- `mosaic_agent/tessera.py`: seed generation, anisotropic assignment, cleanup, records, QA, signature.
- `mosaic_agent/tessera_export.py`: tessera raster, SVG, CSV, and QA exports.
- `tests/test_physical_scale.py`
- `tests/test_flow_field.py`
- `tests/test_tessera_subdivision.py`
- `tests/test_tessera_exports.py`
- `tests/test_workbench_tessera_flow.py`
- `docs/physical_tessera_subdivision.md`

**Modify:**

- `mosaic_agent/tile_map_models.py`: physical, tessera, color-region, request, and result contracts.
- `mosaic_agent/region_map.py`: expose SLIC compactness.
- `mosaic_agent/palette_compiler.py`: physical color-area minimum and optional tessera orchestration.
- `mosaic_agent/tile_map_export.py`: conditional report content.
- `mosaic_workbench/controllers.py`: accept and pass physical/tessera controls.
- `mosaic_workbench/app.py`: two compile sections, controls, previews, QA.
- Existing compiler/export/workbench tests: preserve M1 defaults and artifact behavior.
- `README.md`, `STATUS.md`, `docs/deterministic_tile_map_compiler.md`: M2 workflow and limitations.

### Task 1: Physical And Tessera Contracts

**Files:**
- Create: `tests/test_physical_scale.py`
- Modify: `tests/test_tile_map_models.py`
- Create: `mosaic_agent/physical_scale.py`
- Modify: `mosaic_agent/tile_map_models.py`

- [ ] **Step 1: Write failing physical-scale and model tests**

Tests define the desired API:

```python
def test_full_image_scale_uses_working_dimensions():
    work = np.ones((100, 200), dtype=bool)
    scale = build_physical_scale((200, 100), work, 2000, 1000, "full_image")
    assert scale.mm_per_px_x == pytest.approx(10)
    assert scale.mm_per_px_y == pytest.approx(10)


def test_mask_bbox_scale_uses_only_mask_bounds():
    work = np.zeros((100, 200), dtype=bool)
    work[20:80, 50:150] = True
    scale = build_physical_scale((200, 100), work, 2000, 1200, "mask_bbox")
    assert scale.mm_per_px_x == pytest.approx(20)
    assert scale.mm_per_px_y == pytest.approx(20)


def test_tessera_options_validate_edge_order():
    with pytest.raises(ValidationError, match="edge ordering"):
        TesseraCompileOptions(min_short_edge_mm=20, target_short_edge_mm=10)
```

Cover axis length conversion, cm2-to-pixel area, empty mask, missing dimensions, aspect validation, positive grout/seed caps, request defaults, result serialization, and backward-compatible `RegionRecord` import.

- [ ] **Step 2: Run tests and verify missing-module/import failures**

Run: `python -m pytest tests/test_physical_scale.py tests/test_tile_map_models.py -q`

Expected: failures identify absent `physical_scale`, `PhysicalScale`, and tessera contracts.

- [ ] **Step 3: Implement strict contracts and physical transforms**

Add these public types:

```python
PhysicalScaleBasis = Literal["full_image", "mask_bbox"]
FlowStrength = Literal["none", "low", "medium", "high"]
EdgeFollowing = Literal["low", "medium", "high"]
ShapeStyle = Literal["irregular", "angular", "smooth", "slivered"]

class PhysicalScale(StrictModel):
    image_width_px: int
    image_height_px: int
    physical_width_mm: float
    physical_height_mm: float
    mm_per_px_x: float
    mm_per_px_y: float
    px_per_mm_x: float
    px_per_mm_y: float
    scale_basis: PhysicalScaleBasis

class TesseraCompileOptions(StrictModel):
    physical_scale_basis: PhysicalScaleBasis = "mask_bbox"
    min_short_edge_mm: float = 8
    target_short_edge_mm: float = 18
    max_long_edge_mm: float = 55
    preferred_aspect_ratio: float = 1.8
    max_aspect_ratio: float = 4.0
    flow_strength: FlowStrength = "medium"
    edge_following: EdgeFollowing = "medium"
    shape_style: ShapeStyle = "irregular"
    random_seed: int = 0
    grout_width_mm: float = 2
    max_tessera_count: int = 3000
```

Add strict `TesseraCompileRequest`, `TesseraRecord`, and `TesseraCompileResult` with objective fields. Add `tessera_options: TesseraCompileOptions | None`, `physical_scale_basis`, `minimum_color_area_cm2`, and `color_compactness` to `PaletteCompileRequest`. Add optional tessera result to `PaletteCompileResult`. Define `ColorRegion` and retain `RegionRecord = ColorRegion`.

Implement `build_physical_scale`, `length_mm_to_px`, `area_mm2_to_px`, and `area_px_to_mm2`. Use bbox width `x2-x1` and height `y2-y1`.

- [ ] **Step 4: Run physical/model tests to green**

Run: `python -m pytest tests/test_physical_scale.py tests/test_tile_map_models.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit contracts and scale**

```bash
git add mosaic_agent/tile_map_models.py mosaic_agent/physical_scale.py tests/test_physical_scale.py tests/test_tile_map_models.py
git commit -m "Add physical tessera contracts and scale"
```

### Task 2: Color-Area Compactness And Physical Minimum

**Files:**
- Modify: `tests/test_palette_compiler.py`
- Modify: `mosaic_agent/region_map.py`
- Modify: `mosaic_agent/palette_compiler.py`

- [ ] **Step 1: Write failing compactness and physical-area tests**

Add tests that call `segment_work_area` with identical source/mask/target inputs and compactness values `2.0` and `12.0`, assert deterministic repeats, and assert different label maps on a synthetic gradient. Add a compile test with a known 100x100 cm field and `minimum_color_area_cm2=100` that verifies the normalized pixel threshold in result parameters. Add a missing-dimensions error test.

- [ ] **Step 2: Verify failures identify absent parameters/conversion**

Run: `python -m pytest tests/test_palette_compiler.py -q`

Expected: calls reject `compactness` or physical minimum is absent.

- [ ] **Step 3: Pass compactness through SLIC and convert minimum area**

Add `compactness: float = 5.0` to `segment_work_area` and `create_initial_tile_map`, pass it unchanged to `skimage.segmentation.slic`, and preserve the same deterministic grid fallback call when SLIC fails.

Use the request compactness in palette compilation. If `minimum_color_area_cm2` is supplied, build physical scale and convert `cm2 * 100` to pixels; use that threshold for connected cleanup. Record both requested cm2 and effective pixels in parameters.

- [ ] **Step 4: Run compiler tests to green and commit**

Run: `python -m pytest tests/test_palette_compiler.py -q`

```bash
git add mosaic_agent/region_map.py mosaic_agent/palette_compiler.py tests/test_palette_compiler.py
git commit -m "Expose organic color-area controls"
```

### Task 3: Art-Flow Field

**Files:**
- Create: `tests/test_flow_field.py`
- Create: `mosaic_agent/flow_field.py`

- [ ] **Step 1: Write failing synthetic orientation tests**

Create vertical stripe, horizontal band, diagonal line, flat image, and elongated-mask tests. Compare axial angular error with a helper that treats 0 and 180 degrees as equivalent:

```python
def axial_error_degrees(actual, expected):
    return abs(((actual - expected + 90) % 180) - 90)

def test_vertical_stripe_has_vertical_tangent_flow():
    field = compute_gradient_orientation_field(vertical_stripe())
    orientation, confidence = dominant_orientation_for_mask(field, stripe_edge_mask())
    assert axial_error_degrees(np.degrees(orientation), 90) < 12
    assert confidence > 0.2
```

Flat-image confidence must be below 0.05 and `resolve_region_orientation` must return deterministic PCA fallback. Elongated horizontal and diagonal masks must return their major axes.

- [ ] **Step 2: Verify tests fail on missing flow module**

Run: `python -m pytest tests/test_flow_field.py -q`

Expected: `ModuleNotFoundError: mosaic_agent.flow_field`.

- [ ] **Step 3: Implement doubled-angle flow and PCA fallback**

Export a frozen `FlowField` dataclass with `orientation_radians`, `confidence`, and `magnitude` arrays. Export `compute_gradient_orientation_field(source_rgb, sigma=2.0)`, `dominant_orientation_for_mask(field, mask)`, `pca_orientation_for_mask(mask, scale)`, `blend_axial_orientations(base, flow, weight)`, and `resolve_region_orientation(field, mask, scale, flow_strength)` with the return types fixed in the design specification.

Use Sobel gradients, tangent angle, Gaussian doubled-angle smoothing, confidence normalization, and physical-coordinate PCA.

- [ ] **Step 4: Run flow tests to green and commit**

Run: `python -m pytest tests/test_flow_field.py -q`

```bash
git add mosaic_agent/flow_field.py tests/test_flow_field.py
git commit -m "Compute deterministic art-flow orientation"
```

### Task 4: Tessera Seeds And Anisotropic Assignment

**Files:**
- Create: `tests/test_tessera_subdivision.py`
- Create: `mosaic_agent/tessera.py`

- [ ] **Step 1: Write failing seed and assignment tests**

Cover required cases 14 through 26. Public test API:

```python
def test_seed_generation_is_repeatable(simple_context):
    first = generate_tessera_seeds(simple_context, options(seed=7))
    second = generate_tessera_seeds(simple_context, options(seed=7))
    assert first == second

def test_tessera_map_cannot_cross_parent_regions(two_region_context):
    result = subdivide_tesserae(two_region_context, options())
    assert result.outside_mask_pixel_count == 0
    assert result.crosses_region_boundary_count == 0
    assert np.array_equal(result.parent_region_map[result.work_mask], two_region_context.region_ids[result.work_mask])
```

Test smaller target creates more seeds, all seeds are inside parent regions, narrow regions receive multiple axial seeds, exact coverage, inherited tile IDs, slivered style has higher mean aspect ratio than smooth, vertical flow alignment, tiny-fragment warning/merge, count-cap error, seed changes signature, and repeated signatures match.

- [ ] **Step 2: Verify tests fail on missing tessera module**

Run: `python -m pytest tests/test_tessera_subdivision.py -q`

Expected: missing module/import failures.

- [ ] **Step 3: Implement deterministic seeds**

Define frozen internal dataclasses `TesseraContext`, `TesseraSeed`, and `TesseraSubdivision`. Generate desired counts from physical area and target area. Build jittered physical lattice candidates keyed by SHA-256 of region/grid/user seed. Add deterministic major-axis and farthest-pixel support until desired count is met. Reject the whole request before assignment if desired total exceeds the cap.

- [ ] **Step 4: Implement anisotropic KD-tree assignment and cleanup**

For each parent color region, query up to 12 nearest seeds using `scipy.spatial.cKDTree`. Evaluate the flow-oriented ellipse metric, assign stable ties, split disconnected seed components, merge physically tiny fragments along the largest shared boundary, and renumber by parent then top-left order.

Build `TesseraRecord` metrics from physical-coordinate covariance and contours. Build invariant counts and SHA-256 signature from final maps and normalized options.

- [ ] **Step 5: Run tessera tests to green and commit**

Run: `python -m pytest tests/test_tessera_subdivision.py -q`

```bash
git add mosaic_agent/tessera.py tests/test_tessera_subdivision.py
git commit -m "Subdivide color regions into flow-oriented tesserae"
```

### Task 5: Compiler Orchestration And Tessera Exports

**Files:**
- Create: `tests/test_tessera_exports.py`
- Create: `mosaic_agent/tessera_export.py`
- Modify: `mosaic_agent/palette_compiler.py`
- Modify: `mosaic_agent/tile_map_export.py`
- Modify: `tests/test_tile_map_export.py`

- [ ] **Step 1: Write failing integrated export tests**

Compile a small two-color source with physical dimensions and enabled options. Assert all five tessera files exist, PNG dimensions match color outputs, SVG groups have `data-tessera-id` and `data-parent-region-id`, CSV headers match the objective, QA invariant checks pass, report contains previews/links, archive includes files, and disabled compilation retains exactly the M1 artifact set.

- [ ] **Step 2: Verify export tests fail on missing artifacts**

Run: `python -m pytest tests/test_tessera_exports.py tests/test_tile_map_export.py -q`

Expected: enabled compile lacks tessera paths/files.

- [ ] **Step 3: Integrate subdivision after color compilation**

When options are enabled, require physical dimensions, build scale, create `TesseraContext` from authoritative arrays, call `subdivide_tesserae`, write tessera artifacts, attach `TesseraCompileResult`, and extend palette compile parameters. Disabled path must not instantiate the tessera engine.

- [ ] **Step 4: Render and export tessera artifacts**

Write exact-color map plus grout-width boundaries, source overlay, contour SVG, required CSV, and required QA JSON. Extend compile report conditionally with two images, QA summary, and links. Keep `export_compile_archive` generic so it naturally includes the files.

- [ ] **Step 5: Run export/compiler suites and commit**

Run: `python -m pytest tests/test_palette_compiler.py tests/test_tile_map_export.py tests/test_tessera_exports.py -q`

```bash
git add mosaic_agent/palette_compiler.py mosaic_agent/tile_map_export.py mosaic_agent/tessera_export.py tests/test_tile_map_export.py tests/test_tessera_exports.py
git commit -m "Export physically scaled tessera planning maps"
```

### Task 6: Session And Gradio Workbench Flow

**Files:**
- Create: `tests/test_workbench_tessera_flow.py`
- Modify: `tests/test_workbench_app.py`
- Modify: `mosaic_workbench/controllers.py`
- Modify: `mosaic_workbench/app.py`

- [ ] **Step 1: Write failing controller and app tests**

Assert enabled controller compile with a 200x200 cm field and 8/18/55 mm controls returns tessera artifacts; disabled compile has `tessera_result is None`; missing dimensions raises friendly text; full archive includes tessera files. Assert app config contains both section headings, all M2 control labels, output labels, and explanatory copy.

- [ ] **Step 2: Verify tests fail on missing arguments and controls**

Run: `python -m pytest tests/test_workbench_tessera_flow.py tests/test_workbench_app.py -q`

Expected: controller rejects new options or labels are absent.

- [ ] **Step 3: Extend controller without changing source resolution**

Add keyword arguments for color compactness, minimum color area cm2, enable flag, scale basis, all tessera edge/aspect/flow/style/seed/grout/cap controls. Build `TesseraCompileOptions` only when enabled and pass through `PaletteCompileRequest`.

- [ ] **Step 4: Split compile tab and add outputs**

Create unframed headings `Color-area compilation` and `Tessera / shard subdivision`. Replace visible pixel-minimum wording with optional `Minimum color area (cm²)`. Add regularity radio and every required tessera control with objective defaults. Add tessera map, boundaries, and QA Markdown. Handler returns empty tessera outputs when disabled.

- [ ] **Step 5: Run workbench tests and full regression suite**

Run: `python -m pytest tests/test_workbench_tessera_flow.py tests/test_workbench_app.py tests/test_workbench_compile_flow.py -q`

Run: `python -m pytest -q`

Expected: all old and new tests pass; paid canaries remain skipped.

- [ ] **Step 6: Commit workbench integration**

```bash
git add mosaic_workbench/controllers.py mosaic_workbench/app.py tests/test_workbench_tessera_flow.py tests/test_workbench_app.py
git commit -m "Add physical tessera controls to workbench"
```

### Task 7: Documentation, Performance, Visual QA, And Integration

**Files:**
- Create: `docs/physical_tessera_subdivision.md`
- Modify: `docs/deterministic_tile_map_compiler.md`
- Modify: `README.md`
- Modify: `STATUS.md`

- [ ] **Step 1: Document M2 workflow and limitations**

Explain separate color/tessera layers, both scale bases, mm-to-pixel conversion, flow field, seed/assignment method, safeguards, exports, Yael workflow, and honest limitations. Add launch and demo settings for a 200x200 cm field with 8/18/55 mm pieces.

- [ ] **Step 2: Run deterministic and performance audits**

Compile synthetic and checked-in demo inputs twice into separate `/tmp` directories. Compare signatures and invariant checks. Benchmark a practical image and confirm runtime is interactive and tessera count remains below cap. Inspect that tesserae are smaller than color regions and slivered/flow mode has visibly elongated pieces.

- [ ] **Step 3: Launch isolated workbench and perform browser QA**

Run a tmux QA server on port 7863. Verify page identity, sections, enabled 200x200 cm compilation, previews, QA, report, ZIP, disabled M1 path, desktop, 390x844 mobile, and console health. Fix regressions through failing tests.

- [ ] **Step 4: Run final acceptance audit**

Run `python -m pytest -q`, count new tests, inspect required files, validate archive members, run `git diff --check`, confirm `git ls-files runs` is empty, and map evidence to all 12 acceptance criteria.

- [ ] **Step 5: Commit docs, merge, push, and restart persistent server**

```bash
git add README.md STATUS.md docs/physical_tessera_subdivision.md docs/deterministic_tile_map_compiler.md
git commit -m "Document physical tessera subdivision"
```

Fast-forward `main`, rerun tests from the primary checkout, push `origin main`, remove the owned worktree, and restart tmux session `mosaic_workbench` on `127.0.0.1:7862`.
