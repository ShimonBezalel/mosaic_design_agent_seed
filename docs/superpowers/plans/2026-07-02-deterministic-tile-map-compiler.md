# Deterministic Tile Map Compiler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline, deterministic finalized-image to studio-palette paint-by-color compiler and integrate it as the workbench's primary workflow without removing ideation.

**Architecture:** A pure `mosaic_agent` backend normalizes images and masks, segments with mask-aware SLIC, assigns CIEDE2000-nearest studio colors, cleans connected regions, and writes a complete planning bundle. Gradio only resolves source choices, collects controls, stores typed compile results in the existing session, and presents/export artifacts.

**Tech Stack:** Python 3.10+, Pydantic 2, NumPy, Pillow, scikit-image, Gradio 5/6, pytest, standard-library CSV/JSON/ZIP.

---

## File Map

**Create:**

- `mosaic_agent/tile_map_models.py`: strict request/result, region, and color-usage contracts.
- `mosaic_agent/region_map.py`: image/mask normalization, Lab matching, SLIC/grid segmentation, connected components, tiny-region merging, adjacency, and stable records.
- `mosaic_agent/palette_compiler.py`: request validation, deterministic orchestration, accounting, signature, and QA payload.
- `mosaic_agent/tile_map_export.py`: raster, SVG, CSV, JSON, HTML, and archive rendering.
- `tests/test_tile_map_models.py`: model and validation behavior.
- `tests/test_palette_compiler.py`: matching, masks, segmentation, cleanup, determinism, accounting, and seeded invariants.
- `tests/test_tile_map_export.py`: artifact formats, contents, reports, and bundle archive.
- `tests/test_workbench_compile_flow.py`: source resolution, session state, standalone compile, latest variant, and full export.
- `examples/tile_compile_demo/*`: deterministic visual fixture and notes.
- `docs/deterministic_tile_map_compiler.md`: user-facing algorithm and limitations.

**Modify:**

- `pyproject.toml`: add NumPy and scikit-image runtime dependencies.
- `mosaic_agent/session_models.py`: persist accepted source and compile results.
- `mosaic_workbench/controllers.py`: compile source resolution and session update.
- `mosaic_workbench/export.py`: include compile runs and allow compile-only session export.
- `mosaic_workbench/app.py`: compile tab, handlers, concise concepts, and demo inputs.
- `tests/test_workbench_app.py`: compile controls and concept-summary behavior.
- `tests/test_workbench_session.py`: compile-aware full export behavior.
- `README.md`: product framing, workflow, artifacts, and limitations.
- `STATUS.md`: milestone status.

### Task 1: Dependencies and Typed Compile Contracts

**Files:**
- Modify: `pyproject.toml`
- Create: `mosaic_agent/tile_map_models.py`
- Create: `tests/test_tile_map_models.py`

- [ ] **Step 1: Write failing request/result model tests**

Create tests that instantiate all four models and assert strict validation:

```python
def test_compile_request_defaults_to_strict_palette(tmp_path, source, palette):
    request = PaletteCompileRequest(
        source_image_path=str(source),
        palette_db_path=str(palette),
        selected_palette_ids=["red"],
        granularity="medium",
        min_region_area_px=8,
        boundary_smoothing="light",
        merge_tiny_regions=True,
        output_dir=str(tmp_path / "out"),
    )
    assert request.strict_palette is True
    assert request.mask_image_path is None


@pytest.mark.parametrize("value", [0, -1])
def test_compile_request_rejects_non_positive_min_area(valid_request_data, value):
    with pytest.raises(ValidationError):
        PaletteCompileRequest(**valid_request_data, min_region_area_px=value)


def test_compile_request_rejects_non_strict_mode(valid_request_data):
    with pytest.raises(ValidationError, match="strict palette"):
        PaletteCompileRequest(**valid_request_data, strict_palette=False)


def test_color_usage_serializes_tile_identity():
    usage = ColorUsage(
        tile_id="red", tile_name="Red", hex="#ff0000", pixel_count=10,
        percent_of_mask=100.0, region_count=1, mean_delta_e=0.0, max_delta_e=0.0,
    )
    assert usage.model_dump(mode="json")["tile_id"] == "red"
```

Cover missing source/palette paths, duplicate selected IDs, invalid `max_colors`, invalid target count, one-sided physical dimensions, and bbox/centroid serialization.

- [ ] **Step 2: Run tests and verify the missing-module failure**

Run: `python -m pytest tests/test_tile_map_models.py -q`

Expected: collection fails with `ModuleNotFoundError: mosaic_agent.tile_map_models`.

- [ ] **Step 3: Add dependencies and implement strict models**

Add to `pyproject.toml`:

```toml
  "numpy>=1.24",
  "scikit-image>=0.21",
```

Implement these exact contracts:

```python
Granularity = Literal["coarse", "medium", "fine"]
BoundarySmoothing = Literal["none", "light", "medium"]

class PaletteCompileRequest(StrictModel):
    source_image_path: str
    mask_image_path: str | None = None
    palette_db_path: str
    selected_palette_ids: list[str] = Field(default_factory=list)
    max_colors: int | None = Field(default=None, ge=1)
    granularity: Granularity = "medium"
    target_region_count: int | None = Field(default=None, ge=1)
    min_region_area_px: int = Field(default=64, ge=1)
    boundary_smoothing: BoundarySmoothing = "light"
    merge_tiny_regions: bool = True
    strict_palette: bool = True
    physical_width_cm: float | None = Field(default=None, gt=0)
    physical_height_cm: float | None = Field(default=None, gt=0)
    output_dir: str

class ColorUsage(StrictModel):
    tile_id: str
    tile_name: str
    hex: str
    pixel_count: int
    percent_of_mask: float
    estimated_area_cm2: float | None = None
    region_count: int
    mean_delta_e: float
    max_delta_e: float

class RegionRecord(StrictModel):
    region_id: int
    tile_id: str
    pixel_count: int
    estimated_area_cm2: float | None = None
    bbox_xyxy: tuple[int, int, int, int]
    centroid_xy: tuple[float, float]
    mean_source_rgb: tuple[float, float, float]
    mean_source_lab: tuple[float, float, float]
    delta_e: float
    neighbor_region_ids: list[int] = Field(default_factory=list)

class PaletteCompileResult(StrictModel):
    run_id: str
    source_image_path: str
    mask_image_path: str
    palette_map_path: str
    region_labels_path: str
    region_boundaries_path: str
    regions_svg_path: str
    legend_csv_path: str
    regions_csv_path: str
    qa_report_path: str
    compile_report_html_path: str
    compile_request_path: str
    region_count: int
    color_count: int
    masked_pixel_count: int
    color_usage: list[ColorUsage]
    regions: list[RegionRecord]
    warnings: list[str]
    parameters: dict[str, object]
```

Use model validators to require both physical dimensions or neither, reject duplicate selected IDs, verify source/palette/mask files exist, and reject `strict_palette=False` with `strict palette compilation is required`.

- [ ] **Step 4: Install editable dependencies and run model tests**

Run: `python -m pip install -e .`

Run: `python -m pytest tests/test_tile_map_models.py -q`

Expected: all model tests pass.

- [ ] **Step 5: Commit the contracts**

```bash
git add pyproject.toml mosaic_agent/tile_map_models.py tests/test_tile_map_models.py
git commit -m "Add deterministic tile map contracts"
```

### Task 2: Mask, Palette, and Perceptual Matching Primitives

**Files:**
- Create: `mosaic_agent/region_map.py`
- Create: `tests/test_palette_compiler.py`

- [ ] **Step 1: Write failing mask and exact color tests**

Use small generated PNGs and a three-color palette. Test the public helper behavior:

```python
def test_transparent_alpha_is_work_area(tmp_path):
    mask = rgba_mask(tmp_path, alpha=[[0, 255], [255, 0]])
    work = load_work_area(mask, (2, 2))
    assert work.tolist() == [[True, False], [False, True]]


def test_black_white_mask_uses_white_as_work_area(tmp_path):
    mask = grayscale_mask(tmp_path, [[255, 0], [0, 255]])
    assert load_work_area(mask, (2, 2)).tolist() == [[True, False], [False, True]]


def test_mask_resize_is_nearest_neighbor(tmp_path):
    work = load_work_area(two_pixel_mask, (4, 2))
    assert work[:, :2].all()
    assert not work[:, 2:].any()


def test_nearest_palette_color_matches_exact_lab_color():
    assert nearest_palette_index(rgb_to_lab([[255, 0, 0]]), palette_lab) == [0]
```

Also test no-mask means all pixels, six-digit hex validation, selected palette filtering, stable tile ordering, and a selected-ID error.

- [ ] **Step 2: Verify primitive tests fail because functions are absent**

Run: `python -m pytest tests/test_palette_compiler.py -q`

Expected: collection fails importing `mosaic_agent.region_map`.

- [ ] **Step 3: Implement normalization and matching helpers**

Implement a frozen `PaletteArrays` dataclass with `tiles`, `rgb`, and `lab` arrays and a frozen `NormalizedSource` dataclass with RGB pixels, original size, working size, and scale. Export `parse_hex_rgb`, `build_palette_arrays`, `load_source_rgb`, `load_work_area`, `rgb_to_lab`, and `nearest_palette_indices` with the parameter and return types fixed in the design specification.

`nearest_palette_indices` computes a CIEDE2000 matrix one palette column at a time and uses `np.argmin`, preserving palette order for ties.

- [ ] **Step 4: Run primitive tests to green**

Run: `python -m pytest tests/test_palette_compiler.py -q`

Expected: the mask, hex, filtering, and exact color tests pass.

- [ ] **Step 5: Commit normalization and matching**

```bash
git add mosaic_agent/region_map.py tests/test_palette_compiler.py
git commit -m "Add mask-aware perceptual palette matching"
```

### Task 3: Deterministic Segmentation and Region Cleanup

**Files:**
- Modify: `mosaic_agent/region_map.py`
- Modify: `tests/test_palette_compiler.py`

- [ ] **Step 1: Write failing segmentation and cleanup tests**

Add synthetic tests for requirements 10 through 18:

```python
def test_two_color_image_assigns_two_expected_tiles(two_color_source, full_work_mask, test_palette):
    segmented = create_initial_tile_map(two_color_source, full_work_mask, test_palette, granularity="coarse")
    assert set(segmented.tile_indices[work]) == {red_index, blue_index}


def test_adjacent_same_tile_segments_become_one_component():
    tiles = np.array([[0, 0], [0, 0]])
    labels = label_tile_components(tiles, np.ones((2, 2), dtype=bool))
    assert set(labels.ravel()) == {1}


def test_tiny_island_merges_to_best_adjacent_region(tiny_island_case):
    cleaned = merge_tiny_tile_regions(*tiny_island_case, min_region_area_px=4)
    assert island_tile not in cleaned.tile_indices[island_mask]
    assert int(cleaned.work_mask.sum()) == original_count


def test_disabling_tiny_merge_preserves_more_regions(compiled_with_merge, compiled_without_merge):
    assert without_merge.region_count > with_merge.region_count
```

Include stable tie-breaking, isolated-region warning, same masked pixel count, target-count override, and coarse/fine region-count tolerance.

- [ ] **Step 2: Run the new tests and verify missing behavior failures**

Run selected tests with `python -m pytest tests/test_palette_compiler.py -q`.

Expected: failures name missing segmentation/component/merge functions.

- [ ] **Step 3: Implement deterministic SLIC and grid fallback**

Implement `derive_segment_target`, `smooth_source_lab`, `segment_work_area`, `assign_segments_to_palette`, and `reduce_palette_by_demand`. Use frozen dataclasses for segment assignment results so tests can inspect labels, tile indices, distances, retained colors, and fallback status without mutating compiler state.

Call `skimage.segmentation.slic` with `convert2lab=False`, `start_label=1`, `mask=work_mask`, `channel_axis=-1`, `compactness=10`, and `enforce_connectivity=True`. Catch only segmentation-specific exceptions, then produce deterministic rectangular grid labels and mark fallback use.

- [ ] **Step 4: Implement connected components, adjacency, and deterministic tiny merging**

Implement four-way component labeling with `skimage.measure.label(connectivity=1)`. Build shared-boundary counts by scanning right and down neighbor pairs. Reassign tiny components using `(color_penalty, -shared_boundary, -neighbor_area, neighbor_id)`, relabel after each pass, and cap at 100 passes.

Expose `label_tile_components`, `merge_tiny_tile_regions`, and `build_region_records`. `merge_tiny_tile_regions` returns a frozen `CleanupResult` carrying final tile indices, region IDs, warning strings, and iteration count.

- [ ] **Step 5: Run all region tests to green**

Run: `python -m pytest tests/test_palette_compiler.py -q`

Expected: all segmentation and cleanup tests pass consistently across two consecutive runs.

- [ ] **Step 6: Commit the region engine**

```bash
git add mosaic_agent/region_map.py tests/test_palette_compiler.py
git commit -m "Implement deterministic mosaic region cleanup"
```

### Task 4: Compiler Orchestration, Accounting, and Signature

**Files:**
- Create: `mosaic_agent/palette_compiler.py`
- Modify: `tests/test_palette_compiler.py`

- [ ] **Step 1: Write failing end-to-end compiler tests**

Test `compile_palette_map(request)` against generated fixtures:

```python
def test_compile_uses_only_selected_tile_ids(make_request):
    result = compile_palette_map(make_request(selected=["red", "blue"]))
    assert {usage.tile_id for usage in result.color_usage} <= {"red", "blue"}


def test_same_request_in_different_output_dirs_has_same_signature(make_request, tmp_path):
    first = compile_palette_map(make_request(output_dir=tmp_path / "one"))
    second = compile_palette_map(make_request(output_dir=tmp_path / "two"))
    assert read_qa(first)["deterministic_signature"] == read_qa(second)["deterministic_signature"]


def test_legend_and_regions_account_for_every_masked_pixel(make_request):
    result = compile_palette_map(make_request())
    assert sum(item.pixel_count for item in result.color_usage) == result.masked_pixel_count
    assert sum(item.pixel_count for item in result.regions) == result.masked_pixel_count
    assert sum(item.percent_of_mask for item in result.color_usage) == pytest.approx(100)
```

Also test max-color demand reduction, optional/complete physical estimates, resize warnings, empty mask error, no-mask whole image, palette-map exact colors, deterministic seeded random images, and signature changes when parameters change.

- [ ] **Step 2: Run compiler tests and verify import/function failures**

Run: `python -m pytest tests/test_palette_compiler.py -q`

Expected: end-to-end tests fail importing `compile_palette_map`.

- [ ] **Step 3: Implement the orchestration pipeline**

Implement:

```python
def compile_palette_map(request: PaletteCompileRequest) -> PaletteCompileResult:
    palette = load_palette(request.palette_db_path)
    selected = build_palette_arrays(palette, request.selected_palette_ids)
    source = load_source_rgb(request.source_image_path)
    work = load_work_area(request.mask_image_path, source.size)
    # smooth, segment, assign, reduce, relabel, merge, record, account
    # build deterministic signature from canonical bytes
    # delegate artifact writing to tile_map_export
```

Use a temporary in-memory `CompiledTileMap` dataclass to carry arrays to export. Generate `run_id` from the first 12 signature characters so repeated runs are semantically identifiable without timestamps.

Build QA fields exactly:

```python
{
  "masked_pixel_count": int,
  "region_count": int,
  "color_count": int,
  "parameters": dict,
  "warnings": list[str],
  "worst_regions_by_delta_e": list[dict],
  "tiny_regions_remaining": list[int],
  "colors_used_not_in_selected_palette": list[str],
  "legend_area_sum_check": {"expected": int, "actual": int, "matches": bool},
  "region_area_sum_check": {"expected": int, "actual": int, "matches": bool},
  "original_dimensions": [int, int],
  "working_dimensions": [int, int],
  "working_scale": float,
  "deterministic_signature": str,
}
```

- [ ] **Step 4: Run compiler tests to green**

Run: `python -m pytest tests/test_palette_compiler.py -q`

Expected: color, mask, region, accounting, max-color, resize, physical-area, and seeded determinism tests pass.

- [ ] **Step 5: Commit compiler orchestration**

```bash
git add mosaic_agent/palette_compiler.py mosaic_agent/region_map.py tests/test_palette_compiler.py
git commit -m "Build deterministic studio palette compiler"
```

### Task 5: Render and Export the Paint-by-Color Bundle

**Files:**
- Create: `mosaic_agent/tile_map_export.py`
- Create: `tests/test_tile_map_export.py`

- [ ] **Step 1: Write failing artifact and content tests**

Test all named outputs and schemas:

```python
REQUIRED = {
    "source_image.png", "mask.png", "palette_map.png", "region_labels.png",
    "region_boundaries.png", "regions.svg", "legend.csv", "regions.csv",
    "qa_report.json", "compile_report.html", "compile_request.json",
}

def test_compile_writes_complete_bundle(compiled):
    assert REQUIRED <= {path.name for path in Path(compiled.output_dir).iterdir()}


def test_svg_contains_region_metadata(compiled):
    root = ElementTree.parse(compiled.regions_svg_path).getroot()
    groups = root.findall(".//{http://www.w3.org/2000/svg}g")
    assert groups
    assert all("data-region-id" in group.attrib and "data-tile-id" in group.attrib for group in groups)


def test_csv_headers_match_contract(compiled):
    assert next(csv.reader(open(compiled.legend_csv_path))) == EXPECTED_LEGEND_HEADERS
    assert next(csv.reader(open(compiled.regions_csv_path))) == EXPECTED_REGION_HEADERS
```

Also assert report relative assets, disclaimer, warning text, normalized alpha mask semantics, numbered-map dimensions, boundary overlay dimensions, QA signature, and ZIP members.

- [ ] **Step 2: Run export tests and verify missing exporter failures**

Run: `python -m pytest tests/test_tile_map_export.py -q`

Expected: collection fails importing `mosaic_agent.tile_map_export` or artifact assertions fail.

- [ ] **Step 3: Implement raster, SVG, CSV, JSON, and HTML rendering**

Implement focused writers named `write_compile_artifacts`, `render_palette_map`, `render_region_labels`, `render_boundary_overlay`, `write_regions_svg`, `write_legend_csv`, `write_regions_csv`, `write_compile_report`, and `export_compile_archive`. `write_compile_artifacts` accepts `CompiledTileMap`, request, and QA payload and returns an `ArtifactPaths` dataclass. `export_compile_archive` accepts a typed result and destination path and returns the ZIP path.

Use Pillow's bundled default font with a contrasting stroke and dynamically bounded label size. Draw final boundaries from `skimage.segmentation.find_boundaries`. Generate SVG contours with `measure.find_contours`, XML-escape metadata, and group contours by final region. Always write the normalized RGBA mask.

- [ ] **Step 4: Run export tests to green**

Run: `python -m pytest tests/test_tile_map_export.py -q`

Expected: all artifact and archive tests pass.

- [ ] **Step 5: Run compiler and export tests together**

Run: `python -m pytest tests/test_palette_compiler.py tests/test_tile_map_export.py -q`

Expected: both suites pass with no network access.

- [ ] **Step 6: Commit artifact export**

```bash
git add mosaic_agent/tile_map_export.py mosaic_agent/palette_compiler.py tests/test_tile_map_export.py
git commit -m "Export paint-by-color planning bundles"
```

### Task 6: Session State, Source Resolution, and Full Export

**Files:**
- Modify: `mosaic_agent/session_models.py`
- Modify: `mosaic_workbench/controllers.py`
- Modify: `mosaic_workbench/export.py`
- Create: `tests/test_workbench_compile_flow.py`
- Modify: `tests/test_workbench_session.py`

- [ ] **Step 1: Write failing compile-flow integration tests**

Cover standalone upload, latest variant, base canvas, source errors, repeated runs, and full export:

```python
def test_compile_uploaded_image_without_concepts(session_without_concepts, source, mask):
    updated = compile_session_tile_map(
        session_without_concepts,
        source_choice="upload",
        uploaded_source_path=str(source),
        compile_mask_path=str(mask),
        whole_image=False,
        controls=controls(),
    )
    assert not updated.concepts
    assert updated.latest_compile_result is not None


def test_compile_uses_latest_generated_variant(session_with_two_runs):
    updated = compile_session_tile_map(
        session_with_two_runs,
        source_choice="latest_variant",
        uploaded_source_path=None,
        compile_mask_path=None,
        whole_image=True,
        max_colors=None,
        granularity="coarse",
        min_region_area_px=4,
        boundary_smoothing="none",
        merge_tiny_regions=True,
        physical_width_cm=None,
        physical_height_cm=None,
    )
    assert updated.accepted_source_image_path == session_with_two_runs.generation_runs[-1].image_paths[-1]


def test_full_export_contains_compile_artifacts(compile_session, tmp_path):
    export_session(compile_session, tmp_path / "export")
    assert (tmp_path / "export/compile_runs/run_01/qa_report.json").exists()
```

Assert compile-only full export succeeds without selected concept and that legacy selected-concept exports remain unchanged.

- [ ] **Step 2: Run integration tests and verify missing fields/functions**

Run: `python -m pytest tests/test_workbench_compile_flow.py tests/test_workbench_session.py -q`

Expected: failures identify absent session fields and compile controller.

- [ ] **Step 3: Extend session models and controller**

Add fields:

```python
accepted_source_image_path: str | None = None
compile_runs: list[PaletteCompileResult] = Field(default_factory=list)
latest_compile_result: PaletteCompileResult | None = None
```

Add `resolve_compile_source` with typed session, source choice, and uploaded path arguments. Add the compile controller with this exact signature:

```python
def compile_session_tile_map(
    session: InteractiveSession,
    *,
    source_choice: Literal["upload", "latest_variant", "base_canvas"],
    uploaded_source_path: str | None,
    compile_mask_path: str | None,
    whole_image: bool,
    max_colors: int | None,
    granularity: str,
    min_region_area_px: int,
    boundary_smoothing: str,
    merge_tiny_regions: bool,
    physical_width_cm: float | None,
    physical_height_cm: float | None,
) -> InteractiveSession:
    """Compile one source and return a copied session containing the immutable result."""
```

Use the session's normalized mask unless compile-specific mask overrides it; set mask to `None` in whole-image mode. Store output under `runs/workbench/<session_id>/compilations/run_XX`.

- [ ] **Step 4: Make full export compile-aware**

Write each compile run under `compile_runs/run_XX/`, add relative results to `manifest.json`, and permit export when either a selected concept or compile result exists. Write prompt/critique files only when a concept is selected.

- [ ] **Step 5: Run workbench integration tests to green**

Run: `python -m pytest tests/test_workbench_compile_flow.py tests/test_workbench_session.py -q`

Expected: upload/latest/base and compile-only/full-export tests pass.

- [ ] **Step 6: Commit session integration**

```bash
git add mosaic_agent/session_models.py mosaic_workbench/controllers.py mosaic_workbench/export.py tests/test_workbench_compile_flow.py tests/test_workbench_session.py
git commit -m "Integrate deterministic compilation with sessions"
```

### Task 7: Gradio Compile Tab and Concise Concept Summaries

**Files:**
- Modify: `mosaic_workbench/app.py`
- Modify: `tests/test_workbench_app.py`
- Modify: `tests/test_workbench_compile_flow.py`

- [ ] **Step 1: Write failing app-structure and UI-handler tests**

Assert app config includes:

```python
required_labels = {
    "Finalized source image", "Compile source", "Compile-specific mask",
    "Whole image", "Max colors", "Minimum region area (px)",
    "Boundary smoothing", "Merge tiny regions", "Strict palette",
    "Physical width (cm)", "Physical height (cm)", "Palette map",
    "Numbered region map", "Region boundaries", "Tile legend",
    "Compile bundle",
}
assert required_labels <= component_labels(build_app())
assert "5. Compile to Tile Map" in tab_labels(build_app())
```

Test `_compile_tile_map_ui` from a state with no concepts and `_render_concepts` for `<details>` plus absence of always-visible composition text.

- [ ] **Step 2: Run UI tests and verify missing controls/handler failures**

Run: `python -m pytest tests/test_workbench_app.py tests/test_workbench_compile_flow.py -q`

Expected: compile tab labels and handler are absent.

- [ ] **Step 3: Add the compile tab and event handlers**

Add source radio values `upload`, `latest_variant`, and `base_canvas`; finalized source image; compile mask; whole-image checkbox; controls; compile/export buttons; three image outputs; `gr.Dataframe` legend; warnings Markdown; and `gr.File` report/archive outputs.

`_compile_tile_map_ui` must create a minimal `InteractiveSession` from current brief/palette form values if no prepared session exists, enabling direct upload compilation. It then calls `compile_session_tile_map` and returns serialized state plus artifact paths/table/warnings.

`_export_compile_ui` calls `export_compile_archive` on `latest_compile_result` and returns the ZIP path.

Lock strict palette with `interactive=False`, `value=True`.

- [ ] **Step 4: Shorten concept rendering**

Render each concept as:

```html
<section>
  <h3>Concept name</h3>
  <p><strong>Thesis:</strong> one-line intent</p>
  <p><strong>Palette:</strong> tile chips</p>
  <details><summary>Details</summary><p>Composition text</p><p>Risk text</p></details>
</section>
```

Escape all model text and keep selection in the existing radio control.

- [ ] **Step 5: Run workbench UI tests to green**

Run: `python -m pytest tests/test_workbench_app.py tests/test_workbench_compile_flow.py -q`

Expected: tab, controls, standalone handler, latest variant handler, and concise concept tests pass.

- [ ] **Step 6: Commit the workbench UI**

```bash
git add mosaic_workbench/app.py tests/test_workbench_app.py tests/test_workbench_compile_flow.py
git commit -m "Add compile to tile map workbench tab"
```

### Task 8: Demo Fixture and Documentation

**Files:**
- Create: `examples/tile_compile_demo/source_image.png`
- Create: `examples/tile_compile_demo/mask.png`
- Create: `examples/tile_compile_demo/palette_db.json`
- Create: `examples/tile_compile_demo/expected_notes.md`
- Create: `docs/deterministic_tile_map_compiler.md`
- Modify: `README.md`
- Modify: `STATUS.md`

- [ ] **Step 1: Add a deterministic fixture-generation test**

Extend export tests to load the checked-in demo, compile it, and assert 3-5 used colors, excluded right strip, tiny-island cleanup, and complete outputs.

- [ ] **Step 2: Run the demo test and verify fixture absence**

Run: `python -m pytest tests/test_tile_map_export.py -k demo -q`

Expected: failure because `examples/tile_compile_demo/source_image.png` does not exist.

- [ ] **Step 3: Generate and add the small fixture**

Create a 320x200 RGB image with four broad geometric color regions and one 3x3 contrasting island. Create an RGBA mask with alpha zero over the left 280 pixels and alpha 255 over the excluded right strip. Add a four-color valid palette DB and notes describing expected cleanup.

Use a deterministic repository script invocation or Pillow one-off, then inspect all images before committing.

- [ ] **Step 4: Write product and algorithm documentation**

README must lead with: optional ideation, deterministic palette compilation, optional preview. Document launch, tab workflow, alpha/grayscale masks, strict palette discipline, artifacts, and all known limitations.

`docs/deterministic_tile_map_compiler.md` must document the ten algorithm stages, CIEDE2000, SLIC/grid fallback, region cleanup tie-breaks, signature inputs, performance cap, mask semantics, and limitations.

- [ ] **Step 5: Run demo and documentation checks**

Run: `python -m pytest tests/test_tile_map_export.py -k demo -q`

Run: `rg -n "planning aids|not construction-ready|CIEDE2000|transparent|selected palette" README.md docs/deterministic_tile_map_compiler.md`

Expected: demo passes and every required topic has at least one direct match.

- [ ] **Step 6: Commit demo and docs**

```bash
git add examples/tile_compile_demo docs/deterministic_tile_map_compiler.md README.md STATUS.md tests/test_tile_map_export.py
git commit -m "Document and demonstrate deterministic compilation"
```

### Task 9: Full Verification, Runtime QA, and Publication

**Files:**
- Modify only files required by failures found during verification.

- [ ] **Step 1: Run the complete automated suite**

Run: `python -m pytest -q`

Expected: all old and new tests pass; real-provider tests remain skipped without explicit environment flags.

- [ ] **Step 2: Verify test-count and requirement coverage**

Run:

```bash
rg -n "^def test_" tests/test_tile_map_models.py tests/test_palette_compiler.py tests/test_tile_map_export.py tests/test_workbench_compile_flow.py | wc -l
```

Expected: at least 35 compiler/export/workbench tests.

- [ ] **Step 3: Run a repeatability audit on the demo**

Compile the demo twice into separate temporary directories and compare `deterministic_signature`, selected tile sets, masked counts, legend sums, and region sums.

Expected: signatures and accounting are identical; palette violations are empty.

- [ ] **Step 4: Launch the workbench persistently**

Restart the existing `mosaic_workbench` tmux session with:

```bash
python -m mosaic_workbench.app --demo --server-name 127.0.0.1 --server-port 7862
```

Verify `curl http://127.0.0.1:7862/` returns HTTP 200.

- [ ] **Step 5: Perform browser QA**

Use the in-app browser to verify desktop and 390x844 mobile layouts. Load the compile demo, compile from uploaded finalized image without generating concepts, inspect palette/label/boundary images, legend, warnings, report, and ZIP. Then generate a stub variant and compile from latest variant. Confirm no browser console errors or overlapping controls.

- [ ] **Step 6: Audit export bundles and repository hygiene**

Inspect ZIP members and HTML relative links. Run:

```bash
git status --short
git diff --check
git ls-files runs
```

Expected: no generated run artifacts are tracked and no whitespace errors exist.

- [ ] **Step 7: Commit any verification fixes and push**

```bash
git add mosaic_agent mosaic_workbench tests examples docs README.md STATUS.md pyproject.toml
git commit -m "Verify deterministic tile map workflow"
git push origin main
```

Record the final commit SHA, full test result, launch URL, demo workflow, output list, limitations, and recommended next step.
