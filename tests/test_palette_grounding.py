from pathlib import Path

from mosaic_agent.demo import run_demo
from mosaic_agent.load import load_palette


ROOT = Path(__file__).resolve().parents[1]


def test_stub_concepts_only_use_palette_tile_ids(tmp_path):
    palette_path = ROOT / "examples" / "palette_db.example.json"
    brief_path = ROOT / "examples" / "project_brief.example.json"

    package = run_demo(
        palette_path=palette_path,
        brief_path=brief_path,
        mode="stub",
        allow_assumptions=True,
        out_dir=tmp_path,
    )

    palette_ids = {tile.tile_id for tile in load_palette(palette_path).tiles}
    assert [concept.name for concept in package.concepts] == [
        "Desert Sunrise Welcome",
        "Path Into Community",
        "Typography Stone Ribbon",
    ]

    for concept in package.concepts:
        assert 8 <= len(concept.palette_tile_ids) <= 14
        assert set(concept.palette_tile_ids).issubset(palette_ids)
