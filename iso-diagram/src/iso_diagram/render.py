"""PNG export through headless Chrome or Chromium."""

import shutil
import subprocess

from pathlib import Path

from iso_diagram.shared import resolved_path


CANDIDATES: list[str] = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "chromium",
    "chromium-browser",
]


def browser() -> str:
    """Return the path to a Chrome or Chromium executable."""
    for c in CANDIDATES:
        path = c if Path(c).is_absolute() else shutil.which(c)
        if path and Path(path).exists():
            return path
    raise SystemExit("PNG export needs Chrome or Chromium, and neither was found")


def png(
    svg_path: str | Path,
    png_path: str | Path,
    width: int,
    height: int,
    scale: int = 2,
) -> None:
    cmd = [
        browser(),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--force-device-scale-factor={scale}",
        f"--window-size={int(width)},{int(height)}",
        f"--screenshot={resolved_path(png_path)}",
        "file://" + resolved_path(svg_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
