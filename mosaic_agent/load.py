from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from mosaic_agent.models import PaletteDB, ProjectBrief


def load_json(path: str | Path) -> dict[str, Any]:
    json_path = Path(path)
    with json_path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{json_path} must contain a JSON object")
    return data


def validate_json_file(instance_path: str | Path, schema_path: str | Path) -> dict[str, Any]:
    instance = load_json(instance_path)
    schema = load_json(schema_path)
    Draft202012Validator(schema).validate(instance)
    return instance


def load_brief(path: str | Path) -> ProjectBrief:
    return ProjectBrief.model_validate(load_json(path))


def load_palette(path: str | Path) -> PaletteDB:
    return PaletteDB.model_validate(load_json(path))
