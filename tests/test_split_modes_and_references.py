import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from mosaic_agent.demo import run_demo
from mosaic_agent.load import load_brief
from mosaic_agent.models import ImageGenerationRequest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_BRIEF = ROOT / "examples" / "real_image_fixtures" / "briefs" / "project_brief.real_image_fixture.json"
PALETTE = ROOT / "examples" / "palette_db.example.json"


def test_stub_ideation_stub_image_mode_supports_limits_and_references(tmp_path):
    package = run_demo(
        palette_path=PALETTE,
        brief_path=FIXTURE_BRIEF,
        ideation_mode="stub",
        image_mode="stub",
        allow_assumptions=True,
        out_dir=tmp_path,
        concept_limit=1,
        variants_per_concept=1,
    )

    assert len(package.concepts) == 1
    assert (tmp_path / "images" / "concept_01_variant_01.png").exists()
    assert not (tmp_path / "images" / "concept_01_variant_02.png").exists()

    manifest = json.loads((tmp_path / "visual_manifest.json").read_text())
    assert manifest["ideation_mode"] == "stub"
    assert manifest["image_mode"] == "stub"
    assert len(manifest["images"]) == 1
    assert manifest["input_references"] == [
        {
            "role": "artist_style_reference",
            "source_path": "examples/real_image_fixtures/images/artist_style_reference.png",
            "image_path": "input_references/artist_style_reference_01.png",
        }
    ]

    contact_sheet = (tmp_path / "contact_sheet.html").read_text()
    assert "Generated images are visual ideation only" in contact_sheet
    assert "artist_style_reference" in contact_sheet
    assert "input_references/artist_style_reference_01.png" in contact_sheet


def test_reference_image_paths_are_validated(tmp_path):
    with pytest.raises(ValidationError):
        ImageGenerationRequest(
            provider="stub",
            concept_id="concept_01",
            variant_id="variant_01",
            prompt="prompt",
            input_image_paths=[str(tmp_path / "missing.png")],
            input_image_roles=["artist_style_reference"],
        )


def test_cli_missing_reference_image_fails_without_traceback(tmp_path):
    broken_brief = json.loads(FIXTURE_BRIEF.read_text())
    broken_brief["reference_image_paths"] = ["examples/real_image_fixtures/images/missing.png"]
    brief_path = tmp_path / "broken_brief.json"
    brief_path.write_text(json.dumps(broken_brief), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mosaic_agent.demo",
            "--palette",
            str(PALETTE),
            "--brief",
            str(brief_path),
            "--ideation-mode",
            "stub",
            "--image-mode",
            "stub",
            "--allow-assumptions",
            "--out",
            str(tmp_path / "out"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Reference image error" in result.stderr
    assert "missing.png" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_split_modes_work_without_api_keys(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mosaic_agent.demo",
            "--palette",
            str(PALETTE),
            "--brief",
            str(FIXTURE_BRIEF),
            "--ideation-mode",
            "stub",
            "--image-mode",
            "stub",
            "--allow-assumptions",
            "--concept-limit",
            "1",
            "--variants-per-concept",
            "1",
            "--out",
            str(tmp_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "contact_sheet.html").exists()
    assert (tmp_path / "images" / "concept_01_variant_01.png").exists()


def test_fixture_brief_roles_match_references():
    brief = load_brief(FIXTURE_BRIEF)

    assert brief.reference_image_paths == ["examples/real_image_fixtures/images/artist_style_reference.png"]
    assert brief.reference_image_roles == ["artist_style_reference"]
