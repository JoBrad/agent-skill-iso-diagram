"""Spec and layout checks.

spec_issues() catches a spec that names something it never defines, before layout
trips over it. Each layout rule here is one the skill promises; a layout records what it
drew and check() reports every place a rule breaks, so problems surface before anyone
sees them.
"""

import itertools
import math

from collections import Counter
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from iso_diagram.iso import Point, Slab, Spec
from iso_diagram.theme import Theme


INSET = 16  # plane units between a child and its parent's edge
LABEL_MARGIN = 4  # plane units between a label and the edge of its surface
RESOURCE_COUNTS = (1, 2, 3)  # iso-stack draws a resource as 1 to 3 slabs


Rect = tuple[float, float, float, float]  # plane x, y, w, d
# Values a spec reference may take, and what they name: ({"web", "db"}, "column").
Known = tuple[Collection[object], str]


@dataclass(frozen=True)
class Surface:
    """A flat face that children and labels sit on: its name and plane size."""

    name: str
    w: float
    d: float


@dataclass(frozen=True)
class Label:
    """Text lying on a surface, as the text-size and fit rules see it."""

    surface: Surface
    text: str
    center: Point  # plane coordinates, from the surface's center
    size: float
    length: float  # rendered width, from Theme.measure()
    along_y: bool = True  # text runs along the surface's y axis


class Registry:
    """Shapes, labels, and connectors a layout drew, checked against the layout rules.

    The layout records each element as it draws it, and adds to `issues` any problem it
    hits along the way. `check()` then returns every rule the drawing breaks.
    """

    def __init__(self, theme: Theme) -> None:
        """Start an empty registry; theme supplies the text-size floor."""
        self.theme = theme
        self.slabs: list[Slab] = []
        # (parent, child name, (x, y, w, d))
        self.children: list[tuple[Surface, str, Rect]] = []
        self.labels: list[Label] = []
        # (text, left, right, what it must stay within, (min x, max x) or None for the canvas)
        self.texts: list[tuple[str, float, float, str, tuple[float, float] | None]] = []
        # (name, points, source slab or None, target slab or None)
        self.connectors: list[
            tuple[str, Sequence[Point], Slab | None, Slab | None]
        ] = []
        self.issues: list[str] = []

    def slab(self, s: Slab) -> Slab:
        """Record a slab and return it."""
        self.slabs.append(s)
        return s

    def child(self, *, parent: Surface, name: str, rect: Rect) -> None:
        """Record a child rect drawn on parent, for the inset rule."""
        self.children.append((parent, name, rect))

    def label(self, label: Label) -> None:
        """Record a label, for the text-size and fit rules."""
        self.labels.append(label)

    def text(
        self,
        *,
        text: str,
        left: float,
        right: float,
        within: str = "canvas",
        box: tuple[float, float] | None = None,
    ) -> None:
        """Record screen text spanning left to right, for the fit rule; box None is the canvas."""
        self.texts.append((text, left, right, within, box))

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

    def check(
        self,
        width: float,
        height: float,
    ) -> list[str]:
        """Return every rule the recorded layout breaks on a width x height canvas."""
        out = list(self.issues)
        for parent, name, (x, y, w, d) in self.children:
            gap = min(
                parent.w / 2 - (x + w / 2),
                parent.w / 2 - (-x + w / 2),
                parent.d / 2 - (y + d / 2),
                parent.d / 2 - (-y + d / 2),
            )
            if gap < INSET:
                out.append(
                    f"inset: '{name}' is {gap:.0f} units from the edge of "
                    f"'{parent.name}' (needs {INSET})"
                )
        for lb in self.labels:
            surface = lb.surface
            if lb.size < self.theme.min_surface_text:
                out.append(
                    f"text: '{lb.text}' on '{surface.name}' is {lb.size}px "
                    f"(floor {self.theme.min_surface_text})"
                )
            half_len, half_h = lb.length / 2, lb.size * 0.42
            hx, hy = (half_h, half_len) if lb.along_y else (half_len, half_h)
            x, y = lb.center
            if (
                abs(x) + hx > surface.w / 2 - LABEL_MARGIN
                or abs(y) + hy > surface.d / 2 - LABEL_MARGIN
            ):
                out.append(f"surface: label '{lb.text}' runs off '{surface.name}'")
        for name, pts, source, target in self.connectors:
            out.extend(
                self._connector_issues(name=name, pts=pts, source=source, target=target)
            )
        for s in self.slabs:
            xs, ys = [p[0] for p in s.body], [p[1] for p in s.body]
            if min(xs) < 0 or min(ys) < 0 or max(xs) > width or max(ys) > height:
                out.append(f"canvas: '{s.name}' extends past the canvas")
        out.extend(self._fit_issues(width))
        return out

    def _fit_issues(self, width: float) -> list[str]:
        out = []
        for text, left, right, within, box in self.texts:
            lo, hi = box or (0, width)
            if left < lo or right > hi:
                out.append(f"fit: '{text}' runs past the {within}")
        return out

    def _connector_issues(
        self,
        *,
        name: str,
        pts: Sequence[Point],
        source: Slab | None,
        target: Slab | None,
    ) -> list[str]:
        return [
            *_route_issues(name=name, pts=pts),
            *self._crossing_issues(name=name, pts=pts),
            *_endpoint_issues(name=name, pts=pts, source=source, target=target),
        ]

    def _crossing_issues(self, *, name: str, pts: Sequence[Point]) -> list[str]:
        # Sample every 2 units, skipping 3 at each end where the connector meets its
        # slabs; report at most one crossing per segment.
        out = []
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
                hit = next((s for s in self.slabs if s.contains(x, y, margin=1)), None)
                if hit is not None:
                    out.append(
                        f"connector: '{name}' crosses '{hit.name}' near ({x:.0f},{y:.0f})"
                    )
                    break
            walked += seg
        return out


def _route_issues(*, name: str, pts: Sequence[Point]) -> list[str]:
    out = []
    if any(
        abs(a[0] - b[0]) > 0.5 and abs(a[1] - b[1]) > 0.5
        for a, b in itertools.pairwise(pts)
    ):
        out.append(f"route: '{name}' has a diagonal segment")
    bends = sum(
        1
        for a, b, c in zip(pts, pts[1:], pts[2:], strict=False)
        if abs((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])) > 1e-6
    )
    if bends > 1:
        out.append(f"route: '{name}' has {bends} bends")
    return out


def _endpoint_issues(
    *,
    name: str,
    pts: Sequence[Point],
    source: Slab | None,
    target: Slab | None,
) -> list[str]:
    # An end sits on the outline when a step forward lands inside the slab and a step
    # back lands outside it.
    out = []
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


# --- spec checks ----------------------------------------------------------------------


def spec_issues(spec: Spec) -> list[str]:
    """Return every missing key and dangling reference in a spec of a known style."""
    check = {"iso-tree": _tree_spec_issues, "iso-stack": _stack_spec_issues}
    return [f"spec: {i}" for i in check[spec["style"]](spec)]


def _missing(obj: Spec, keys: Sequence[str], where: str) -> list[str]:
    prefix = f"{where} is missing" if where else "missing"
    return [f"{prefix} '{k}'" for k in keys if obj.get(k) is None]


def _refs(obj: Spec, *, where: str, refs: dict[str, Known]) -> list[str]:
    out = []
    for key, (known, what) in refs.items():
        if obj.get(key) is None:
            out.append(f"{where} is missing '{key}'")
        elif obj[key] not in known:
            out.append(f"{where}.{key} names no {what} '{obj[key]}'")
    return out


def _duplicates(ids: list[str], what: str) -> list[str]:
    return [
        f"{what} id '{i}' is used {n} times; ids must be unique"
        for i, n in Counter(ids).items()
        if n > 1
    ]


def _tree_spec_issues(spec: Spec) -> list[str]:
    if spec.get("root") is None:
        return ["missing 'root'"]
    out: list[str] = []
    ids: list[str] = []

    def walk(node: Spec, where: str) -> None:
        out.extend(_missing(node, ["id"], where))
        if "id" in node:
            ids.append(node["id"])
        for i, child in enumerate(node.get("children", [])):
            walk(child, f"{where}.children[{i}]")

    walk(spec["root"], "root")
    out += _duplicates(ids, "node")
    nodes: Known = (set(ids), "node")
    for i, flow in enumerate(spec.get("flows", [])):
        out += _refs(flow, where=f"flows[{i}]", refs={"from": nodes, "to": nodes})
    source = spec.get("source")
    if source:
        out += _missing(source, ["id"], "source")
    on_path = set(ids) | ({source.get("id")} if source else set())
    out += [
        f"path[{i}] names no node '{p}'"
        for i, p in enumerate(spec.get("path", []))
        if p not in on_path
    ]
    return out


def _stack_spec_issues(spec: Spec) -> list[str]:
    missing = _missing(spec, ["columns", "layers"], "")
    if missing:
        return missing
    layers = spec["layers"]
    out: list[str] = []
    for i, layer in enumerate(layers):
        out += _missing(layer, ["id", "title"], f"layers[{i}]")
    ids = [layer["id"] for layer in layers if "id" in layer]
    out += _duplicates(ids, "layer")
    columns: Known = (set(spec["columns"]), "column")
    for i, layer in enumerate(layers):
        out += _layer_item_issues(layer, where=f"layers[{i}]", columns=columns)
    out += _step_issues(
        spec.get("steps", []), columns=columns, layers=(set(ids), "layer")
    )
    if spec.get("source"):
        out += _refs(spec["source"], where="source", refs={"column": columns})
    return out


def _layer_item_issues(layer: Spec, *, where: str, columns: Known) -> list[str]:
    out = []
    for kind in ("zones", "markers", "resources"):
        for j, item in enumerate(layer.get(kind, [])):
            at = f"{where}.{kind}[{j}]"
            out += _refs(item, where=at, refs={"column": columns})
            out += _missing(
                item, ["label", "icon"] if kind == "resources" else ["label"], at
            )
            count = item.get("count", 1)
            if kind == "resources" and count not in RESOURCE_COUNTS:
                out.append(f"{at}.count is {count}; use 1, 2, or 3")
    return out


def _step_issues(steps: list[Spec], *, columns: Known, layers: Known) -> list[str]:
    out = []
    for i, step in enumerate(steps):
        refs = (
            {"column": columns, "to": layers}
            if step.get("from") == "source"
            else {"from": columns, "to": columns, "via": layers, "at": layers}
        )
        out += _refs(step, where=f"steps[{i}]", refs=refs)
    return out
