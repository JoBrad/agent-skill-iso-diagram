"""PNG export through headless Chrome or Chromium."""

import shutil
import subprocess

from pathlib import Path


CANDIDATES: list[str] = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "chromium",
    "chromium-browser",
]


def resolved_path(path: str | Path) -> Path:
    """Return path made absolute, with ~ expanded."""
    return Path(path).expanduser().resolve()


def browser() -> str:
    """Return the path to a Chrome or Chromium executable."""
    for c in CANDIDATES:
        path = c if Path(c).is_absolute() else shutil.which(c)
        if path and Path(path).exists():
            return path
    raise SystemExit("PNG export needs Chrome or Chromium, and neither was found")


def png(
    *,
    svg_path: str | Path,
    png_path: str | Path,
    width: float,
    height: float,
    scale: float = 2,
) -> None:
    """Screenshot svg_path to png_path at width x height, scaled by scale."""
    cmd = [
        browser(),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--force-device-scale-factor={scale}",
        # Rounded the way svg_doc writes the SVG's size, so no edge pixel is cut off.
        f"--window-size={width:.0f},{height:.0f}",
        f"--screenshot={resolved_path(png_path)}",
        resolved_path(svg_path).as_uri(),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
