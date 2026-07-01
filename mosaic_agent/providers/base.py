from __future__ import annotations

from pathlib import Path
from typing import Protocol

from mosaic_agent.models import ImageGenerationRequest, ImageGenerationResult


class ProviderConfigurationError(RuntimeError):
    """Raised when a provider cannot run because credentials or config are missing."""


class ProviderRuntimeError(RuntimeError):
    """Raised when a provider call fails after configuration succeeds."""


class ImageProvider(Protocol):
    provider_name: str

    def generate(self, request: ImageGenerationRequest, output_path: Path) -> ImageGenerationResult:
        """Generate an image file or deterministic stand-in image."""
