from __future__ import annotations

from mosaic_agent.models import ImageGenerationRequest, ImageGenerationResult


class GeminiNanoBananaProvider:
    provider_name = "gemini_nano_banana"

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        raise RuntimeError("Gemini/Nano Banana image generation is not implemented in the stub-first prototype.")
