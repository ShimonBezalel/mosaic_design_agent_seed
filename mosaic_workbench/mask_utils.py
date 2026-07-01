from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageOps


def normalize_base_image(source_path: str | Path, output_path: str | Path) -> Path:
    source = Path(source_path)
    destination = Path(output_path)
    with Image.open(source) as image:
        normalized = image.convert("RGB")
        destination.parent.mkdir(parents=True, exist_ok=True)
        normalized.save(destination, format="PNG")
    return destination


def save_drawn_mask(
    base_image_path: str | Path,
    editor_value: object,
    output_path: str | Path,
) -> Path:
    if not isinstance(editor_value, dict) or not editor_value.get("layers"):
        raise ValueError("draw at least one mask stroke or upload a mask PNG")
    with Image.open(base_image_path) as base:
        selection = Image.new("L", base.size, 0)

    for layer_value in editor_value["layers"]:
        if isinstance(layer_value, Image.Image):
            layer = layer_value.convert("RGBA")
        else:
            with Image.open(layer_value) as layer_source:
                layer = layer_source.convert("RGBA")
        layer = layer.resize(selection.size, Image.Resampling.NEAREST)
        selection = ImageChops.lighter(selection, layer.getchannel("A"))

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    selection.save(destination, format="PNG")
    return destination


def normalize_mask(
    base_image_path: str | Path,
    mask_image_path: str | Path,
    output_path: str | Path,
) -> Path:
    base_path = Path(base_image_path)
    source_path = Path(mask_image_path)
    destination = Path(output_path)

    with Image.open(base_path) as base:
        target_size = base.size

    with Image.open(source_path) as source:
        source.load()
        has_meaningful_alpha = "A" in source.getbands() and source.getchannel("A").getextrema() != (255, 255)
        resized = source.resize(target_size, Image.Resampling.NEAREST)
        if has_meaningful_alpha:
            alpha = resized.getchannel("A")
        else:
            alpha = ImageOps.invert(resized.convert("L"))

    normalized = Image.new("RGBA", target_size, (0, 0, 0, 255))
    normalized.putalpha(alpha)
    destination.parent.mkdir(parents=True, exist_ok=True)
    normalized.save(destination, format="PNG")
    return destination


def create_mask_overlay(
    base_image_path: str | Path,
    normalized_mask_path: str | Path,
    output_path: str | Path,
) -> Path:
    destination = Path(output_path)
    with Image.open(base_image_path) as base_source:
        base = base_source.convert("RGBA")
    with Image.open(normalized_mask_path) as mask_source:
        mask = mask_source.convert("RGBA")

    if base.size != mask.size:
        raise ValueError("base image and normalized mask must have the same dimensions")

    editable = ImageOps.invert(mask.getchannel("A"))
    overlay_alpha = editable.point(lambda value: round(value * 0.45))
    overlay = Image.new("RGBA", base.size, (220, 40, 40, 0))
    overlay.putalpha(overlay_alpha)
    preview = Image.alpha_composite(base, overlay)

    destination.parent.mkdir(parents=True, exist_ok=True)
    preview.save(destination, format="PNG")
    return destination
