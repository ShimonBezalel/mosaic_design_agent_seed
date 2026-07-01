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
    ]:
        assert (tmp_path / filename).exists()

    assert not (tmp_path / "run_trace.json").exists()
    exported = json.loads((tmp_path / "concept_package.json").read_text())
    assert exported["mode"] == "stub"
    assert len(exported["concepts"]) == 3
    assert all(concept["critique"]["notes"] for concept in exported["concepts"])


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
