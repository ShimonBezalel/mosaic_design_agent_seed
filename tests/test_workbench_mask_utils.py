from pathlib import Path

from PIL import Image, ImageDraw

from mosaic_workbench.mask_utils import create_mask_overlay, normalize_mask, save_drawn_mask


def _save_base(path: Path, size: tuple[int, int] = (120, 80)) -> None:
    Image.new("RGB", size, "#d8c6a8").save(path)


def test_normalize_black_white_mask_resizes_and_adds_edit_alpha(tmp_path):
    base_path = tmp_path / "base.jpg"
    mask_path = tmp_path / "mask.png"
    output_path = tmp_path / "normalized_mask.png"
    _save_base(base_path)

    mask = Image.new("L", (60, 40), 0)
    ImageDraw.Draw(mask).rectangle((15, 10, 45, 30), fill=255)
    mask.save(mask_path)

    result = normalize_mask(base_path, mask_path, output_path)

    assert result == output_path
    with Image.open(result) as normalized:
        assert normalized.format == "PNG"
        assert normalized.mode == "RGBA"
        assert normalized.size == (120, 80)
        assert normalized.getpixel((60, 40))[3] == 0
        assert normalized.getpixel((5, 5))[3] == 255


def test_normalize_uploaded_alpha_mask_preserves_transparent_edit_region(tmp_path):
    base_path = tmp_path / "base.png"
    mask_path = tmp_path / "alpha_mask.png"
    output_path = tmp_path / "normalized_mask.png"
    _save_base(base_path, (64, 64))

    mask = Image.new("RGBA", (64, 64), (0, 0, 0, 255))
    ImageDraw.Draw(mask).rectangle((20, 20, 44, 44), fill=(0, 0, 0, 0))
    mask.save(mask_path)

    normalize_mask(base_path, mask_path, output_path)

    with Image.open(output_path) as normalized:
        assert normalized.getpixel((32, 32))[3] == 0
        assert normalized.getpixel((5, 5))[3] == 255


def test_create_mask_overlay_marks_only_editable_region(tmp_path):
    base_path = tmp_path / "base.png"
    mask_path = tmp_path / "mask.png"
    overlay_path = tmp_path / "overlay.png"
    _save_base(base_path, (40, 40))

    mask = Image.new("RGBA", (40, 40), (0, 0, 0, 255))
    ImageDraw.Draw(mask).rectangle((10, 10, 30, 30), fill=(0, 0, 0, 0))
    mask.save(mask_path)

    result = create_mask_overlay(base_path, mask_path, overlay_path)

    assert result == overlay_path
    with Image.open(result) as overlay:
        center = overlay.convert("RGB").getpixel((20, 20))
        corner = overlay.convert("RGB").getpixel((2, 2))
        assert center[0] > center[1]
        assert corner == (216, 198, 168)


def test_save_drawn_mask_combines_editor_layers_as_white_edit_selection(tmp_path):
    base_path = tmp_path / "base.png"
    drawn_path = tmp_path / "drawn_mask.png"
    normalized_path = tmp_path / "normalized.png"
    _save_base(base_path, (80, 60))
    layer = Image.new("RGBA", (80, 60), (255, 255, 255, 0))
    ImageDraw.Draw(layer).rectangle((20, 15, 60, 45), fill=(255, 255, 255, 255))

    save_drawn_mask(base_path, {"layers": [layer]}, drawn_path)
    normalize_mask(base_path, drawn_path, normalized_path)

    with Image.open(normalized_path) as normalized:
        assert normalized.getpixel((40, 30))[3] == 0
        assert normalized.getpixel((5, 5))[3] == 255
