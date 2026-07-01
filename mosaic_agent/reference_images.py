from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


class ReferenceImageError(ValueError):
    pass


def ensure_reference_images_exist(paths: Iterable[str]) -> None:
    missing = [path for path in paths if not Path(path).exists()]
    if missing:
        raise ReferenceImageError(f"reference image paths do not exist: {', '.join(missing)}")
