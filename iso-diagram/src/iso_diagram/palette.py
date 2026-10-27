"""Swatch sheet for a theme: slabs, shades, contrast, and simulated color vision.

    uv run --project SKILL_DIR iso-palette [THEME] -o OUT.svg [--png]

Also prints the closest pair of stroke colors under each type of color blindness, so a new
theme can be judged before any diagram uses it.
"""

import argparse
import itertools
import math

from collections.abc import Sequence
from pathlib import Path

from iso_diagram import fonts, render
from iso_diagram.iso import Slab, TextStyle, plane_matrix, svg_doc, text
from iso_diagram.theme import Theme


MACHADO = {  # Machado, Oliveira and Fernandes 2009, full severity, linear RGB
    "Deuteranopia": [
        [0.367322, 0.860646, -0.227968],
        [0.280085, 0.672501, 0.047413],
        [-0.011820, 0.042940, 0.968881],
    ],
    "Protanopia": [
        [0.152286, 1.052583, -0.204868],
        [0.114503, 0.786281, 0.099216],
        [-0.003882, -0.048116, 1.051998],
    ],
    "Tritanopia": [
        [1.255528, -0.076749, -0.178779],
        [-0.078411, 0.930809, 0.147602],
        [0.004733, 0.691367, 0.303900],
    ],
}


def lin(c: float) -> float:
    """Return an sRGB channel (0 to 255) as linear light (0 to 1)."""
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb(h: str) -> list[int]:
    """Return the 0 to 255 channels of a #RRGGBB color."""
    return [int(h[i : i + 2], 16) for i in (1, 3, 5)]


def simulate_linear(h: str, m: list[list[float]]) -> list[float]:
    """Return color h in linear RGB as seen through simulation matrix m."""
    v = [lin(c) for c in rgb(h)]
    return [max(0.0, min(1.0, sum(m[i][j] * v[j] for j in range(3)))) for i in range(3)]


def to_hex(linear: Sequence[float]) -> str:
    """Return a linear RGB color as #RRGGBB."""
    enc = [
        12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055 for v in linear
    ]
    return "#" + "".join(f"{round(255 * max(0, min(1, v))):02X}" for v in enc)


def lab(linear: Sequence[float]) -> tuple[float, float, float]:
    """Return the CIELAB coordinates of a linear RGB color."""
    x = 0.4124 * linear[0] + 0.3576 * linear[1] + 0.1805 * linear[2]
    y = 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
    z = 0.0193 * linear[0] + 0.1192 * linear[1] + 0.9505 * linear[2]
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116  # ruff: ignore[lambda-assignment]
    fx, fy, fz = f(x / 0.95047), f(y), f(z / 1.08883)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def contrast(h: str) -> float:
    """Return the contrast ratio of color h against white."""
    v = [lin(c) for c in rgb(h)]
    return 1.05 / (0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2] + 0.05)


def build(theme: Theme) -> tuple[str, list[str], float]:
    """Return the swatch sheet SVG, the color-blindness report lines, and the width."""
    slots = [*theme.order, theme.leaf]
    ink = theme.ink
    out = [
        text(
            x=40,
            y=64,
            s=f"{theme.data['name'].title()} palette",
            style=TextStyle(font=theme.sans, size=36, fill=ink["title"], weight=600),
        ),
        text(
            x=40,
            y=98,
            s=f"{len(slots)} slots, assigned in order; the last is the leaf tier. Tints mix the "
            f"stroke toward white. Contrast is against white.",
            style=TextStyle(font=theme.sans, size=18, fill=ink["caption"]),
        ),
    ]
    x0, colw = 200, 210
    rows = [
        ("Stroke", "hue"),
        ("Text", "text"),
        ("Top tint", "top"),
        ("Side tint", "side"),
    ]
    for i, slot in enumerate(slots):
        t = theme.tier(slot)
        cx = x0 + i * colw + colw / 2
        s = Slab(name=slot, cx=cx, cy=210, w=110, d=110, h=22, r=14)
        out.append(
            s.shadow(dy=24) + s.svg(top=t["top"], side=t["side"], stroke=t["stroke"])
        )
        out.append(
            f'<g transform="{plane_matrix(cx, 210)} rotate(-90)">'
            + text(
                x=0,
                y=0,
                s=slot.title(),
                style=TextStyle(
                    font=theme.sans,
                    size=20,
                    fill=t["text"],
                    weight=600,
                    anchor="middle",
                    baseline="central",
                ),
            )
            + "</g>"
        )
        out.append(
            text(
                x=cx,
                y=330,
                s=f"{i + 1}. {slot.title()}",
                style=TextStyle(
                    font=theme.sans,
                    size=20,
                    fill=ink["title"],
                    weight=600,
                    anchor="middle",
                ),
            )
        )
        for r, (_, key) in enumerate(rows):
            y = 360 + r * 66
            out.append(
                f'<rect x="{cx - 85:.1f}" y="{y}" width="56" height="44" rx="8" fill="{t[key]}" '
                f'stroke="#E5E7EB"/>'
            )
            out.append(
                text(
                    x=cx - 18,
                    y=y + 20,
                    s=t[key],
                    style=TextStyle(
                        font=theme.mono, size=17, fill=ink["title"], weight=500
                    ),
                )
            )
            if key in ("hue", "text"):
                out.append(
                    text(
                        x=cx - 18,
                        y=y + 40,
                        s=f"{contrast(t[key]):.1f}:1",
                        style=TextStyle(font=theme.sans, size=15, fill=ink["caption"]),
                    )
                )
    for r, (label, _) in enumerate(rows):
        out.append(
            text(
                x=40,
                y=388 + r * 66,
                s=label,
                style=TextStyle(
                    font=theme.sans, size=18, fill=ink["label"], weight=600
                ),
            )
        )

    out.append(
        text(
            x=40,
            y=690,
            s="Simulated color vision (stroke colors)",
            style=TextStyle(font=theme.sans, size=26, fill=ink["title"], weight=600),
        )
    )
    report = []
    for r, (label, m) in enumerate([("Typical", None), *list(MACHADO.items())]):
        y = 720 + r * 74
        out.append(
            text(
                x=40,
                y=y + 34,
                s=label,
                style=TextStyle(
                    font=theme.sans, size=18, fill=ink["label"], weight=600
                ),
            )
        )
        sims = {}
        for i, slot in enumerate(slots):
            hue = theme.tier(slot)["hue"]
            linear = (
                [lin(c) for c in rgb(hue)] if m is None else simulate_linear(hue, m)
            )
            sims[slot] = linear
            out.append(
                f'<rect x="{x0 + i * colw + 10}" y="{y}" width="{colw - 20}" height="54" rx="10" '
                f'fill="{to_hex(linear)}"/>'
            )
        d, a, b = min(
            (math.dist(lab(sims[a]), lab(sims[b])), a, b)
            for a, b in itertools.combinations(slots, 2)
        )
        report.append(f"{label:13} closest pair {a} / {b}: difference {d:.1f}")
    light = ", ".join(theme.data["light_slots"]) or "none"
    out.append(
        text(
            x=40,
            y=1040,
            s=f"Simulation: Machado et al. 2009, full severity. Outlines for light slots ({light}) "
            f"use the text shade.",
            style=TextStyle(font=theme.sans, size=16, fill=ink["caption"]),
        )
    )
    width = x0 + len(slots) * colw + 40
    return (
        svg_doc(
            size=(width, 1070),
            body="".join(out),
            background=theme.background,
            title=f"{theme.data['name']} palette",
        ),
        report,
        width,
    )


def main() -> None:
    """Draw the swatch sheet for the theme named on the command line."""
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "theme",
        nargs="?",
        default="default",
    )
    ap.add_argument(
        "-o",
        "--out",
        required=True,
        type=render.resolved_path,
    )
    ap.add_argument(
        "--png",
        action="store_true",
    )
    args = ap.parse_args()
    theme = Theme(args.theme)
    output_svg_file = Path(args.out)
    svg_content, report, width = build(theme)
    svg_content = fonts.embed(svg_content, theme)
    output_svg_file.parent.mkdir(parents=True, exist_ok=True)
    with output_svg_file.open("w") as f:
        f.write(svg_content)
    print(f"wrote {output_svg_file}")
    print("\n".join(report))
    print("A difference under about 10 is hard to tell apart; aim for 15 or more.")
    if args.png:
        output_png_file = output_svg_file.with_suffix(".png")
        render.png(
            svg_path=output_svg_file, png_path=output_png_file, width=width, height=1070
        )
        print(f"wrote {output_png_file}")


if __name__ == "__main__":
    main()
