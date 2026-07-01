from __future__ import annotations

from mosaic_agent.models import ImageGenerationRequest, ImageGenerationResult


class StubImageProvider:
    provider_name = "stub"

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        return ImageGenerationResult(
            provider=self.provider_name,
            concept_id=request.concept_id,
            status="stubbed",
            metadata={
                "prompt_length": len(request.prompt),
                "negative_prompt_length": len(request.negative_prompt),
                "external_api_called": False,
            },
        )
