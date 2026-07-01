from __future__ import annotations

import base64
import os
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from mosaic_agent.image_edit_service import ImageEditRequest
from mosaic_agent.providers.base import ProviderConfigurationError, ProviderRuntimeError


class OpenAIImageEditProvider:
    provider_name = "openai-edit"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        image_model: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ProviderConfigurationError("OPENAI_API_KEY is required for --image-mode openai-edit.")
        self.model = image_model or os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2")
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)
        self.client = client

    def edit(self, request: ImageEditRequest, output_dir: Path) -> list[Path]:
        try:
            with ExitStack() as stack:
                image_files = [
                    stack.enter_context(open(path, "rb"))
                    for path in [request.base_image_path, *request.reference_image_paths]
                ]
                mask_file = stack.enter_context(open(request.mask_image_path, "rb"))
                response = self.client.images.edit(
                    model=self.model,
                    image=image_files,
                    mask=mask_file,
                    prompt=request.prompt,
                    n=request.variant_count,
                    quality=request.quality,
                    size=request.size,
                    output_format="png",
                )
        except Exception as error:
            raise ProviderRuntimeError(f"OpenAI masked image edit failed: {error}") from None

        output_dir.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        for index, item in enumerate(response.data, start=1):
            image_data = getattr(item, "b64_json", None)
            if not image_data:
                raise ProviderRuntimeError("OpenAI masked image edit response did not include b64_json image data.")
            output_path = output_dir / f"variant_{index:02d}.png"
            output_path.write_bytes(base64.b64decode(image_data))
            outputs.append(output_path)
        if len(outputs) != request.variant_count:
            raise ProviderRuntimeError(
                f"OpenAI masked image edit returned {len(outputs)} image(s); expected {request.variant_count}."
            )
        return outputs
