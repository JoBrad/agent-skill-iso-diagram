"""Layout checks.

Each rule here is one the skill promises; a layout records what it drew
and check() reports every place a rule breaks, so problems surface before anyone sees them.
"""

import itertools
import math


INSET = 16  # plane units between a child and its parent's edge
LABEL_MARGIN = 4  # plane units between a label and the edge of its surface


class Registry:
    def __init__(self, theme) -> None:
        self.theme = theme
        self.slabs = []
        self.children = []  # (parent, pw, pd, child, (x, y, w, d))
        self.labels = []  # (surface, sw, sd, text, (x, y), size, along_y, length)
        self.connectors = []  # (name, points, source slab or None, target slab or None)
        self.issues = []

    def slab(self, s):
        self.slabs.append(s)
        return s

    def child(self, parent, pw, pd, name, rect) -> None:
        self.children.append((parent, pw, pd, name, rect))

    def label(self, surface, sw, sd, s, center, size, length, along_y=True) -> None:
        self.labels.append((surface, sw, sd, s, center, size, along_y, length))

    def connector(self, name, points, source=None, target=None) -> None:
        self.connectors.append((name, points, source, target))

    def check(self, width, height):
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
            out.extend(self._connector_issues(name, pts, source, target))
        for s in self.slabs:
            xs, ys = [p[0] for p in s.body], [p[1] for p in s.body]
            if min(xs) < 0 or min(ys) < 0 or max(xs) > width or max(ys) > height:
                out.append(f"canvas: '{s.name}' extends past the canvas")
        return out

    def _connector_issues(self, name, pts, source, target):
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
