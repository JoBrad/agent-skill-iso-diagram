"""Theme loading: color slots, tints, fonts, and text measurement."""

import json

from pathlib import Path
from typing import Any

from iso_diagram import SKILL_DIR


THEMES_DIR = SKILL_DIR / "themes"

# Colors for one slot: slot, hue, top, side, stroke, text.
Tier = dict[str, str]


def tint(hex_color: str, amount: float) -> str:
    """Mix a color toward white; amount 0 is the color, 1 is white."""
    rgb = [int(hex_color[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(c + (255 - c) * amount):02X}" for c in rgb)


def theme_path(name_or_path: str | Path, *, base: Path) -> Path:
    """Return the theme file: a bare name is a built-in theme, anything else a path from base.

    A bare name never looks at the working directory, so a file or folder there cannot
    shadow a built-in theme.
    """
    path = Path(name_or_path).expanduser()
    if len(path.parts) == 1 and not path.suffix:
        return THEMES_DIR / f"{path}.json"
    return base / path


class Theme:
    """A theme file: color slots and tints, ink colors, fonts, and text measurement."""

    def __init__(
        self,
        name_or_path: str | Path = "default",
        *,
        base: Path | None = None,
    ) -> None:
        """Load a built-in theme by name, or a theme file by path relative to base (default cwd)."""
        path = theme_path(name_or_path, base=base or Path.cwd())
        with path.open() as f:
            self.data = json.load(f)
        self.path = path
        d = self.data
        self.order, self.leaf, self.flow_slot = d["order"], d["leaf"], d["flow"]
        self.ink, self.background = d["ink"], d["background"]
        self.muted_opacity = d["muted_opacity"]
        self.min_surface_text = d["min_surface_text"]
        f = d["fonts"]
        self.sans = f"{f['sans']['family']}, {f['sans']['fallback']}"
        self.mono = f"'{f['mono']['family']}', {f['mono']['fallback']}"
        self._fonts = {}

    def tier(self, slot: str) -> Tier:
        """Colors for one slot: top and side tints, outline, text shade, and the raw hue."""
        s = self.data["slots"][slot]
        t = self.data["tints"]
        light = slot in self.data["light_slots"]
        return {
            "slot": slot,
            "hue": s["stroke"],
            "top": tint(s["stroke"], t["top"]),
            "side": tint(s["stroke"], t["side"]),
            "stroke": s["text"] if light else s["stroke"],
            "text": s["text"],
        }

    def level_slots(self, depth_count: int) -> list[str]:
        """Color by level: slots in order, the deepest level takes the leaf slot."""
        if depth_count > len(self.order) + 1:
            raise ValueError(
                f"{depth_count} levels but the theme has {len(self.order) + 1} slots"
            )
        return [*self.order[: depth_count - 1], self.leaf]

    @property
    def flow(self) -> Tier:
        """Colors for connectors and traffic: the theme's flow slot."""
        return self.tier(self.flow_slot)

    def font_file(self, kind: str) -> Path:
        """Return the font file for kind ('sans' or 'mono')."""
        return SKILL_DIR / self.data["fonts"][kind]["file"]

    def font_spec(self, kind: str) -> dict[str, Any]:
        """Return the theme's font entry for kind ('sans' or 'mono')."""
        return self.data["fonts"][kind]

    def measure(
        self, *, s: object, size: float, mono: bool = False, weight: int = 400
    ) -> float:
        """Return the rendered width of s in screen units, from the font's advance widths."""
        kind = "mono" if mono else "sans"
        if kind not in self._fonts:
            from fontTools.ttLib import TTFont

            font = TTFont(self.font_file(kind))
            self._fonts[kind] = (
                font.getBestCmap(),
                font["hmtx"].metrics,
                font["head"].unitsPerEm,
            )
        cmap, metrics, upem = self._fonts[kind]
        units = sum(
            metrics.get(cmap.get(ord(ch), ".notdef"), (upem // 2, 0))[0]
            for ch in str(s)
        )
        bold = 1 + max(0, weight - 400) / 4000 if not mono else 1
        return units / upem * size * bold

    def wrap_lines(
        self,
        *,
        s: str,
        size: float,
        width: float,
        mono: bool = False,
        weight: int = 400,
    ) -> list[str]:
        """Split s into lines no wider than width, breaking between words.

        A single word wider than width gets a line to itself; the fit check reports it.
        """
        lines: list[str] = []
        for word in s.split():
            joined = f"{lines[-1]} {word}" if lines else word
            if (
                lines
                and self.measure(s=joined, size=size, mono=mono, weight=weight) <= width
            ):
                lines[-1] = joined
            else:
                lines.append(word)
        return lines
