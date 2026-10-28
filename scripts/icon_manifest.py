"""Regenerate iso-diagram/assets/icons/manifest.json from pinned npm releases.

    uv run scripts/icon_manifest.py

Dev-only: the skill reads the manifest, never this script. Each tarball is checked
against the integrity hash npm publishes before any icon in it is hashed, so the
manifest's SHA-256 values come from the same bytes jsDelivr serves. Bump a version
in SETS, rerun, and review the manifest diff for renamed or removed icons.
"""

import base64
import hashlib
import io
import json
import ssl
import tarfile

from pathlib import Path

import httpx2
import truststore


# Lookup order: the skill uses the first set that has a name.
SETS = [
    {
        "name": "feather",
        "package": "feather-icons",
        "version": "4.29.2",
        "path": "dist/icons",
    },
    {
        "name": "lucide",
        "package": "lucide-static",
        "version": "0.460.0",
        "path": "icons",
    },
]
MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "iso-diagram"
    / "assets"
    / "icons"
    / "manifest.json"
)
TIMEOUT = 120

# Verify SSL certificates against the OS trust store.
TLS = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


def fetch(*, url: str) -> bytes:
    """Return the body at url."""
    try:
        res = httpx2.get(url=url, timeout=TIMEOUT, verify=TLS)
        res.raise_for_status()
        return res.content
    except httpx2.HTTPError as e:
        raise SystemExit(f"Failed to fetch {url}: {e}") from e


def tarball(*, package: str, version: str) -> bytes:
    """Download a package tarball and verify it against npm's sha512 integrity."""
    meta = json.loads(fetch(url=f"https://registry.npmjs.org/{package}/{version}"))
    data = fetch(url=meta["dist"]["tarball"])
    algo, expected = meta["dist"]["integrity"].split("-", 1)
    if algo != "sha512":
        raise SystemExit(f"{package}@{version}: unexpected integrity type {algo}")
    actual = base64.b64encode(hashlib.sha512(data).digest()).decode()
    if actual != expected:
        raise SystemExit(f"{package}@{version}: tarball fails its integrity check")
    return data


def icon_hashes(*, data: bytes, path: str) -> dict[str, str]:
    """Map each SVG directly under package/<path>/ to its SHA-256."""
    prefix = f"package/{path}/"
    hashes = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for member in tar.getmembers():
            rest = member.name.removeprefix(prefix)
            if rest == member.name or "/" in rest or not rest.endswith(".svg"):
                continue
            if svg_content := tar.extractfile(member):
                body = svg_content.read()
                hashes[rest.removesuffix(".svg")] = hashlib.sha256(body).hexdigest()
    return dict(sorted(hashes.items()))


def main() -> None:
    """Rebuild the manifest and print an icon count per set."""
    sets = []
    for icon_set in SETS:
        data = tarball(package=icon_set["package"], version=icon_set["version"])
        icons = icon_hashes(data=data, path=icon_set["path"])
        print(f"{icon_set['name']}: {len(icons)} icons")
        sets.append({**icon_set, "icons": icons})
    MANIFEST.write_text(json.dumps({"sets": sets}, indent=1) + "\n")
    print(f"wrote {MANIFEST}")


if __name__ == "__main__":
    main()
