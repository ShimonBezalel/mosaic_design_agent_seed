import json
import subprocess
import sys
from pathlib import Path

from mosaic_agent.demo import run_demo


ROOT = Path(__file__).resolve().parents[1]


def test_stub_demo_exports_expected_artifacts(tmp_path):
    package = run_demo(
        palette_path=ROOT / "examples" / "palette_db.example.json",
        brief_path=ROOT / "examples" / "project_brief.example.json",
        mode="stub",
        allow_assumptions=True,
        out_dir=tmp_path,
    )

    assert len(package.concepts) == 3
    for filename in [
        "concept_package.json",
        "artist_questions.md",
        "image_prompts.md",
        "critique.md",
        "contact_sheet.html",
        "visual_manifest.json",
    ]:
        assert (tmp_path / filename).exists()

    expected_images = [
        tmp_path / "images" / "concept_01_variant_01.png",
        tmp_path / "images" / "concept_01_variant_02.png",
        tmp_path / "images" / "concept_02_variant_01.png",
        tmp_path / "images" / "concept_02_variant_02.png",
        tmp_path / "images" / "concept_03_variant_01.png",
        tmp_path / "images" / "concept_03_variant_02.png",
    ]
    for image_path in expected_images:
        assert image_path.exists()
        assert image_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")

    assert not (tmp_path / "run_trace.json").exists()
    exported = json.loads((tmp_path / "concept_package.json").read_text())
    assert exported["mode"] == "stub"
    assert len(exported["concepts"]) == 3
    assert all(concept["critique"]["notes"] for concept in exported["concepts"])

    manifest = json.loads((tmp_path / "visual_manifest.json").read_text())
    assert manifest["provider"] == "stub"
    assert [image["image_path"] for image in manifest["images"]] == [
        "images/concept_01_variant_01.png",
        "images/concept_01_variant_02.png",
        "images/concept_02_variant_01.png",
        "images/concept_02_variant_02.png",
        "images/concept_03_variant_01.png",
        "images/concept_03_variant_02.png",
    ]
    assert all(image["prompt"] for image in manifest["images"])
    assert all(image["critique"]["text_risk"] for image in manifest["images"])

    contact_sheet = (tmp_path / "contact_sheet.html").read_text()
    assert "Town Entrance Stone" in contact_sheet
    assert "Desert Sunrise Welcome" in contact_sheet
    assert "terracotta orange" in contact_sheet
    assert "images/concept_01_variant_01.png" in contact_sheet


def test_cli_stub_demo_runs_without_api_keys(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mosaic_agent.demo",
            "--palette",
            str(ROOT / "examples" / "palette_db.example.json"),
            "--brief",
            str(ROOT / "examples" / "project_brief.example.json"),
            "--mode",
            "stub",
            "--allow-assumptions",
            "--out",
            str(tmp_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "concept_package.json").exists()


def test_openai_image_mode_without_key_fails_cleanly(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mosaic_agent.demo",
            "--palette",
            str(ROOT / "examples" / "palette_db.example.json"),
            "--brief",
            str(ROOT / "examples" / "project_brief.example.json"),
            "--mode",
            "openai-image",
            "--allow-assumptions",
            "--out",
            str(tmp_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "OPENAI_API_KEY" in result.stderr
    assert "Traceback" not in result.stderr


def test_gemini_image_mode_without_key_fails_cleanly(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mosaic_agent.demo",
            "--palette",
            str(ROOT / "examples" / "palette_db.example.json"),
            "--brief",
            str(ROOT / "examples" / "project_brief.example.json"),
            "--mode",
            "gemini-image",
            "--allow-assumptions",
            "--out",
            str(tmp_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "GEMINI_API_KEY" in result.stderr
    assert "Traceback" not in result.stderr
