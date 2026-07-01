import os
from pathlib import Path

import pytest

from mosaic_agent.models import ImageGenerationRequest
from mosaic_agent.providers.gemini_nano_banana import GeminiNanoBananaProvider
from mosaic_agent.providers.openai_image import OpenAIImageProvider
from mosaic_agent.providers.openai_responses_image import OpenAIResponsesImageProvider


@pytest.mark.skipif(
    not (os.environ.get("OPENAI_API_KEY") and os.environ.get("RUN_REAL_IMAGE_TESTS")),
    reason="set OPENAI_API_KEY and RUN_REAL_IMAGE_TESTS=1 to run real OpenAI image smoke tests",
)
def test_openai_provider_real_smoke(tmp_path):
    provider = OpenAIImageProvider()
    output_path = tmp_path / "openai_smoke.png"

    result = provider.generate(
        ImageGenerationRequest(
            provider="openai-image",
            concept_id="smoke",
            variant_id="variant_01",
            prompt="A simple handmade ceramic mosaic sun on a stone, no text.",
            negative_prompt="avoid pixel art",
        ),
        output_path,
    )

    assert output_path.exists()
    assert result.status == "generated"


@pytest.mark.skipif(
    not ((os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")) and os.environ.get("RUN_REAL_IMAGE_TESTS")),
    reason="set GEMINI_API_KEY or GOOGLE_API_KEY and RUN_REAL_IMAGE_TESTS=1 to run real Gemini image smoke tests",
)
def test_gemini_provider_real_smoke(tmp_path):
    provider = GeminiNanoBananaProvider()
    output_path = tmp_path / "gemini_smoke.png"

    result = provider.generate(
        ImageGenerationRequest(
            provider="gemini-image",
            concept_id="smoke",
            variant_id="variant_01",
            prompt="A simple handmade ceramic mosaic sun on a stone, no text.",
            negative_prompt="avoid pixel art",
        ),
        output_path,
    )

    assert output_path.exists()
    assert result.status == "generated"


@pytest.mark.skipif(
    not (os.environ.get("OPENAI_API_KEY") and os.environ.get("RUN_REAL_IMAGE_TESTS")),
    reason="set OPENAI_API_KEY and RUN_REAL_IMAGE_TESTS=1 to run real OpenAI Responses image smoke tests",
)
def test_openai_responses_image_provider_real_smoke(tmp_path):
    provider = OpenAIResponsesImageProvider(image_size="1024x1024", image_quality="low")
    output_path = tmp_path / "openai_responses_smoke.png"

    result = provider.generate(
        ImageGenerationRequest(
            provider="openai-responses-image",
            concept_id="smoke",
            variant_id="variant_01",
            prompt="Draw a simple handmade ceramic mosaic sun on a stone, no text.",
            negative_prompt="avoid pixel art",
        ),
        output_path,
    )

    assert output_path.exists()
    assert result.status in {"generated", "completed"}
