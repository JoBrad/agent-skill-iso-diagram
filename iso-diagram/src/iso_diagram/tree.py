"""iso-tree: an isometric hierarchy of slabs with color-keyed callout cards.

Containment runs top to bottom. Connectors are orthogonal with at most one bend and touch
shapes only at their outlines. A story path is shown by emphasizing the connectors it uses.
"""

import itertools
import math

from collections.abc import Iterator, Sequence

from iso_diagram.checks import Label, Registry, Surface
from iso_diagram.iso import (
    Point,
    Slab,
    badge,
    connector,
    dot,
    icon,
    plane_matrix,
    svg_doc,
    text,
)
from iso_diagram.shared import Spec
from iso_diagram.theme import Theme, Tier


SIZES = [
    (260, 34),
    (150, 26),
    (110, 22),
    (90, 20),
]  # footprint and thickness by size step
STACK_TILE = (
    70,
    130,
    22,
)  # stacked leaf tiles: narrow along x, long along y (labels run along y)
STACK_STEP = (85, 42)  # screen offset between stacked tiles
GAP_X = 75  # screen gap between sibling subtrees
GAP_Y = 100  # screen gap between a level's bottom and the next level's top
CARD_W = 650


class Node:
    """One node of a tree spec, its place in the hierarchy, and its slab once laid out."""

    def __init__(self, spec: Spec, depth: int, parent: "Node | None" = None) -> None:
        """Build a node and its children from spec."""
        self.id = spec["id"]
        self.label = spec.get("label", self.id)
        self.sublabel = spec.get("sublabel")
        self.mono = spec.get("mono", False)
        self.mono_sub = spec.get("mono_sublabel", False)
        self.desc = spec.get("desc")
        self.slot = spec.get("slot")
        self.depth, self.parent = depth, parent
        self.children = [Node(c, depth + 1, self) for c in spec.get("children", [])]
        self.stacked = False
        # Set by build() during layout; nothing reads it before then.
        self.slab: Slab

    def walk(self) -> Iterator["Node"]:
        """Yield this node and every descendant, depth first."""
        yield self
        for c in self.children:
            yield from c.walk()


def footprint(node: Node) -> tuple[int, int, int]:
    """Return a node's slab size (w, d, h): a stacked tile, or its size step's."""
    if node.parent is not None and node.parent.stacked:
        return STACK_TILE
    size, h = SIZES[min(size_step(node), len(SIZES) - 1)]
    return (size, size, h)


def size_step(node: Node) -> int:
    """Return a node's size step: an only child keeps its parent's, a fan-out steps down."""
    if node.parent is None:
        return 0
    return size_step(node.parent) + (0 if len(node.parent.children) == 1 else 1)


def screen_width(node: Node) -> float:
    """Return the screen width of a node's slab."""
    w, d, _ = footprint(node)
    return (w + d) * math.cos(math.radians(30))


def subtree_width(node: Node) -> float:
    """Return the screen width a node's subtree needs, gaps included."""
    own = screen_width(node)
    if not node.children:
        return own
    if node.stacked:
        return max(
            own,
            screen_width(node.children[0]) + STACK_STEP[0] * (len(node.children) - 1),
        )
    return max(
        own,
        sum(subtree_width(c) for c in node.children) + GAP_X * (len(node.children) - 1),
    )


def place_x(node: Node, center: float, xs: dict[str, float]) -> None:
    """Set the screen x of node and its subtree in xs, centered on center."""
    xs[node.id] = center
    if not node.children:
        return
    if node.stacked:
        n = len(node.children)
        for i, c in enumerate(node.children):
            xs[c.id] = center + STACK_STEP[0] * (i - (n - 1) / 2)
        return
    total = sum(subtree_width(c) for c in node.children) + GAP_X * (
        len(node.children) - 1
    )
    left = center - total / 2
    for c in node.children:
        wdt = subtree_width(c)
        place_x(c, left + wdt / 2, xs)
        left += wdt + GAP_X


def build(spec: Spec, theme: Theme) -> tuple[str, Registry, Point]:
    """Lay out and draw an iso-tree spec; return the SVG, its registry, and its size."""
    reg = Registry(theme)
    root = Node(spec["root"], 0)
    nodes = {n.id: n for n in root.walk()}
    for n in nodes.values():
        n.stacked = (
            spec.get("stack_leaves", True)
            and len(n.children) >= 2
            and all(not c.children for c in n.children)
        )
    depth_count = max(n.depth for n in nodes.values()) + 1
    slots = theme.level_slots(depth_count)
    levels = [[n for n in nodes.values() if n.depth == d] for d in range(depth_count)]

    # Vertical placement, level by level.
    ys = {}
    root_w, root_d, _ = footprint(root)
    ys[0] = 80 + (root_w + root_d) / 2 * 0.5
    for d in range(1, depth_count):
        prev = levels[d - 1]
        bottom = max(
            ys[d - 1] + (footprint(n)[0] + footprint(n)[1]) / 2 * 0.5 + footprint(n)[2]
            for n in prev
        )
        lvl = levels[d]
        same = (
            all(len(p.children) == 1 for p in prev)
            and len(lvl) == len(prev)
            and all(footprint(n)[:2] == footprint(n.parent)[:2] for n in lvl)
        )
        if same:
            ys[d] = ys[d - 1] + 0.92 * footprint(lvl[0])[0]
        else:
            half = max((footprint(n)[0] + footprint(n)[1]) / 2 * 0.5 for n in lvl)
            ys[d] = bottom + GAP_Y + half

    # Horizontal placement, then shift right so the left margin and the source fit.
    xs = {}
    place_x(root, subtree_width(root) / 2, xs)
    source = spec.get("source")
    for n in nodes.values():
        w, d, h = footprint(n)
        y = ys[n.depth]
        if n.parent is not None and n.parent.stacked:
            y += STACK_STEP[1] * (
                n.parent.children.index(n) - (len(n.parent.children) - 1) / 2
            )
        n.slab = Slab(
            name=n.id,
            cx=xs[n.id],
            cy=y,
            w=w,
            d=d,
            h=h,
            r=12 if (w, d, h) == STACK_TILE else 18,
        )
    min_x = min(min(p[0] for p in n.slab.body) for n in nodes.values())
    shift = 55 - min_x
    if source:
        shift = max(shift, 300 - root.slab.vertex("left")[0])
    for n in nodes.values():
        s = n.slab
        n.slab = reg.slab(
            Slab(name=n.id, cx=s.cx + shift, cy=s.cy, w=s.w, d=s.d, h=s.h, r=s.r)
        )
    tree_right = max(max(p[0] for p in n.slab.body) for n in nodes.values())
    tree_bottom = max(max(p[1] for p in n.slab.body) for n in nodes.values())

    tiers = {n.id: theme.tier(n.slot or slots[n.depth]) for n in nodes.values()}
    out, markers = [], []

    # Slabs: deepest level first, back to front, so parents overlap their children.
    for d in reversed(range(depth_count)):
        out.extend(
            n.slab.shadow(dy=30 if d >= 2 else 40)
            for n in sorted(levels[d], key=lambda k: k.slab.cy)
        )
    for d in reversed(range(depth_count)):
        out.extend(
            draw_node(n=n, t=tiers[n.id], theme=theme, reg=reg)
            for n in sorted(levels[d], key=lambda k: k.slab.cy)
        )

    # Connectors.
    path = spec.get("path", [])
    path_pairs = set(itertools.pairwise(path))
    placed = []
    lines = []
    for n in nodes.values():
        for c in n.children:
            pts = route_parent_child(p=n.slab, q=c.slab, slabs=reg.slabs, placed=placed)
            if pts is None:
                reg.issues.append(f"route: no clean route from '{n.id}' to '{c.id}'")
                continue
            placed.append(pts)
            reg.connector(
                name=f"{n.id}->{c.id}", points=pts, source=n.slab, target=c.slab
            )
            lines.append((pts, tiers[n.id]["stroke"], (n.id, c.id) in path_pairs))
    for pts, color, on_path in lines:
        if not on_path:
            out.append(
                connector(
                    points=pts,
                    color=color,
                    width=1.5,
                    arrow=False,
                    opacity=theme.muted_opacity,
                )
            )
    for pts, color, on_path in lines:
        if on_path:
            out.append(connector(points=pts, color=color, width=3))
            markers.append(color)

    flow = theme.flow
    steps = []
    if source:
        first = (
            nodes[path[1]]
            if path and path[0] == source["id"] and len(path) > 1
            else root
        )
        sx, sy = 90, 62
        out.append(
            f'<g transform="translate({sx},{sy})">{icon(name=source.get("icon", "globe"), color=flow["text"], size=52)}</g>'
        )
        out.append(
            text(
                x=sx + 40,
                y=sy + 8,
                s=source.get("label", source["id"]),
                font=theme.sans,
                size=22,
                fill=flow["text"],
                weight=600,
            )
        )
        _lx, ly = first.slab.vertex("left")
        y_in = ly + first.slab.h * 0.45
        x_in = first.slab.hspan(y_in)[0]
        pts = [(sx, sy + 38), (sx, y_in), (x_in, y_in)]
        reg.connector(name=f"{source['id']}->{first.id}", points=pts, target=first.slab)
        placed.append(pts)
        out.append(connector(points=pts, color=flow["text"], width=3))
        markers.append(flow["text"])
        steps.append((sx - 32, (sy + 38 + y_in) / 2, flow["text"]))
    elif path:
        steps.append(None)

    for f in spec.get("flows", []):
        a, b = nodes[f["from"]].slab, nodes[f["to"]].slab
        pts = route_flow(a=a, b=b, slabs=reg.slabs, placed=placed)
        if pts is None:
            reg.issues.append(
                f"route: no clean route for flow '{a.name}' to '{b.name}'"
            )
            continue
        placed.append(pts)
        color = tiers[f["from"]]["stroke"]
        reg.connector(name=f"{a.name}=>{b.name}", points=pts, source=a, target=b)
        out.append(connector(points=pts, color=color, width=3))
        markers.append(color)
        longest = max(itertools.pairwise(pts), key=lambda s: math.dist(*s))
        mx, my = (
            (longest[0][0] + longest[1][0]) / 2,
            (longest[0][1] + longest[1][1]) / 2,
        )
        steps.append((mx, my, color))
        if f.get("label"):
            out.append(
                text(
                    x=mx,
                    y=my + 34,
                    s=f["label"],
                    font=theme.mono,
                    size=18,
                    fill=tiers[f["from"]]["text"],
                    weight=500,
                    anchor="middle",
                )
            )
    for i, st in enumerate(steps, start=1):
        if st is not None and len(steps) > 1:
            out.append(badge(x=st[0], y=st[1], n=i, fill=st[2], font=theme.sans))

    # Callout cards with leader lines, one per level that has a card.
    card_x = tree_right + 105
    prev_bottom = 0
    cards_bottom = 0
    level_specs = spec.get("levels", [])
    for d, lvl in enumerate(levels):
        card = level_specs[d].get("card") if d < len(level_specs) else None
        if not card:
            continue
        n = max(lvl, key=lambda k: k.slab.vertex("right")[0])
        color = tiers[n.id]["stroke"]
        rx, ry = n.slab.vertex("right")
        tx, ty = n.slab.vertex("top")
        lead = None
        for t in (0.15, 0.3, 0.45, 0.6):
            ex, ey = rx + (tx - rx) * t, ry + (ty - ry) * t  # along the top-right edge
            px, py = (
                ex + (n.slab.cx - ex) * 0.15,
                ey + (n.slab.cy - ey) * 0.15,
            )  # nudged onto the face
            if not any(
                abs(py - a[1]) < 22 and abs(a[1] - b[1]) < 0.5 and max(a[0], b[0]) > px
                for pts in placed
                for a, b in itertools.pairwise(pts)
            ):
                lead = (px, py)
                break
        if lead is None:
            lead = (rx - 25, ry)
            reg.issues.append(f"leader: '{n.id}' leader runs close to a connector")
        rows = math.ceil(len(card.get("items", [])) / 2)
        h = 104 + rows * 38 if rows else 90
        top = max(prev_bottom + 30, 40, lead[1] - 90)
        if not top + 24 <= lead[1] <= top + h - 24:
            reg.issues.append(
                f"leader: '{card.get('title')}' card cannot sit level with its leader"
            )
        out.append(
            f'<line x1="{lead[0]:.1f}" y1="{lead[1]:.1f}" x2="{card_x:.1f}" y2="{lead[1]:.1f}" '
            f'stroke="{color}" stroke-width="2.5"/>'
        )
        out.append(dot(x=lead[0], y=lead[1], color=color))
        out.append(
            callout_card(
                x=card_x,
                y=top,
                w=CARD_W,
                h=h,
                color=color,
                title=card.get("title", n.label),
                items=card.get("items", []),
                theme=theme,
            )
        )
        prev_bottom = top + h
        cards_bottom = max(cards_bottom, top + h)

    width = (
        card_x + CARD_W + 40
        if any(level_specs and l.get("card") for l in level_specs)
        else tree_right + 60
    )
    caption_y = max(tree_bottom, cards_bottom) + 70
    caption = spec.get("caption") or default_caption(spec)
    out.append(
        text(
            x=40,
            y=caption_y,
            s=caption,
            font=theme.sans,
            size=18,
            fill=theme.ink["caption"],
        )
    )
    height = caption_y + 30
    return (
        svg_doc(
            width=width,
            height=height,
            body="".join(out),
            marker_colors=markers,
            background=theme.background,
            title=spec.get("title"),
            desc=spec.get("story"),
        ),
        reg,
        (width, height),
    )


def default_caption(spec: Spec) -> str:
    """Return the story, plus a legend when the spec draws a path."""
    parts = [spec.get("story", "")]
    if spec.get("path"):
        parts.append("Faint lines: contains. Bold arrows: the path, steps numbered.")
    return " ".join(p for p in parts if p)


def draw_node(*, n: Node, t: Tier, theme: Theme, reg: Registry) -> str:
    """Return a node's slab and labels, shrinking the label to fit, and register them."""
    s = n.slab
    lines = [
        (
            n.label,
            max(20, min(46, round(min(s.w, s.d) * 0.17)))
            if not n.parent or not n.parent.stacked
            else 20,
            600,
            n.mono,
        )
    ]
    label, size, weight, mono = lines[0]
    while (
        size > theme.min_surface_text
        and theme.measure(s=label, size=size, mono=mono, weight=weight) > s.d - 28
    ):
        size -= 1  # shrink to fit the surface, never below the floor; checks flag what still overflows
    lines[0] = (label, size, weight, mono)
    if n.sublabel:
        lines.append((n.sublabel, 20, 500 if n.mono_sub else 400, n.mono_sub))
    gap = 6
    block = sum(size for _, size, _, _ in lines) + gap * (len(lines) - 1)
    front = s.w * 0.06 if len(lines) > 1 else 0
    y = front - block / 2
    texts = []
    for s_text, size, weight, mono in lines:
        cy = y + size / 2
        font = theme.mono if mono else theme.sans
        texts.append(
            text(
                x=0,
                y=cy,
                s=s_text,
                font=font,
                size=size,
                fill=t["text"],
                weight=weight,
                anchor="middle",
                baseline="central",
            )
        )
        length = theme.measure(s=s_text, size=size, mono=mono, weight=weight)
        reg.label(
            Label(
                surface=Surface(name=s.name, w=s.w, d=s.d),
                text=s_text,
                center=(cy, 0),
                size=size,
                length=length,
            )
        )
        y += size + gap
    title = f"<title>{n.label}</title>" + (f"<desc>{n.desc}</desc>" if n.desc else "")
    return (
        f"<g>{title}{s.svg(top=t['top'], side=t['side'], stroke=t['stroke'])}"
        f'<g transform="{plane_matrix(s.cx, s.cy)} rotate(-90)">{"".join(texts)}</g></g>'
    )


def callout_card(
    *,
    x: float,
    y: float,
    w: float,
    h: float,
    color: str,
    title: str,
    items: list[str],
    theme: Theme,
) -> str:
    """Return a callout card: a title over its items in two columns."""
    out = [
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w}" height="{h}" rx="22" fill="#FFFFFF" '
        f'stroke="{color}" stroke-width="3"/>',
        text(
            x=x + 30,
            y=y + 52,
            s=title,
            font=theme.sans,
            size=32,
            fill=color,
            weight=600,
        ),
    ]
    per_col = math.ceil(len(items) / 2) if items else 0
    for i, item in enumerate(items):
        cx = x + 30 + (i // per_col) * (w - 60) / 2
        out.append(
            text(
                x=cx,
                y=y + 100 + (i % per_col) * 38,
                s=item,
                font=theme.sans,
                size=19,
                fill=theme.ink["body"],
            )
        )
    return "".join(out)


# --- routing --------------------------------------------------------------------------------


def clear(
    *,
    pts: Sequence[Point],
    slabs: list[Slab],
    placed: list[list[Point]],
    spacing: float = 12,
) -> bool:
    """Return whether a route crosses no slab and keeps clear of parallel connectors."""
    total = sum(math.dist(a, b) for a, b in itertools.pairwise(pts))
    walked = 0.0
    for a, b in itertools.pairwise(pts):
        seg = math.dist(a, b)
        n = max(1, int(seg / 3))
        for i in range(n + 1):
            dd = walked + seg * i / n
            if dd < 3 or dd > total - 3:
                continue
            x, y = a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n
            if any(s.contains(x, y, margin=1) for s in slabs):
                return False
        walked += seg
    for other in placed:
        for a, b in itertools.pairwise(pts):
            for c, d in itertools.pairwise(other):
                if (
                    abs(a[0] - b[0]) < 0.5
                    and abs(c[0] - d[0]) < 0.5
                    and abs(a[0] - c[0]) < spacing
                ) and min(max(a[1], b[1]), max(c[1], d[1])) > max(
                    min(a[1], b[1]), min(c[1], d[1])
                ):
                    return False
                if (
                    abs(a[1] - b[1]) < 0.5
                    and abs(c[1] - d[1]) < 0.5
                    and abs(a[1] - c[1]) < spacing
                ) and min(max(a[0], b[0]), max(c[0], d[0])) > max(
                    min(a[0], b[0]), min(c[0], d[0])
                ):
                    return False
    return True


def route_parent_child(
    *, p: Slab, q: Slab, slabs: list[Slab], placed: list[list[Point]]
) -> list[Point] | None:
    """Straight down if the shapes line up, else out a side corner and down: one bend."""
    qx = q.vertex("top")[0] + 30
    offsets = sorted(range(-240, 241, 10), key=lambda k: (abs(k), k))
    for k in offsets:
        x = qx + k
        ps, qs = p.vspan(x), q.vspan(x)
        if (
            not ps
            or not qs
            or qs[0] - ps[1] < 40
            or not (well_inside(p, x) and well_inside(q, x))
        ):
            continue
        pts = [(x, ps[1]), (x, qs[0])]
        if clear(pts=pts, slabs=slabs, placed=placed):
            return pts
    side = "left" if q.cx < p.cx else "right"
    _vx, vy = p.vertex(side)
    y = vy + p.h * 0.6
    xe = p.hspan(y)[0 if side == "left" else 1]
    for k in offsets:
        x = qx + k
        qs = q.vspan(x)
        if (
            not qs
            or not well_inside(q, x)
            or qs[0] - y < 40
            or (side == "left" and x > xe - 30)
            or (side == "right" and x < xe + 30)
        ):
            continue
        pts = [(xe, y), (x, y), (x, qs[0])]
        if clear(pts=pts, slabs=slabs, placed=placed):
            return pts
    return None


def well_inside(slab: Slab, x: float, margin: float = 30) -> bool:
    """Keep vertical connectors off a shape's far corners, where they would graze its silhouette."""
    xs = [p[0] for p in slab.body]
    return min(xs) + margin <= x <= max(xs) - margin


def route_flow(
    *, a: Slab, b: Slab, slabs: list[Slab], placed: list[list[Point]]
) -> list[Point] | None:
    """Route a sideways flow between two shapes: straight across, else under and up."""
    left_to_right = a.cx < b.cx
    lo = max(min(p[1] for p in a.body), min(p[1] for p in b.body))
    hi = min(max(p[1] for p in a.body), max(p[1] for p in b.body))
    side = (
        b.vertex("left" if left_to_right else "right")[1] + b.h / 2
    )  # level with the target's side corner
    for k in sorted(range(-60, 61, 2), key=abs):
        y = side + k
        if not lo + 4 < y < hi - 4:
            continue
        sa, sb = a.hspan(y), b.hspan(y)
        if sa and sb:
            x1, x2 = (sa[1], sb[0]) if left_to_right else (sa[0], sb[1])
            pts = [(x1, y), (x2, y)]
            if (
                abs(x2 - x1) > 40
                and (x2 > x1) == left_to_right
                and clear(pts=pts, slabs=slabs, placed=placed)
            ):
                return pts
    xa, ya = a.vertex("bottom")
    xb, yb = b.vertex("bottom")
    y = max(ya + a.h, yb + b.h) + 30
    pts = [(xa, ya + a.h), (xa, y), (xb, y), (xb, yb + b.h)]
    return pts if clear(pts=pts, slabs=slabs, placed=placed) else None
