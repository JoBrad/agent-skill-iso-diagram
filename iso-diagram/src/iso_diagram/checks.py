"""Layout checks.

Each rule here is one the skill promises; a layout records what it drew
and check() reports every place a rule breaks, so problems surface before anyone sees them.
"""

import itertools
import math

from collections.abc import Sequence

from iso_diagram.iso import Point, Slab
from iso_diagram.theme import Theme


INSET = 16  # plane units between a child and its parent's edge
LABEL_MARGIN = 4  # plane units between a label and the edge of its surface


Rect = tuple[float, float, float, float]  # plane x, y, w, d


class Registry:
    """Shapes, labels, and connectors a layout drew, checked against the layout rules.

    The layout records each element as it draws it, and adds to `issues` any problem it
    hits along the way. `check()` then returns every rule the drawing breaks.
    """

    def __init__(self, theme: Theme) -> None:
        """Start an empty registry; theme supplies the text-size floor."""
        self.theme = theme
        self.slabs: list[Slab] = []
        # (parent, pw, pd, child, (x, y, w, d))
        self.children: list[tuple[str, float, float, str, Rect]] = []
        # (surface, sw, sd, text, (x, y), size, along_y, length)
        self.labels: list[tuple[str, float, float, str, Point, float, bool, float]] = []
        # (name, points, source slab or None, target slab or None)
        self.connectors: list[
            tuple[str, Sequence[Point], Slab | None, Slab | None]
        ] = []
        self.issues: list[str] = []

    def slab(self, s: Slab) -> Slab:
        """Record a slab and return it."""
        self.slabs.append(s)
        return s

    def child(
        self,
        *,
        parent: str,
        pw: float,
        pd: float,
        name: str,
        rect: Rect,
    ) -> None:
        """Record a child rect drawn on a pw x pd parent, for the inset rule."""
        self.children.append((parent, pw, pd, name, rect))

    def label(
        self,
        *,
        surface: str,
        sw: float,
        sd: float,
        s: str,
        center: Point,
        size: float,
        length: float,
        along_y: bool = True,
    ) -> None:
        """Record a label centered on a sw x sd surface, for the size and fit rules."""
        self.labels.append((surface, sw, sd, s, center, size, along_y, length))

    def connector(
        self,
        *,
        name: str,
        points: Sequence[Point],
        source: Slab | None = None,
        target: Slab | None = None,
    ) -> None:
        """Record a connector and the slabs its ends should sit on."""
        self.connectors.append((name, points, source, target))

    def check(self, width: float, height: float) -> list[str]:
        """Return every rule the recorded layout breaks on a width x height canvas."""
        out = list(self.issues)
        for parent, pw, pd, name, (x, y, w, d) in self.children:
            gap = min(
                pw / 2 - (x + w / 2),
                pw / 2 - (-x + w / 2),
                pd / 2 - (y + d / 2),
                pd / 2 - (-y + d / 2),
            )
            if gap < INSET:
                out.append(
                    f"inset: '{name}' is {gap:.0f} units from the edge of '{parent}' (needs {INSET})"
                )
        for surface, sw, sd, s, (x, y), size, along_y, length in self.labels:
            if size < self.theme.min_surface_text:
                out.append(
                    f"text: '{s}' on '{surface}' is {size}px (floor {self.theme.min_surface_text})"
                )
            half_len, half_h = length / 2, size * 0.42
            hx, hy = (half_h, half_len) if along_y else (half_len, half_h)
            if (
                abs(x) + hx > sw / 2 - LABEL_MARGIN
                or abs(y) + hy > sd / 2 - LABEL_MARGIN
            ):
                out.append(f"surface: label '{s}' runs off '{surface}'")
        for name, pts, source, target in self.connectors:
            out.extend(
                self._connector_issues(name=name, pts=pts, source=source, target=target)
            )
        for s in self.slabs:
            xs, ys = [p[0] for p in s.body], [p[1] for p in s.body]
            if min(xs) < 0 or min(ys) < 0 or max(xs) > width or max(ys) > height:
                out.append(f"canvas: '{s.name}' extends past the canvas")
        return out

    def _connector_issues(
        self,
        *,
        name: str,
        pts: Sequence[Point],
        source: Slab | None,
        target: Slab | None,
    ) -> list[str]:
        out = []
        bends = sum(
            1
            for a, b, c in zip(pts, pts[1:], pts[2:], strict=False)
            if abs((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])) > 1e-6
        )
        if any(
            abs(a[0] - b[0]) > 0.5 and abs(a[1] - b[1]) > 0.5
            for a, b in itertools.pairwise(pts)
        ):
            out.append(f"route: '{name}' has a diagonal segment")
        if bends > 1:
            out.append(f"route: '{name}' has {bends} bends")
        total = sum(math.dist(a, b) for a, b in itertools.pairwise(pts))
        walked = 0.0
        for a, b in itertools.pairwise(pts):
            seg = math.dist(a, b)
            n = max(1, int(seg / 2))
            for i in range(n + 1):
                t = i / n
                d = walked + seg * t
                if d < 3 or d > total - 3:
                    continue
                x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                for s in self.slabs:
                    if s.contains(x, y, margin=1):
                        out.append(
                            f"connector: '{name}' crosses '{s.name}' near ({x:.0f},{y:.0f})"
                        )
                        break
                else:
                    continue
                break
            walked += seg
        for end, prev, slab, what in (
            (pts[-1], pts[-2], target, "end"),
            (pts[0], pts[1], source, "start"),
        ):
            if slab is None:
                continue
            dx, dy = end[0] - prev[0], end[1] - prev[1]
            k = 4 / max(math.hypot(dx, dy), 1e-6)
            inside = slab.contains(end[0] + dx * k, end[1] + dy * k)
            outside = not slab.contains(end[0] - dx * k, end[1] - dy * k)
            if not (inside and outside):
                out.append(
                    f"connector: '{name}' {what} does not sit on the outline of '{slab.name}'"
                )
        return out
