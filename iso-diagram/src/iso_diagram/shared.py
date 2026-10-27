"""Shared utility functions."""

from pathlib import Path
from typing import Any


# A parsed JSON spec, or one of its nested objects.
Spec = dict[str, Any]

SKILL_DIR = Path(__file__).resolve().parents[2]
THEMES_DIR = SKILL_DIR / "themes"
ASSETS_DIR = SKILL_DIR / "assets"


def resolved_path(path: str | Path) -> Path:
    """Return the absolute resolved Path for the given path string."""
    return Path(path).expanduser().resolve()


def json_file(path: str) -> Path:
    """Return the absolute resolved Path for a JSON file."""
    p = resolved_path(path)
    if not p.is_file() or p.suffix.lower() != ".json":
        raise ValueError(f"Invalid JSON file: {path}")
    return p
