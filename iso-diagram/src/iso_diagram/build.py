"""Build an isometric diagram from a JSON spec.

    uv run --project SKILL_DIR iso-build SPEC.json -o OUT.svg [--png] [--scale 2] [--theme NAME|PATH]

Writes an SVG with its fonts embedded. --png also writes OUT.png through headless Chrome.
Prints every layout-rule problem it finds and exits 1 when there are any (--allow-issues
writes the files anyway and exits 0).
"""

import argparse
import json
import os
import sys

from pathlib import Path

from iso_diagram import fonts, render, stack, tree
from iso_diagram.shared import resolved_path
from iso_diagram.theme import Theme


STYLES = {"iso-tree": tree.build, "iso-stack": stack.build}


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("spec")
    ap.add_argument(
        "-o",
        "--out",
        type=resolved_path,
        required=True,
        help="output .svg path",
    )
    ap.add_argument(
        "--theme",
        help="theme name in themes/ or a path; overrides the spec",
    )
    ap.add_argument(
        "--png",
        action="store_true",
        help="also write a PNG next to the SVG",
    )
    ap.add_argument(
        "--scale",
        type=float,
        default=2,
        help="PNG pixel ratio (default 2)",
    )
    ap.add_argument(
        "--allow-issues",
        action="store_true",
        help="write output even when checks fail",
    )
    args = ap.parse_args()

    with Path(args.spec).open() as f:
        spec = json.load(f)
    for key in ("style", "story", "points"):
        if key not in spec:
            sys.exit(
                f"spec is missing '{key}': every diagram starts from its story and key points"
            )
    if spec["style"] not in STYLES:
        sys.exit(
            f"unknown style '{spec['style']}'; expected one of {', '.join(STYLES)}"
        )
    theme = Theme(args.theme or spec.get("theme", "default"))

    svg, reg, (width, height) = STYLES[spec["style"]](spec, theme)
    issues = reg.check(width, height)
    for i in issues:
        print(f"ISSUE {i}")
    if issues and not args.allow_issues:
        sys.exit(
            f"{len(issues)} layout issue(s); nothing written. Fix the spec, or pass --allow-issues."
        )

    svg = fonts.embed(svg, theme)
    output_svg_file: Path = args.out
    output_svg_file.parent.mkdir(exist_ok=True, parents=True)
    with output_svg_file.open("w") as f:
        f.write(svg)
    print(
        f"wrote {output_svg_file} ({len(svg) / 1024:.0f} KB, {width:.0f}x{height:.0f}, theme {theme.data['name']})"
    )
    if args.png:
        png = output_svg_file.with_suffix(".png")
        render.png(output_svg_file, png, width, height, args.scale)
        print(f"wrote {png}")


if __name__ == "__main__":
    main()
