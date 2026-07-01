from __future__ import annotations

from typing import Protocol

from mosaic_agent.models import ImageGenerationRequest, ImageGenerationResult


class ImageProvider(Protocol):
    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Generate an image or deterministic stand-in metadata."""
