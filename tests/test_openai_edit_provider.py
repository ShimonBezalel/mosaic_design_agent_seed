import base64
import os
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw
from pydantic import ValidationError

from mosaic_agent.image_edit_service import ImageEditRequest
from mosaic_agent.providers.base import ProviderConfigurationError
from mosaic_agent.providers.openai_edit import OpenAIImageEditProvider


def _png_bytes(color: str = "#c95a2a") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _edit_assets(tmp_path: Path) -> tuple[Path, Path, Path]:
    base_path = tmp_path / "base.png"
    mask_path = tmp_path / "mask.png"
    reference_path = tmp_path / "reference.png"
    Image.new("RGB", (64, 64), "#d8c6a8").save(base_path)
    mask = Image.new("RGBA", (64, 64), (0, 0, 0, 255))
    ImageDraw.Draw(mask).rectangle((16, 16, 48, 48), fill=(0, 0, 0, 0))
    mask.save(mask_path)
    Image.new("RGB", (64, 64), "#2fa7b1").save(reference_path)
    return base_path, mask_path, reference_path


class _FakeImages:
    def __init__(self) -> None:
        self.kwargs = None

    def edit(self, **kwargs):
        self.kwargs = kwargs
        encoded = base64.b64encode(_png_bytes()).decode("ascii")
        return SimpleNamespace(
            data=[SimpleNamespace(b64_json=encoded), SimpleNamespace(b64_json=encoded)],
            usage={"total_tokens": 1},
        )


class _FakeClient:
    def __init__(self) -> None:
        self.images = _FakeImages()


def test_openai_edit_provider_sends_base_first_mask_references_and_count(tmp_path):
    base_path, mask_path, reference_path = _edit_assets(tmp_path)
    client = _FakeClient()
    provider = OpenAIImageEditProvider(api_key="test-key", client=client)
    request = ImageEditRequest(
        provider="openai-edit",
        concept_id="concept_01",
        prompt="Edit the masked stone face.",
        base_image_path=str(base_path),
        mask_image_path=str(mask_path),
        reference_image_paths=[str(reference_path)],
        variant_count=2,
        quality="low",
        size="1024x1024",
    )

    outputs = provider.edit(request, tmp_path / "outputs")

    assert [path.name for path in outputs] == ["variant_01.png", "variant_02.png"]
    assert all(path.exists() for path in outputs)
    assert client.images.kwargs["n"] == 2
    assert client.images.kwargs["quality"] == "low"
    assert client.images.kwargs["size"] == "1024x1024"
    assert [Path(file.name).name for file in client.images.kwargs["image"]] == [
        "base.png",
        "reference.png",
    ]
    assert Path(client.images.kwargs["mask"].name).name == "mask.png"


def test_openai_edit_provider_requires_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ProviderConfigurationError, match="OPENAI_API_KEY"):
        OpenAIImageEditProvider()


def test_image_edit_request_rejects_mismatched_dimensions(tmp_path):
    base_path, mask_path, _ = _edit_assets(tmp_path)
    Image.new("RGBA", (32, 32), (0, 0, 0, 255)).save(mask_path)

    with pytest.raises(ValidationError, match="same dimensions"):
        ImageEditRequest(
            provider="stub",
            concept_id="concept_01",
            prompt="prompt",
            base_image_path=str(base_path),
            mask_image_path=str(mask_path),
        )


@pytest.mark.skipif(
    not (os.environ.get("OPENAI_API_KEY") and os.environ.get("RUN_REAL_IMAGE_TESTS")),
    reason="set OPENAI_API_KEY and RUN_REAL_IMAGE_TESTS=1 for the paid masked edit canary",
)
def test_openai_edit_provider_real_masked_canary(tmp_path):
    base_path, mask_path, _ = _edit_assets(tmp_path)
    provider = OpenAIImageEditProvider(image_model="gpt-image-2")
    request = ImageEditRequest(
        provider="openai-edit",
        concept_id="canary",
        prompt=(
            "Edit only the transparent square. Add a few large terracotta broken ceramic tile shards with visible "
            "grout. Preserve everything outside the mask. No text."
        ),
        base_image_path=str(base_path),
        mask_image_path=str(mask_path),
        variant_count=1,
        quality="low",
        size="1024x1024",
    )

    outputs = provider.edit(request, tmp_path / "real")

    assert len(outputs) == 1
    assert outputs[0].exists()
