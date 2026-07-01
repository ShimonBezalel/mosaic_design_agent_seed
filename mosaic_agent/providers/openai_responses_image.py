from __future__ import annotations

import base64
import json
import mimetypes
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from mosaic_agent.models import ImageGenerationRequest, ImageGenerationResult
from mosaic_agent.providers.base import ProviderConfigurationError, ProviderRuntimeError


class OpenAIResponsesImageProvider:
    provider_name = "openai-responses-image"

    def __init__(
        self,
        api_key: str | None = None,
        image_model: str | None = None,
        image_size: str = "1536x1024",
        image_quality: str = "low",
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ProviderConfigurationError("OPENAI_API_KEY is required for --image-mode openai-responses-image.")
        self.model = image_model or os.environ.get("OPENAI_RESPONSES_IMAGE_MODEL", "gpt-5.5")
        self.size = image_size
        self.quality = image_quality

    def generate(self, request: ImageGenerationRequest, output_path: Path) -> ImageGenerationResult:
        content: list[dict[str, Any]] = [{"type": "input_text", "text": request.prompt}]
        for path in request.input_image_paths:
            content.append({"type": "input_image", "image_url": _image_data_url(path)})

        payload = {
            "model": self.model,
            "input": [{"role": "user", "content": content}],
            "tools": [
                {
                    "type": "image_generation",
                    "action": "generate",
                    "size": self.size,
                    "quality": self.quality,
                }
            ],
        }
        http_request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(http_request, timeout=240) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            raise ProviderRuntimeError(f"OpenAI Responses image generation failed: {details}") from None
        except urllib.error.URLError as error:
            raise ProviderRuntimeError(f"OpenAI Responses image generation failed: {error.reason}") from None

        image_call = _first_image_generation_call(body)
        if not image_call or not image_call.get("result"):
            raise ProviderRuntimeError("OpenAI Responses image generation response did not include an image result.")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(base64.b64decode(image_call["result"]))
        return ImageGenerationResult(
            provider=self.provider_name,
            concept_id=request.concept_id,
            variant_id=request.variant_id,
            status=image_call.get("status", "generated"),
            image_path=str(output_path),
            metadata={
                "model": self.model,
                "size": self.size,
                "quality": self.quality,
                "revised_prompt": image_call.get("revised_prompt", ""),
                "input_image_count": len(request.input_image_paths),
            },
        )


def _image_data_url(path: str) -> str:
    file_path = Path(path)
    mime_type = mimetypes.guess_type(file_path.name)[0] or "image/png"
    return f"data:{mime_type};base64,{base64.b64encode(file_path.read_bytes()).decode('ascii')}"


def _first_image_generation_call(body: dict[str, Any]) -> dict[str, Any] | None:
    for output in body.get("output", []):
        if output.get("type") == "image_generation_call":
            return output
    return None
