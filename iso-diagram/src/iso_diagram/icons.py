"""Feather and Lucide icons, fetched on first use.

    uv run --project SKILL_DIR iso-icons find WORD

The skill ships only assets/icons/manifest.json, which pins each set's version and
every icon's SHA-256. The first build that uses an icon downloads that one SVG from
jsDelivr, checks it against the manifest, and saves it under assets/icons/<set>/,
so later builds read it from disk. Names come from the manifest, so finding an icon
needs no download.
"""

import argparse
import functools
import hashlib
import json
import ssl
import sys
import urllib.error
import urllib.request

from pathlib import Path

import truststore

from iso_diagram.shared import ASSETS_DIR


ICONS_DIR = ASSETS_DIR / "icons"
CDN = "https://cdn.jsdelivr.net/npm"
TIMEOUT = 30
# Verify against the OS trust store: the CA file a standalone Python ships with can
# lack roots the OS trusts, including jsDelivr's and corporate inspection proxies'.
TLS = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


@functools.cache
def icon_sets() -> list[dict]:
    """Return the manifest's icon sets, in lookup order."""
    return json.loads((ICONS_DIR / "manifest.json").read_text())["sets"]


def find(*, word: str) -> list[tuple[str, str]]:
    """Return (set, name) for every icon whose name contains word."""
    word = word.lower()
    return [(s["name"], n) for s in icon_sets() for n in s["icons"] if word in n]


def source(*, name: str) -> Path | None:
    """Path of a 24x24 icon from the first set that has it, fetching it if needed.

    None when no set has the name.
    """
    for icon_set in icon_sets():
        digest = icon_set["icons"].get(name)
        if digest is None:
            continue
        path = ICONS_DIR / icon_set["name"] / f"{name}.svg"
        if not path.exists():
            download(icon_set=icon_set, name=name, digest=digest, path=path)
        return path
    return None


def download(*, icon_set: dict, name: str, digest: str, path: Path) -> None:
    """Fetch one icon, verify its SHA-256, and write it to path."""
    url = (
        f"{CDN}/{icon_set['package']}@{icon_set['version']}"
        f"/{icon_set['path']}/{name}.svg"
    )
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT, context=TLS) as resp:
            data = resp.read()
    except urllib.error.URLError as e:
        raise OSError(f"icon '{name}': download from {url} failed: {e}") from e
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f"icon '{name}': {url} does not match the manifest hash")
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part")
    partial.write_bytes(data)
    partial.replace(path)


def main() -> None:
    """Command line: search icon names."""
    ap = argparse.ArgumentParser(description="Search the Feather and Lucide icons.")
    sub = ap.add_subparsers(dest="command", required=True)
    find_cmd = sub.add_parser("find", help="list icons whose name contains WORD")
    find_cmd.add_argument("word", metavar="WORD")
    args = ap.parse_args()
    matches = find(word=args.word)
    if not matches:
        sys.exit(f"no icon name contains '{args.word}'")
    for set_name, name in matches:
        print(f"{name}\t{set_name}")


if __name__ == "__main__":
    main()
