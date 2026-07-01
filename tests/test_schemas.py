import json
from pathlib import Path

from jsonschema import Draft202012Validator

from mosaic_agent.load import load_json
from mosaic_agent.models import PaletteDB, ProjectBrief


ROOT = Path(__file__).resolve().parents[1]


def test_example_json_files_match_declared_schemas():
    examples = {
        "project_brief": ROOT / "examples" / "project_brief.example.json",
        "palette_db": ROOT / "examples" / "palette_db.example.json",
    }

    for name, example_path in examples.items():
        schema = json.loads((ROOT / "schemas" / f"{name}.schema.json").read_text())
        instance = json.loads(example_path.read_text())
        Draft202012Validator(schema).validate(instance)


def test_examples_load_into_typed_models():
    brief = ProjectBrief.model_validate(load_json(ROOT / "examples" / "project_brief.example.json"))
    palette = PaletteDB.model_validate(load_json(ROOT / "examples" / "palette_db.example.json"))

    assert brief.project_name == "Town Entrance Stone"
    assert len(palette.tiles) >= 8
