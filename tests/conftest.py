"""Shared pytest fixtures.

pytest loads this file on its own, and every fixture defined here is available to
every test without an import. Put test-data builders in tests/factories.py and
import them as `from tests.factories import ...`; `pythonpath = ["."]` in
[tool.pytest] makes that work without any __init__.py files.

Tests never reach the network: every test runs against a throwaway icon cache
built from synthetic icons, and a download attempt fails the test.
"""

import hashlib
import json
import urllib.request

from collections.abc import Iterator
from pathlib import Path

import pytest

from iso_diagram import icons


# Synthetic stand-ins for the real icons, keyed by set. Every name is cached on
# disk except UNCACHED, which exists only in the manifest.
ICON_SETS = {
    "feather": ("database", "globe", "server", "shield"),
    "lucide": ("network", "router", "shield"),
}
UNCACHED = ("lucide", "cloud-cog")


def fake_svg(name: str) -> bytes:
    """Return a small, distinct SVG for an icon name."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        f'<path d="M2 2 L{2 + len(name)} 22"/></svg>'
    ).encode()


def digest(data: bytes) -> str:
    """Return the hex SHA-256 the manifest stores for data."""
    return hashlib.sha256(data).hexdigest()


@pytest.fixture(autouse=True)
def icon_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point the icon cache at a temp dir of synthetic icons and block downloads."""
    root = tmp_path / "icons"
    sets = []
    for set_name, names in ICON_SETS.items():
        entries = {}
        for name in names:
            data = fake_svg(name)
            path = root / set_name / f"{name}.svg"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            entries[name] = digest(data)
        if set_name == UNCACHED[0]:
            entries[UNCACHED[1]] = digest(fake_svg(UNCACHED[1]))
        sets.append(
            {
                "name": set_name,
                "package": f"{set_name}-pkg",
                "version": "1.0.0",
                "path": "icons",
                "icons": entries,
            }
        )
    (root / "manifest.json").write_text(json.dumps({"sets": sets}))

    def no_network(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"test tried to reach the network: {args[:1]}")

    monkeypatch.setattr(icons, "ICONS_DIR", root)
    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    icons.icon_sets.cache_clear()
    yield root
    icons.icon_sets.cache_clear()
