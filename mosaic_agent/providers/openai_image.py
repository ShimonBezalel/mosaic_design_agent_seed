from __future__ import annotations

from mosaic_agent.models import ImageGenerationRequest, ImageGenerationResult


class OpenAIImageProvider:
    provider_name = "openai"

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        raise RuntimeError("OpenAI image generation is not implemented in the stub-first prototype.")
