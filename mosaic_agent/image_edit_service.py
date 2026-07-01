from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageDraw, ImageOps
from pydantic import Field, model_validator

from mosaic_agent.models import StrictModel
from mosaic_agent.reference_images import ensure_reference_images_exist


class ImageEditRequest(StrictModel):
    provider: str
    concept_id: str
    prompt: str
    base_image_path: str
    mask_image_path: str
    reference_image_paths: list[str] = Field(default_factory=list)
    variant_count: int = Field(default=1, ge=1, le=3)
    quality: str = "low"
    size: str = "auto"

    @model_validator(mode="after")
    def validate_assets(self) -> "ImageEditRequest":
        ensure_reference_images_exist(
            [self.base_image_path, self.mask_image_path, *self.reference_image_paths]
        )
        with Image.open(self.base_image_path) as base, Image.open(self.mask_image_path) as mask:
            if base.size != mask.size:
                raise ValueError("base image and mask must have the same dimensions")
            if mask.format != "PNG" or "A" not in mask.getbands():
                raise ValueError("mask must be a PNG with an alpha channel")
        return self


class ImageEditProvider(Protocol):
    provider_name: str

    def edit(self, request: ImageEditRequest, output_dir: Path) -> list[Path]:
        """Edit the masked region and return generated image paths."""


class StubImageEditProvider:
    provider_name = "stub"

    def edit(self, request: ImageEditRequest, output_dir: Path) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        colors = _prompt_colors(request.prompt)
        with Image.open(request.base_image_path) as base_source:
            base = base_source.convert("RGB")
        with Image.open(request.mask_image_path) as mask_source:
            editable = ImageOps.invert(mask_source.convert("RGBA").getchannel("A"))

        outputs: list[Path] = []
        for variant_index in range(1, request.variant_count + 1):
            pattern = _build_pattern(base.size, colors, variant_index)
            edited = Image.composite(pattern, base, editable)
            output_path = output_dir / f"variant_{variant_index:02d}.png"
            edited.save(output_path, format="PNG")
            outputs.append(output_path)
        return outputs


def _prompt_colors(prompt: str) -> list[str]:
    colors = re.findall(r"#[0-9A-Fa-f]{6}", prompt)
    return colors or ["#C95A2A", "#D6B48F", "#E9D7B6", "#3B2016"]


def _build_pattern(size: tuple[int, int], colors: list[str], variant_index: int) -> Image.Image:
    width, height = size
    pattern = Image.new("RGB", size, colors[0])
    draw = ImageDraw.Draw(pattern)
    band_width = max(8, width // max(len(colors), 1))
    for band in range(0, width, band_width):
        color_index = (band // band_width + variant_index - 1) % len(colors)
        draw.rectangle((band, 0, min(width, band + band_width), height), fill=colors[color_index])
    grout = max(2, min(width, height) // 48)
    for x in range(0, width, max(18, band_width)):
        draw.line((x, 0, x, height), fill="#D8D0C2", width=grout)
    for y in range(0, height, max(18, height // 6)):
        draw.line((0, y, width, y), fill="#D8D0C2", width=grout)
    return pattern
