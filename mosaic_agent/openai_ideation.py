from __future__ import annotations

import base64
import json
import mimetypes
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from mosaic_agent.critique import build_stub_critique
from mosaic_agent.models import Concept, ImagePrompts, PaletteDB, ProjectBrief
from mosaic_agent.palette import validate_tile_ids
from mosaic_agent.providers.base import ProviderConfigurationError, ProviderRuntimeError
from mosaic_agent.reference_images import ensure_reference_images_exist


def generate_openai_concepts(*, brief: ProjectBrief, palette: PaletteDB, concept_limit: int) -> list[Concept]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ProviderConfigurationError("OPENAI_API_KEY is required for --ideation-mode openai.")

    model = os.environ.get("OPENAI_IDEATION_MODEL", "gpt-5.5")
    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": _build_content(brief, palette, concept_limit),
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "mosaic_concept_directions",
                "strict": True,
                "schema": _concept_response_schema(),
            }
        },
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise ProviderRuntimeError(f"OpenAI ideation failed: {details}") from None
    except urllib.error.URLError as error:
        raise ProviderRuntimeError(f"OpenAI ideation failed: {error.reason}") from None

    raw_text = body.get("output_text") or _extract_output_text(body)
    if not raw_text:
        raise ProviderRuntimeError("OpenAI ideation response did not include structured text output.")
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise ProviderRuntimeError(f"OpenAI ideation returned invalid JSON: {error}") from None

    concepts: list[Concept] = []
    for index, item in enumerate(parsed.get("concepts", []), start=1):
        tile_ids = item["palette_tile_ids"]
        validate_tile_ids(tile_ids, palette)
        name = item["name"]
        concepts.append(
            Concept(
                concept_id=item.get("concept_id") or f"openai_concept_{index:02d}",
                name=name,
                intent=item["intent"],
                composition=item["composition"],
                locked_elements=item.get("locked_elements", []),
                flexible_elements=item.get("flexible_elements", []),
                mosaic_grammar=item.get("mosaic_grammar", ""),
                palette_tile_ids=tile_ids,
                image_prompts=ImagePrompts(),
                critique=build_stub_critique(name, brief),
            )
        )
    if not concepts:
        raise ProviderRuntimeError("OpenAI ideation returned no concepts.")
    return concepts[:concept_limit]


def _build_content(brief: ProjectBrief, palette: PaletteDB, concept_limit: int) -> list[dict[str, Any]]:
    ensure_reference_images_exist(brief.reference_image_paths)
    palette_text = "\n".join(
        f"- {tile.tile_id}: {tile.name} {tile.hex}, inventory {tile.inventory_level}, uses {', '.join(tile.preferred_uses)}"
        for tile in palette.tiles
    )
    reference_summary = "\n".join(
        f"- {role}: {path}" for path, role in zip(brief.reference_image_paths, brief.reference_image_roles)
    ) or "- none"
    prompt = f"""
You are a disciplined mosaic studio assistant. Generate {concept_limit} distinct concept directions for a public broken-tile mosaic.

Brief:
project_name: {brief.project_name}
location: {brief.location}
intent: {brief.intent}
required_text: {brief.required_text}
desired_mood: {brief.desired_mood}
must_include: {brief.must_include}
must_avoid: {brief.must_avoid}
viewing_distance_m: {brief.viewing_distance_m}
granularity: {brief.granularity}
canvas: {brief.canvas.model_dump()}
reference_images:
{reference_summary}

Palette DB:
{palette_text}

Rules:
- Use only tile IDs from the palette DB.
- Select 8 to 14 palette_tile_ids per concept.
- Do not ask an image model to render final Hebrew lettering; reserve a readable lettering field instead.
- Make concepts materially different.
- Return only schema-valid JSON.
""".strip()
    content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
    for path in brief.reference_image_paths:
        content.append({"type": "input_image", "image_url": _image_data_url(path)})
    return content


def _image_data_url(path: str) -> str:
    file_path = Path(path)
    mime_type = mimetypes.guess_type(file_path.name)[0] or "image/png"
    return f"data:{mime_type};base64,{base64.b64encode(file_path.read_bytes()).decode('ascii')}"


def _concept_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["concepts"],
        "properties": {
            "concepts": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "concept_id",
                        "name",
                        "intent",
                        "composition",
                        "locked_elements",
                        "flexible_elements",
                        "mosaic_grammar",
                        "palette_tile_ids",
                    ],
                    "properties": {
                        "concept_id": {"type": "string"},
                        "name": {"type": "string"},
                        "intent": {"type": "string"},
                        "composition": {"type": "string"},
                        "locked_elements": {"type": "array", "items": {"type": "string"}},
                        "flexible_elements": {"type": "array", "items": {"type": "string"}},
                        "mosaic_grammar": {"type": "string"},
                        "palette_tile_ids": {
                            "type": "array",
                            "minItems": 8,
                            "maxItems": 14,
                            "items": {"type": "string"},
                        },
                    },
                },
            }
        },
    }


def _extract_output_text(body: dict[str, Any]) -> str:
    chunks: list[str] = []
    for output in body.get("output", []):
        for content in output.get("content", []):
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    return "".join(chunks)
