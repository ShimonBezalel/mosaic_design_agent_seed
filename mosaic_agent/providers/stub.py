from __future__ import annotations

import re
import struct
import zlib
from pathlib import Path

from mosaic_agent.models import ImageGenerationRequest, ImageGenerationResult


class StubImageProvider:
    provider_name = "stub"

    def generate(self, request: ImageGenerationRequest, output_path: Path) -> ImageGenerationResult:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        colors = _extract_prompt_colors(request.prompt)
        _write_placeholder_png(output_path, colors, request.concept_id, request.variant_id)
        return ImageGenerationResult(
            provider=self.provider_name,
            concept_id=request.concept_id,
            variant_id=request.variant_id,
            status="stubbed",
            image_path=str(output_path),
            metadata={
                "prompt_length": len(request.prompt),
                "negative_prompt_length": len(request.negative_prompt),
                "external_api_called": False,
            },
        )


def _extract_prompt_colors(prompt: str) -> list[tuple[int, int, int]]:
    hex_values = re.findall(r"#[0-9A-Fa-f]{6}", prompt)
    if not hex_values:
        hex_values = ["#C95A2A", "#D6B48F", "#E9D7B6", "#3B2016"]
    colors: list[tuple[int, int, int]] = []
    for value in hex_values[:10]:
        colors.append((int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)))
    return colors


def _write_placeholder_png(
    path: Path,
    colors: list[tuple[int, int, int]],
    concept_id: str,
    variant_id: str,
    width: int = 640,
    height: int = 420,
) -> None:
    shift = sum(ord(char) for char in concept_id + variant_id) % len(colors)
    grout = (226, 219, 204)
    dark_grout = (78, 65, 55)
    rows = bytearray()

    for y in range(height):
        rows.append(0)
        for x in range(width):
            band = ((x * len(colors)) // width + shift) % len(colors)
            color = colors[band]

            if "concept_02" in concept_id:
                curve_center = int(width * (0.2 + 0.55 * y / height))
                if abs(x - curve_center) < 42:
                    color = colors[(shift + 2) % len(colors)]
            elif "concept_03" in concept_id:
                ribbon_y = int(height * 0.48 + 38 * ((x / width) - 0.5))
                if abs(y - ribbon_y) < 46:
                    color = colors[(shift + 1) % len(colors)]
            else:
                arc = (x - width // 2) ** 2 + (y - int(height * 0.72)) ** 2
                if 22000 < arc < 43000 and y < height * 0.76:
                    color = colors[(shift + 3) % len(colors)]

            if (x + y + shift) % 37 == 0 or x % 53 == 0 or y % 47 == 0:
                color = grout
            if x < 8 or y < 8 or x >= width - 8 or y >= height - 8:
                color = dark_grout

            rows.extend(color)

    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum)

    png = bytearray()
    png.extend(b"\x89PNG\r\n\x1a\n")
    png.extend(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)))
    png.extend(chunk(b"IDAT", zlib.compress(bytes(rows), level=9)))
    png.extend(chunk(b"IEND", b""))
    path.write_bytes(bytes(png))
