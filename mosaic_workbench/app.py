from __future__ import annotations

import argparse
import html
import shutil
from pathlib import Path
from uuid import uuid4

import gradio as gr
from PIL import Image

from mosaic_agent.load import load_brief, load_palette
from mosaic_agent.models import Canvas, ProjectBrief
from mosaic_agent.session_models import InteractiveSession
from mosaic_agent.tile_map_export import DISCLAIMER, export_compile_archive
from mosaic_workbench.controllers import (
    compile_session_tile_map,
    create_session,
    generate_concepts,
    generate_variants,
    select_session_concept,
)
from mosaic_workbench.export import export_session
from mosaic_workbench.mask_utils import save_drawn_mask


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PALETTE = ROOT / "examples" / "palette_db.example.json"
DEMO_PRESET = ROOT / "examples" / "workbench_demo" / "session_preset.json"


def build_app(*, demo: bool = False) -> gr.Blocks:
    defaults = _demo_defaults() if demo else {}

    with gr.Blocks(title="Mosaic Studio Workbench", fill_width=True) as app:
        session_state = gr.State(value=None)
        gr.Markdown(
            "# Mosaic Studio Workbench\n"
            "Optional visual ideation, deterministic palette compilation, and planning export.\n\n"
            "**Generated images are visual ideation only.**  \n"
            f"**{DISCLAIMER}**"
        )
        with gr.Row():
            load_demo = gr.Button("Load demo session")
            session_status = gr.Markdown("Start with the brief, palette, base canvas, and mask.")

        with gr.Tab("1. Brief & Palette"):
            with gr.Row():
                palette_path = gr.Textbox(
                    value=defaults.get("palette_db_path", str(DEFAULT_PALETTE)),
                    label="Palette DB path",
                    scale=3,
                )
                load_palette_button = gr.Button("Load palette", scale=1)
            palette_swatches = gr.HTML()
            selected_palette_ids = gr.CheckboxGroup(label="Selected palette IDs", choices=[])
            with gr.Row():
                project_name = gr.Textbox(value=defaults.get("project_name", ""), label="Project name")
                location = gr.Textbox(value=defaults.get("location", ""), label="Location")
                viewing_distance = gr.Number(
                    value=defaults.get("viewing_distance_m", 15),
                    label="Viewing distance (m)",
                )
                granularity = gr.Dropdown(
                    choices=["coarse", "medium", "fine", "mixed", "unknown"],
                    value=defaults.get("granularity", "mixed"),
                    label="Granularity",
                )
            intent = gr.Textbox(
                value=defaults.get("intent", ""),
                label="Short design brief",
                lines=3,
            )
            with gr.Row():
                required_text = gr.Textbox(
                    value=defaults.get("required_text", ""),
                    label="Required text",
                    lines=3,
                )
                mood = gr.Textbox(value=defaults.get("mood", ""), label="Mood", lines=3)
            with gr.Row():
                must_include = gr.Textbox(
                    value=defaults.get("must_include", ""),
                    label="Must include",
                    lines=3,
                )
                must_avoid = gr.Textbox(
                    value=defaults.get("must_avoid", ""),
                    label="Must avoid",
                    lines=3,
                )
            notes = gr.Textbox(value=defaults.get("notes", ""), label="Notes", lines=3)

        with gr.Tab("2. Canvas, References & Mask"):
            with gr.Row():
                base_image = gr.Image(
                    value=defaults.get("base_image_path"),
                    type="filepath",
                    label="Base canvas image",
                    sources=["upload", "clipboard"],
                )
                site_context = gr.Image(
                    value=defaults.get("site_context_path"),
                    type="filepath",
                    label="Optional site context",
                    sources=["upload", "clipboard"],
                )
            with gr.Row():
                style_references = gr.File(
                    value=defaults.get("style_reference_paths"),
                    file_count="multiple",
                    file_types=["image"],
                    type="filepath",
                    label="Style reference images (1-5)",
                )
                composition_sketch = gr.Image(
                    value=defaults.get("composition_sketch_path"),
                    type="filepath",
                    label="Optional composition sketch",
                    sources=["upload", "clipboard"],
                )
            reference_gallery = gr.Gallery(label="Session references", columns=4, height=220)
            with gr.Row():
                uploaded_mask = gr.Image(
                    value=defaults.get("mask_image_path"),
                    type="filepath",
                    image_mode="RGBA",
                    format="png",
                    label="Upload mask PNG",
                    sources=["upload", "clipboard"],
                )
                drawn_mask = gr.ImageEditor(
                    type="pil",
                    image_mode="RGBA",
                    format="png",
                    label="Draw mask",
                    brush=gr.Brush(default_size=48, colors=["#FFFFFF"], color_mode="fixed"),
                    eraser=gr.Eraser(default_size=48),
                    transforms=(),
                    sources=[],
                    height=420,
                )
            gr.Markdown(
                "For uploaded black/white masks, white means edit. For alpha masks, transparent means edit. "
                "In the drawing tool, paint the area to edit."
            )
            with gr.Row():
                normalized_mask = gr.Image(type="filepath", label="Normalized mask preview")
                mask_overlay = gr.Image(type="filepath", label="Mask overlay preview")
            prepare_session = gr.Button("Prepare session and normalize mask", variant="primary")

        with gr.Tab("3. Concepts"):
            with gr.Row():
                ideation_mode = gr.Radio(
                    choices=["stub", "openai"],
                    value="stub",
                    label="Ideation mode",
                )
                generate_concepts_button = gr.Button("Generate concepts", variant="primary")
            concept_cards = gr.HTML("No concepts generated yet.")
            concept_selector = gr.Radio(label="Select one concept", choices=[])
            selected_concept_status = gr.Markdown()

        with gr.Tab("4. Variants & Export"):
            with gr.Row():
                image_mode = gr.Radio(
                    choices=["stub", "openai-edit"],
                    value="stub",
                    label="Image edit mode",
                )
                image_quality = gr.Dropdown(
                    choices=["low", "medium", "high"],
                    value="low",
                    label="Image quality",
                )
                image_size = gr.Dropdown(
                    choices=["auto", "1024x1024", "1536x1024", "1024x1536"],
                    value="auto",
                    label="Image size",
                )
            revision_notes = gr.Textbox(
                label="Revision notes",
                placeholder="Optional: simplify the path, increase contrast, reduce vegetation...",
                lines=2,
            )
            with gr.Row():
                generate_one = gr.Button("Generate 1 variant", variant="primary")
                generate_three = gr.Button("Generate 3 variants")
                regenerate = gr.Button("Regenerate selected concept")
            output_gallery = gr.Gallery(label="Generated variants", columns=3, height=520)
            latest_prompt = gr.Markdown()
            with gr.Row():
                export_button = gr.Button("Export session")
                export_archive = gr.File(label="Export archive")
            export_status = gr.Markdown()

        with gr.Tab("5. Compile to Tile Map"):
            gr.Markdown(
                "Compile an accepted image into deterministic regions using only selected studio tiles. "
                f"**{DISCLAIMER}**"
            )
            compile_palette_swatches = gr.HTML(label="Selected compile palette")
            with gr.Row():
                compile_source = gr.Radio(
                    choices=[
                        ("Upload finalized source image", "upload"),
                        ("Use latest generated variant", "latest_variant"),
                        ("Use base canvas image", "base_canvas"),
                    ],
                    value="upload",
                    label="Compile source",
                )
                finalized_source = gr.Image(
                    type="filepath",
                    label="Finalized source image",
                    sources=["upload", "clipboard"],
                )
                compile_mask = gr.Image(
                    type="filepath",
                    image_mode="RGBA",
                    format="png",
                    label="Compile-specific mask",
                    sources=["upload", "clipboard"],
                )
            whole_image = gr.Checkbox(value=False, label="Whole image")
            gr.Markdown(
                "### Color-area compilation\n"
                "Color regions define palette areas. Their boundaries stay authoritative during shard subdivision."
            )
            with gr.Row():
                compile_granularity = gr.Radio(
                    choices=["coarse", "medium", "fine"],
                    value="medium",
                    label="Compile granularity",
                )
                max_colors = gr.Number(value=None, precision=0, label="Max colors")
                minimum_color_area = gr.Number(
                    value=None,
                    minimum=0,
                    label="Minimum color area (cm²)",
                )
                color_compactness = gr.Radio(
                    choices=[
                        ("Organic", 2.0),
                        ("Balanced", 5.0),
                        ("Regular", 12.0),
                    ],
                    value=5.0,
                    label="Color shape regularity",
                )
                boundary_smoothing = gr.Radio(
                    choices=["none", "light", "medium"],
                    value="light",
                    label="Boundary smoothing",
                )
            with gr.Row():
                merge_tiny_regions = gr.Checkbox(value=True, label="Merge tiny regions")
                strict_palette = gr.Checkbox(
                    value=True,
                    label="Strict palette",
                    interactive=False,
                )
                physical_width = gr.Number(value=None, label="Physical width (cm)")
                physical_height = gr.Number(value=None, label="Physical height (cm)")
                physical_scale_basis = gr.Radio(
                    choices=[
                        ("Masked field bounding box", "mask_bbox"),
                        ("Whole source image", "full_image"),
                    ],
                    value="mask_bbox",
                    label="Physical dimensions apply to",
                )
            min_region_area = gr.State(value=64)
            gr.Markdown(
                "### Tessera / shard subdivision\n"
                "Tesserae subdivide color regions without changing tile IDs. Outputs are planning geometry, not cut lines."
            )
            enable_tessera = gr.Checkbox(value=False, label="Enable tessera subdivision")
            with gr.Row():
                min_short_edge = gr.Number(
                    value=8,
                    minimum=0.1,
                    label="Minimum short edge (mm)",
                )
                target_short_edge = gr.Number(
                    value=18,
                    minimum=0.1,
                    label="Target short edge (mm)",
                )
                max_long_edge = gr.Number(
                    value=55,
                    minimum=0.1,
                    label="Maximum long edge (mm)",
                )
                preferred_aspect = gr.Number(
                    value=1.8,
                    minimum=1,
                    label="Preferred aspect ratio",
                )
                max_aspect = gr.Number(
                    value=4,
                    minimum=1,
                    label="Maximum aspect ratio",
                )
            with gr.Row():
                flow_strength = gr.Radio(
                    choices=["none", "low", "medium", "high"],
                    value="medium",
                    label="Flow strength",
                )
                edge_following = gr.Radio(
                    choices=["low", "medium", "high"],
                    value="medium",
                    label="Edge following",
                )
                shape_style = gr.Radio(
                    choices=["irregular", "angular", "smooth", "slivered"],
                    value="irregular",
                    label="Shape style",
                )
            with gr.Row():
                random_seed = gr.Number(value=0, precision=0, label="Random seed")
                grout_width = gr.Number(
                    value=2,
                    minimum=0,
                    label="Grout preview width (mm)",
                )
                max_tessera_count = gr.Number(
                    value=3000,
                    precision=0,
                    minimum=1,
                    label="Maximum tessera count",
                )
            with gr.Row():
                compile_button = gr.Button("Compile to Tile Map", variant="primary")
                export_compile_button = gr.Button("Export Compile Bundle")
            with gr.Row():
                palette_map_preview = gr.Image(type="filepath", label="Palette map")
                region_labels_preview = gr.Image(type="filepath", label="Numbered region map")
                boundaries_preview = gr.Image(type="filepath", label="Region boundaries")
            with gr.Row():
                tessera_map_preview = gr.Image(type="filepath", label="Tessera map")
                tessera_boundaries_preview = gr.Image(
                    type="filepath",
                    label="Tessera boundaries",
                )
            tile_legend = gr.Dataframe(
                headers=[
                    "Tile ID",
                    "Name",
                    "Hex",
                    "Pixels",
                    "% of mask",
                    "Area cm2",
                    "Regions",
                    "Mean Delta E",
                    "Max Delta E",
                ],
                interactive=False,
                wrap=True,
                label="Tile legend",
            )
            qa_warnings = gr.Markdown()
            tessera_qa = gr.Markdown(label="Tessera QA")
            with gr.Row():
                compile_report = gr.File(label="Compile report")
                compile_archive = gr.File(label="Compile bundle")
            compile_status = gr.Markdown()

        load_palette_button.click(
            _load_palette_ui,
            inputs=[palette_path],
            outputs=[palette_swatches, selected_palette_ids, session_status],
        )
        load_palette_button.click(
            _selected_palette_swatches_ui,
            inputs=[palette_path, selected_palette_ids],
            outputs=[compile_palette_swatches],
        )
        selected_palette_ids.change(
            _selected_palette_swatches_ui,
            inputs=[palette_path, selected_palette_ids],
            outputs=[compile_palette_swatches],
        )
        base_image.change(_seed_editor, inputs=[base_image], outputs=[drawn_mask])
        prepare_session.click(
            _prepare_session_ui,
            inputs=[
                palette_path,
                selected_palette_ids,
                project_name,
                location,
                intent,
                required_text,
                mood,
                must_include,
                must_avoid,
                viewing_distance,
                granularity,
                notes,
                base_image,
                site_context,
                style_references,
                composition_sketch,
                uploaded_mask,
                drawn_mask,
            ],
            outputs=[
                session_state,
                normalized_mask,
                mask_overlay,
                reference_gallery,
                session_status,
            ],
        )
        generate_concepts_button.click(
            _generate_concepts_ui,
            inputs=[session_state, ideation_mode],
            outputs=[session_state, concept_cards, concept_selector, session_status],
        )
        concept_selector.change(
            _select_concept_ui,
            inputs=[session_state, concept_selector],
            outputs=[session_state, selected_concept_status],
        )
        generate_one.click(
            lambda *args: _generate_variants_ui(*args, variant_count=1),
            inputs=[session_state, image_mode, image_quality, image_size, revision_notes],
            outputs=[session_state, output_gallery, latest_prompt, session_status],
        )
        generate_three.click(
            lambda *args: _generate_variants_ui(*args, variant_count=3),
            inputs=[session_state, image_mode, image_quality, image_size, revision_notes],
            outputs=[session_state, output_gallery, latest_prompt, session_status],
        )
        regenerate.click(
            lambda *args: _generate_variants_ui(*args, variant_count=1),
            inputs=[session_state, image_mode, image_quality, image_size, revision_notes],
            outputs=[session_state, output_gallery, latest_prompt, session_status],
        )
        export_button.click(
            _export_session_ui,
            inputs=[session_state],
            outputs=[export_archive, export_status],
        )
        compile_button.click(
            _compile_tile_map_ui,
            inputs=[
                session_state,
                palette_path,
                selected_palette_ids,
                project_name,
                location,
                intent,
                required_text,
                mood,
                must_include,
                must_avoid,
                viewing_distance,
                granularity,
                notes,
                compile_source,
                finalized_source,
                compile_mask,
                whole_image,
                compile_granularity,
                max_colors,
                min_region_area,
                boundary_smoothing,
                merge_tiny_regions,
                physical_width,
                physical_height,
                color_compactness,
                minimum_color_area,
                physical_scale_basis,
                enable_tessera,
                min_short_edge,
                target_short_edge,
                max_long_edge,
                preferred_aspect,
                max_aspect,
                flow_strength,
                edge_following,
                shape_style,
                random_seed,
                grout_width,
                max_tessera_count,
            ],
            outputs=[
                session_state,
                palette_map_preview,
                region_labels_preview,
                boundaries_preview,
                tessera_map_preview,
                tessera_boundaries_preview,
                tile_legend,
                qa_warnings,
                tessera_qa,
                compile_report,
                compile_status,
            ],
        )
        export_compile_button.click(
            _export_compile_ui,
            inputs=[session_state],
            outputs=[compile_archive, compile_status],
        )
        load_demo.click(
            _load_demo_ui,
            outputs=[
                palette_path,
                project_name,
                location,
                viewing_distance,
                granularity,
                intent,
                required_text,
                mood,
                must_include,
                must_avoid,
                notes,
                base_image,
                site_context,
                style_references,
                composition_sketch,
                uploaded_mask,
                session_status,
            ],
        )
        app.load(
            _load_palette_ui,
            inputs=[palette_path],
            outputs=[palette_swatches, selected_palette_ids, session_status],
        )

    return app


def _load_palette_ui(palette_path: str):
    try:
        palette = load_palette(palette_path)
    except Exception as error:
        return "", gr.update(choices=[], value=[]), f"Palette error: {error}"
    swatches = "".join(
        (
            "<span style='display:inline-block;margin:4px;padding:6px;border:1px solid #bbb'>"
            f"<span style='display:inline-block;width:24px;height:24px;background:{html.escape(tile.hex)};"
            "vertical-align:middle;margin-right:6px'></span>"
            f"{html.escape(tile.name)} <code>{html.escape(tile.tile_id)}</code></span>"
        )
        for tile in palette.tiles
    )
    ids = [tile.tile_id for tile in palette.tiles]
    return swatches, gr.update(choices=ids, value=ids), f"Loaded {len(ids)} palette colors."


def _selected_palette_swatches_ui(palette_path: str, selected_ids: list[str] | None) -> str:
    try:
        palette = load_palette(palette_path)
    except Exception:
        return ""
    selected = set(selected_ids or [])
    tiles = [tile for tile in palette.tiles if tile.tile_id in selected]
    if not tiles:
        return "<p>No palette colors selected.</p>"
    return "".join(
        (
            "<span style='display:inline-flex;align-items:center;gap:6px;margin:3px 6px 3px 0;"
            "padding:4px 6px;border:1px solid #bbb'>"
            f"<span style='width:20px;height:20px;background:{html.escape(tile.hex)};"
            "display:inline-block'></span>"
            f"<code>{html.escape(tile.tile_id)}</code></span>"
        )
        for tile in tiles
    )


def _seed_editor(base_image_path: str | None):
    if not base_image_path:
        return None
    with Image.open(base_image_path) as image:
        background = image.convert("RGBA")
    return {"background": background, "layers": [], "composite": background.copy()}


def _prepare_session_ui(
    palette_path: str,
    selected_ids: list[str],
    project_name: str,
    location: str,
    intent: str,
    required_text: str,
    mood: str,
    must_include: str,
    must_avoid: str,
    viewing_distance: float | None,
    granularity: str,
    notes: str,
    base_image_path: str | None,
    site_context_path: str | None,
    style_reference_paths: list[str] | str | None,
    composition_sketch_path: str | None,
    uploaded_mask_path: str | None,
    editor_value,
):
    try:
        if not base_image_path:
            raise ValueError("upload a base canvas image")
        mask_path = Path(uploaded_mask_path) if uploaded_mask_path else _save_editor_mask(editor_value, base_image_path)
        brief = _brief_from_form(
            project_name=project_name,
            location=location,
            intent=intent,
            required_text=required_text,
            mood=mood,
            must_include=must_include,
            must_avoid=must_avoid,
            viewing_distance=viewing_distance,
            granularity=granularity,
            notes=notes,
        )
        references = []
        if site_context_path:
            references.append((site_context_path, "site_context"))
        style_paths = [style_reference_paths] if isinstance(style_reference_paths, str) else style_reference_paths or []
        references.extend((path, "artist_style_reference") for path in style_paths[:5])
        if composition_sketch_path:
            references.append((composition_sketch_path, "composition_sketch"))
        session = create_session(
            brief=brief,
            palette_db_path=palette_path,
            base_image_path=base_image_path,
            mask_image_path=mask_path,
            reference_inputs=references,
        )
        if selected_ids:
            session = session.model_copy(update={"selected_palette_ids": selected_ids})
        assert session.edit_target is not None
        return (
            session.model_dump(mode="json"),
            session.edit_target.mask_image_path,
            session.edit_target.overlay_preview_path,
            [asset.path for asset in session.reference_assets],
            f"Session {session.session_id} is ready.",
        )
    except Exception as error:
        raise gr.Error(str(error)) from error


def _generate_concepts_ui(state: dict | None, ideation_mode: str):
    try:
        session = _session_from_state(state)
        session = generate_concepts(session, ideation_mode=ideation_mode)
        choices = [(concept.name, concept.concept_id) for concept in session.concepts]
        return (
            session.model_dump(mode="json"),
            _render_concepts(session),
            gr.update(choices=choices, value=None),
            f"Generated {len(session.concepts)} concept directions.",
        )
    except Exception as error:
        raise gr.Error(str(error)) from error


def _select_concept_ui(state: dict | None, concept_id: str | None):
    try:
        if not concept_id:
            return state, "Select a concept to continue."
        session = select_session_concept(_session_from_state(state), concept_id)
        concept = next(item for item in session.concepts if item.concept_id == concept_id)
        return session.model_dump(mode="json"), f"Selected **{concept.name}**."
    except Exception as error:
        raise gr.Error(str(error)) from error


def _generate_variants_ui(
    state: dict | None,
    image_mode: str,
    quality: str,
    size: str,
    revision_notes: str,
    *,
    variant_count: int,
):
    try:
        session = generate_variants(
            _session_from_state(state),
            image_mode=image_mode,
            variant_count=variant_count,
            quality=quality,
            size=size,
            revision_notes=revision_notes,
        )
        latest = session.generation_runs[-1]
        return (
            session.model_dump(mode="json"),
            latest.image_paths,
            f"### Edit prompt\n\n{latest.prompt}",
            f"Generated {len(latest.image_paths)} variant(s) with {latest.provider}.",
        )
    except Exception as error:
        raise gr.Error(str(error)) from error


def _export_session_ui(state: dict | None):
    try:
        session = _session_from_state(state)
        export_dir = ROOT / "runs" / "workbench_exports" / session.session_id
        export_session(session, export_dir)
        archive_base = export_dir.parent / session.session_id
        archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=export_dir)
        return archive_path, f"Exported session to `{export_dir}`."
    except Exception as error:
        raise gr.Error(str(error)) from error


def _compile_tile_map_ui(
    state: dict | None,
    palette_path: str,
    selected_ids: list[str],
    project_name: str,
    location: str,
    intent: str,
    required_text: str,
    mood: str,
    must_include: str,
    must_avoid: str,
    viewing_distance: float | None,
    brief_granularity: str,
    notes: str,
    source_choice: str,
    finalized_source_path: str | None,
    compile_mask_path: str | None,
    whole_image: bool,
    compile_granularity: str,
    max_colors: float | int | None,
    min_region_area_px: float | int,
    boundary_smoothing: str,
    merge_tiny_regions: bool,
    physical_width_cm: float | None,
    physical_height_cm: float | None,
    color_compactness: float = 5.0,
    minimum_color_area_cm2: float | None = None,
    physical_scale_basis: str = "mask_bbox",
    enable_tessera: bool = False,
    min_short_edge_mm: float = 8.0,
    target_short_edge_mm: float = 18.0,
    max_long_edge_mm: float = 55.0,
    preferred_aspect_ratio: float = 1.8,
    max_aspect_ratio: float = 4.0,
    flow_strength: str = "medium",
    edge_following: str = "medium",
    shape_style: str = "irregular",
    random_seed: float | int = 0,
    grout_width_mm: float = 2.0,
    max_tessera_count: float | int = 3000,
):
    try:
        if not selected_ids:
            raise ValueError("Select at least one palette color before compiling.")
        if state:
            session = InteractiveSession.model_validate(state).model_copy(
                update={
                    "palette_db_path": palette_path,
                    "selected_palette_ids": selected_ids,
                }
            )
        else:
            brief = _brief_from_form(
                project_name=project_name,
                location=location,
                intent=intent,
                required_text=required_text,
                mood=mood,
                must_include=must_include,
                must_avoid=must_avoid,
                viewing_distance=viewing_distance,
                granularity=brief_granularity,
                notes=notes,
            )
            session = InteractiveSession(
                session_id=uuid4().hex[:12],
                brief=brief,
                palette_db_path=palette_path,
                selected_palette_ids=selected_ids,
            )
        normalized_max_colors = int(max_colors) if max_colors not in (None, 0) else None
        normalized_width = (
            float(physical_width_cm) if physical_width_cm not in (None, 0) else None
        )
        normalized_height = (
            float(physical_height_cm) if physical_height_cm not in (None, 0) else None
        )
        normalized_minimum_color_area = (
            float(minimum_color_area_cm2)
            if minimum_color_area_cm2 not in (None, 0)
            else None
        )
        session = compile_session_tile_map(
            session,
            source_choice=source_choice,
            uploaded_source_path=finalized_source_path,
            compile_mask_path=compile_mask_path,
            whole_image=whole_image,
            max_colors=normalized_max_colors,
            granularity=compile_granularity,
            min_region_area_px=int(min_region_area_px),
            boundary_smoothing=boundary_smoothing,
            merge_tiny_regions=merge_tiny_regions,
            physical_width_cm=normalized_width,
            physical_height_cm=normalized_height,
            color_compactness=float(color_compactness),
            minimum_color_area_cm2=normalized_minimum_color_area,
            physical_scale_basis=physical_scale_basis,
            enable_tessera=enable_tessera,
            min_short_edge_mm=float(min_short_edge_mm),
            target_short_edge_mm=float(target_short_edge_mm),
            max_long_edge_mm=float(max_long_edge_mm),
            preferred_aspect_ratio=float(preferred_aspect_ratio),
            max_aspect_ratio=float(max_aspect_ratio),
            flow_strength=flow_strength,
            edge_following=edge_following,
            shape_style=shape_style,
            random_seed=int(random_seed),
            grout_width_mm=float(grout_width_mm),
            max_tessera_count=int(max_tessera_count),
            out_root=ROOT / "runs" / "workbench",
        )
        result = session.latest_compile_result
        assert result is not None
        legend = [
            [
                item.tile_id,
                item.tile_name,
                item.hex,
                item.pixel_count,
                round(item.percent_of_mask, 2),
                None
                if item.estimated_area_cm2 is None
                else round(item.estimated_area_cm2, 2),
                item.region_count,
                round(item.mean_delta_e, 2),
                round(item.max_delta_e, 2),
            ]
            for item in result.color_usage
        ]
        warning_lines = [f"**{DISCLAIMER}**", "", "### QA warnings", ""]
        warning_lines.extend(
            f"- {warning}" for warning in result.warnings
        )
        if not result.warnings:
            warning_lines.append("- No QA warnings.")
        tessera = result.tessera_result
        tessera_qa_lines: list[str] = []
        if tessera is not None:
            tessera_qa_lines = [
                "### Tessera QA",
                "",
                f"- Pieces: {tessera.tessera_count}",
                f"- Mean area: {tessera.mean_area_mm2:.2f} mm²",
                f"- Mean aspect ratio: {tessera.mean_aspect_ratio:.2f}",
                f"- Signature: `{tessera.deterministic_signature[:12]}`",
            ]
            tessera_qa_lines.extend(f"- {warning}" for warning in tessera.warnings[:10])
        status = (
            f"Compiled {result.region_count} regions using {result.color_count} studio colors. "
            f"Signature `{result.run_id}`."
        )
        if tessera is not None:
            status += f" Subdivided into {tessera.tessera_count} tesserae."
        return (
            session.model_dump(mode="json"),
            result.palette_map_path,
            result.region_labels_path,
            result.region_boundaries_path,
            tessera.tessera_map_path if tessera is not None else None,
            tessera.tessera_boundaries_path if tessera is not None else None,
            legend,
            "\n".join(warning_lines),
            "\n".join(tessera_qa_lines),
            result.compile_report_html_path,
            status,
        )
    except Exception as error:
        raise gr.Error(str(error)) from error


def _export_compile_ui(state: dict | None):
    try:
        session = _session_from_state(state)
        if session.latest_compile_result is None:
            raise ValueError("Compile a tile map before exporting the compile bundle.")
        export_dir = ROOT / "runs" / "workbench_exports" / session.session_id
        archive_path = export_compile_archive(
            session.latest_compile_result,
            export_dir / f"compile_{len(session.compile_runs):02d}.zip",
        )
        return str(archive_path), f"Exported compile bundle to `{archive_path}`."
    except Exception as error:
        raise gr.Error(str(error)) from error


def _session_from_state(state: dict | None) -> InteractiveSession:
    if not state:
        raise ValueError("prepare the session and mask first")
    return InteractiveSession.model_validate(state)


def _brief_from_form(
    *,
    project_name: str,
    location: str,
    intent: str,
    required_text: str,
    mood: str,
    must_include: str,
    must_avoid: str,
    viewing_distance: float | None,
    granularity: str,
    notes: str,
) -> ProjectBrief:
    return ProjectBrief(
        project_name=project_name.strip() or "Untitled mosaic",
        location=location.strip() or "Unconfirmed site",
        intent=intent.strip() or "Explore a public broken-tile mosaic direction.",
        required_text=_split_values(required_text),
        desired_mood=_split_values(mood),
        must_include=_split_values(must_include),
        must_avoid=_split_values(must_avoid),
        viewing_distance_m=viewing_distance,
        granularity=granularity,
        canvas=Canvas(type="uploaded base image"),
        desired_outputs=["questions", "concepts", "image_prompts", "image_renders", "critique"],
        notes=notes.strip(),
    )


def _split_values(value: str) -> list[str]:
    return [item.strip() for line in value.splitlines() for item in line.split(",") if item.strip()]


def _save_editor_mask(editor_value, base_image_path: str) -> Path:
    output_dir = ROOT / "runs" / "workbench" / "_drawn_masks"
    output_path = output_dir / f"{uuid4().hex}.png"
    return save_drawn_mask(base_image_path, editor_value, output_path)


def _render_concepts(session: InteractiveSession) -> str:
    sections = []
    for concept in session.concepts:
        tile_ids = " ".join(
            f"<code style='margin-right:6px'>{html.escape(tile_id)}</code>"
            for tile_id in concept.palette_tile_ids
        )
        risks = "; ".join(html.escape(risk) for risk in concept.critique.risks)
        sections.append(
            "<section style='padding:10px 0;border-bottom:1px solid #ccc'>"
            f"<h3>{html.escape(concept.name)}</h3>"
            f"<p><strong>Thesis:</strong> {html.escape(concept.intent)}</p>"
            f"<p><strong>Palette:</strong> {tile_ids}</p>"
            "<details><summary>Details</summary>"
            f"<p><strong>Composition:</strong> {html.escape(concept.composition)}</p>"
            f"<p><strong>Risks:</strong> {risks}</p>"
            "</details></section>"
        )
    return "".join(sections)


def _demo_defaults() -> dict[str, object]:
    if not DEMO_PRESET.exists():
        return {}
    data = load_brief(DEMO_PRESET)
    return {
        "palette_db_path": str(DEFAULT_PALETTE),
        "project_name": data.project_name,
        "location": data.location,
        "viewing_distance_m": data.viewing_distance_m,
        "granularity": data.granularity,
        "intent": data.intent,
        "required_text": "\n".join(data.required_text),
        "mood": ", ".join(data.desired_mood),
        "must_include": "\n".join(data.must_include),
        "must_avoid": "\n".join(data.must_avoid),
        "notes": data.notes,
    }


def _load_demo_ui():
    if not DEMO_PRESET.exists():
        raise gr.Error("demo preset has not been generated")
    brief = load_brief(DEMO_PRESET)
    demo_dir = DEMO_PRESET.parent
    return (
        str(DEFAULT_PALETTE),
        brief.project_name,
        brief.location,
        brief.viewing_distance_m,
        brief.granularity,
        brief.intent,
        "\n".join(brief.required_text),
        ", ".join(brief.desired_mood),
        "\n".join(brief.must_include),
        "\n".join(brief.must_avoid),
        brief.notes,
        str(demo_dir / "base_canvas.png"),
        str(demo_dir / "site_context.png"),
        [str(demo_dir / "style_reference.png")],
        str(demo_dir / "composition_sketch.png"),
        str(demo_dir / "sample_mask.png"),
        'Demo inputs loaded. Click "Prepare session and normalize mask".',
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the local mosaic ideation workbench.")
    parser.add_argument("--demo", action="store_true", help="Prefill the bundled demo session.")
    parser.add_argument("--server-name", default="127.0.0.1")
    parser.add_argument("--server-port", type=int, default=7860)
    parser.add_argument("--share", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    app = build_app(demo=args.demo)
    app.launch(server_name=args.server_name, server_port=args.server_port, share=args.share)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
