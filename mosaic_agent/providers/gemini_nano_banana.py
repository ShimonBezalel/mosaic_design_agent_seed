from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from mosaic_agent.models import ImageGenerationRequest, ImageGenerationResult
from mosaic_agent.providers.base import ProviderConfigurationError, ProviderRuntimeError


class GeminiNanoBananaProvider:
    provider_name = "gemini-image"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise ProviderConfigurationError(
                "GEMINI_API_KEY or GOOGLE_API_KEY is required for --image-mode gemini-image."
            )
        self.model = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image-preview")

    def generate(self, request: ImageGenerationRequest, output_path: Path) -> ImageGenerationResult:
        payload = {
            "model": self.model,
            "input": request.prompt,
            "response_format": {
                "type": "image",
                "aspect_ratio": "1:1",
            },
        }
        http_request = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(http_request, timeout=240) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            raise ProviderRuntimeError(f"Gemini image generation failed: {details}") from None
        except urllib.error.URLError as error:
            raise ProviderRuntimeError(f"Gemini image generation failed: {error.reason}") from None

        b64_image = _extract_base64_image(body)
        if not b64_image:
            raise ProviderRuntimeError("Gemini image generation response did not include image data.")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(base64.b64decode(b64_image))
        return ImageGenerationResult(
            provider=self.provider_name,
            concept_id=request.concept_id,
            variant_id=request.variant_id,
            status="generated",
            image_path=str(output_path),
            metadata={"model": self.model},
        )


def _extract_base64_image(value: Any) -> str | None:
    if isinstance(value, dict):
        output_image = value.get("output_image") or value.get("outputImage")
        if isinstance(output_image, dict) and isinstance(output_image.get("data"), str):
            return output_image["data"]

        inline_data = value.get("inlineData") or value.get("inline_data")
        if isinstance(inline_data, dict) and str(inline_data.get("mimeType", "")).startswith("image/"):
            data = inline_data.get("data")
            if isinstance(data, str):
                return data

        if value.get("mime_type", "").startswith("image/") and isinstance(value.get("data"), str):
            return value["data"]

        for child in value.values():
            found = _extract_base64_image(child)
            if found:
                return found

    if isinstance(value, list):
        for child in value:
            found = _extract_base64_image(child)
            if found:
                return found

    return None
