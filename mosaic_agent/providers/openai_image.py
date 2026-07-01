from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from mosaic_agent.models import ImageGenerationRequest, ImageGenerationResult
from mosaic_agent.providers.base import ProviderConfigurationError, ProviderRuntimeError


class OpenAIImageProvider:
    provider_name = "openai-image"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ProviderConfigurationError("OPENAI_API_KEY is required for --mode openai-image.")
        self.model = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1.5")
        self.size = os.environ.get("OPENAI_IMAGE_SIZE", "1024x1024")
        self.quality = os.environ.get("OPENAI_IMAGE_QUALITY", "low")

    def generate(self, request: ImageGenerationRequest, output_path: Path) -> ImageGenerationResult:
        payload = {
            "model": self.model,
            "prompt": request.prompt,
            "n": 1,
            "size": self.size,
            "quality": self.quality,
            "output_format": "png",
        }
        http_request = urllib.request.Request(
            "https://api.openai.com/v1/images/generations",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(http_request, timeout=180) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            raise ProviderRuntimeError(f"OpenAI image generation failed: {details}") from None
        except urllib.error.URLError as error:
            raise ProviderRuntimeError(f"OpenAI image generation failed: {error.reason}") from None

        image_data = body.get("data", [{}])[0]
        b64_image = image_data.get("b64_json")
        if not b64_image:
            raise ProviderRuntimeError("OpenAI image generation response did not include b64_json image data.")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(base64.b64decode(b64_image))
        return ImageGenerationResult(
            provider=self.provider_name,
            concept_id=request.concept_id,
            variant_id=request.variant_id,
            status="generated",
            image_path=str(output_path),
            metadata={
                "model": self.model,
                "size": self.size,
                "quality": self.quality,
                "revised_prompt": image_data.get("revised_prompt", ""),
                "usage": body.get("usage", {}),
            },
        )
