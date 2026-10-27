"""Theme loading: color slots, tints, fonts, and text measurement."""

import json

from pathlib import Path

from iso_diagram.shared import SKILL_DIR


def tint(hex_color: str, amount: float) -> str:
    """Mix a color toward white; amount 0 is the color, 1 is white."""
    rgb = [int(hex_color[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(c + (255 - c) * amount):02X}" for c in rgb)


class Theme:
    def __init__(
        self,
        name_or_path: str | Path = "default",
    ) -> None:
        path = name_or_path
        if not Path(path).exists():
            path = SKILL_DIR / "themes" / f"{name_or_path}.json"
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

    def tier(self, slot):
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

    def level_slots(self, depth_count):
        """Color by level: slots in order, the deepest level takes the leaf slot."""
        if depth_count > len(self.order) + 1:
            raise ValueError(
                f"{depth_count} levels but the theme has {len(self.order) + 1} slots"
            )
        return [*self.order[: depth_count - 1], self.leaf]

    @property
    def flow(self):
        return self.tier(self.flow_slot)

    def font_file(self, kind):
        return SKILL_DIR / self.data["fonts"][kind]["file"]

    def font_spec(self, kind):
        return self.data["fonts"][kind]

    def measure(self, s, size, mono=False, weight=400):
        """Rendered width of a string in screen units, from the font's own advance widths."""
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
