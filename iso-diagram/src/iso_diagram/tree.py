"""iso-tree: an isometric hierarchy of slabs with color-keyed callout cards.

Containment runs top to bottom. Connectors are orthogonal with at most one bend and touch
shapes only at their outlines. A story path is shown by emphasizing the connectors it uses.
"""

import itertools
import math

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

from iso_diagram.checks import Label, Registry, Surface
from iso_diagram.iso import (
    Point,
    Slab,
    Spec,
    TextStyle,
    badge,
    caption,
    connector,
    dot,
    icon,
    plane_matrix,
    svg_doc,
    text,
)
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
CARD_GAP = 105  # screen gap between the tree's right edge and its cards


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


@dataclass
class Tree:
    """An iso-tree spec as laid out: its nodes and levels, their colors, and the drawing so far.

    `placed` holds every connector route drawn so far, so later routes and leaders keep
    clear of them. `steps` holds a badge spot (x, y, color) for each step of the story
    path, in order; None marks a step that gets no badge.
    """

    spec: Spec
    theme: Theme
    reg: Registry
    root: Node
    levels: list[list[Node]]
    tiers: dict[str, Tier]
    out: list[str] = field(default_factory=list)
    placed: list[list[Point]] = field(default_factory=list)
    steps: list[tuple[float, float, str] | None] = field(default_factory=list)

    @property
    def nodes(self) -> dict[str, Node]:
        """Every node by id, depth first."""
        return {n.id: n for n in self.root.walk()}


def build(spec: Spec, theme: Theme) -> tuple[str, Registry, Point]:
    """Lay out and draw an iso-tree spec; return the SVG, its registry, and its size."""
    tree = lay_out(spec, theme)
    draw_slabs(tree)
    draw_containment(tree)
    draw_source(tree)
    draw_flows(tree)
    draw_badges(tree)
    slabs = [n.slab for n in tree.root.walk()]
    tree_right = max(max(p[0] for p in s.body) for s in slabs)
    tree_bottom = max(max(p[1] for p in s.body) for s in slabs)
    cards_bottom = draw_cards(tree, card_x=tree_right + CARD_GAP)
    card_right = tree_right + CARD_GAP + CARD_W

    width = tree_right + 60 if cards_bottom is None else card_right + 40
    caption_svg, height = caption(
        s=spec.get("caption") or default_caption(spec),
        top=max(tree_bottom, cards_bottom or 0) + 70,
        width=width,
        theme=theme,
        reg=tree.reg,
    )
    tree.out.append(caption_svg)
    doc = svg_doc(
        size=(width, height),
        body="".join(tree.out),
        background=theme.background,
        title=spec.get("title"),
        desc=spec.get("story"),
    )
    return doc, tree.reg, (width, height)


# --- layout -----------------------------------------------------------------------------


def lay_out(spec: Spec, theme: Theme) -> Tree:
    """Build the node tree, place every slab, and pick each node's colors."""
    reg = Registry(theme)
    root = Node(spec["root"], 0)
    nodes = list(root.walk())
    for n in nodes:
        n.stacked = (
            spec.get("stack_leaves", True)
            and len(n.children) >= 2
            and all(not c.children for c in n.children)
        )
    depth_count = max(n.depth for n in nodes) + 1
    slots = theme.level_slots(depth_count)
    levels = [[n for n in nodes if n.depth == d] for d in range(depth_count)]
    place_slabs(root, ys=level_ys(levels), has_source=bool(spec.get("source")), reg=reg)
    return Tree(
        spec=spec,
        theme=theme,
        reg=reg,
        root=root,
        levels=levels,
        tiers={n.id: theme.tier(n.slot or slots[n.depth]) for n in nodes},
    )


def level_ys(levels: list[list[Node]]) -> list[float]:
    """Return the screen y of each level's slab centers, top level first."""
    root_w, root_d, _ = footprint(levels[0][0])
    ys = [80 + (root_w + root_d) / 2 * 0.5]
    for d in range(1, len(levels)):
        prev, lvl = levels[d - 1], levels[d]
        bottom = max(
            ys[d - 1] + (footprint(n)[0] + footprint(n)[1]) / 2 * 0.5 + footprint(n)[2]
            for n in prev
        )
        # A level of only children the same size as their parents stacks closer.
        same = (
            all(len(p.children) == 1 for p in prev)
            and len(lvl) == len(prev)
            and all(
                n.parent is not None and footprint(n)[:2] == footprint(n.parent)[:2]
                for n in lvl
            )
        )
        if same:
            ys.append(ys[d - 1] + 0.92 * footprint(lvl[0])[0])
        else:
            half = max((footprint(n)[0] + footprint(n)[1]) / 2 * 0.5 for n in lvl)
            ys.append(bottom + GAP_Y + half)
    return ys


def place_slabs(
    root: Node, *, ys: list[float], has_source: bool, reg: Registry
) -> None:
    """Give every node its slab, shifted right so the left margin and the source fit."""
    xs: dict[str, float] = {}
    place_x(root, subtree_width(root) / 2, xs)
    nodes = list(root.walk())
    for n in nodes:
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
    min_x = min(min(p[0] for p in n.slab.body) for n in nodes)
    shift = 55 - min_x
    if has_source:
        shift = max(shift, 300 - root.slab.vertex("left")[0])
    for n in nodes:
        s = n.slab
        n.slab = reg.slab(
            Slab(name=n.id, cx=s.cx + shift, cy=s.cy, w=s.w, d=s.d, h=s.h, r=s.r)
        )


# --- drawing ----------------------------------------------------------------------------


def draw_slabs(tree: Tree) -> None:
    """Draw every slab, deepest level first and back to front, so parents overlap children."""
    by_depth = [
        (d, sorted(lvl, key=lambda k: k.slab.cy)) for d, lvl in enumerate(tree.levels)
    ][::-1]
    for d, lvl in by_depth:
        tree.out.extend(n.slab.shadow(dy=30 if d >= 2 else 40) for n in lvl)
    for _, lvl in by_depth:
        tree.out.extend(
            draw_node(n=n, t=tree.tiers[n.id], theme=tree.theme, reg=tree.reg)
            for n in lvl
        )


def draw_containment(tree: Tree) -> None:
    """Connect each parent to its children: faint lines, bold arrows along the story path."""
    reg = tree.reg
    path_pairs = set(itertools.pairwise(tree.spec.get("path", [])))
    lines = []
    for n in tree.root.walk():
        for c in n.children:
            pts = route_parent_child(
                p=n.slab, q=c.slab, slabs=reg.slabs, placed=tree.placed
            )
            if pts is None:
                reg.issues.append(f"route: no clean route from '{n.id}' to '{c.id}'")
                continue
            tree.placed.append(pts)
            reg.connector(
                name=f"{n.id}->{c.id}", points=pts, source=n.slab, target=c.slab
            )
            lines.append((pts, tree.tiers[n.id]["stroke"], (n.id, c.id) in path_pairs))
    tree.out.extend(
        connector(
            points=pts,
            color=color,
            width=1.5,
            arrow=False,
            opacity=tree.theme.muted_opacity,
        )
        for pts, color, on_path in lines
        if not on_path
    )
    tree.out.extend(
        connector(points=pts, color=color, width=3)
        for pts, color, on_path in lines
        if on_path
    )


def draw_source(tree: Tree) -> None:
    """Draw the source and its feed into the first node on the path, or the root."""
    spec, flow = tree.spec, tree.theme.flow
    source, path = spec.get("source"), spec.get("path", [])
    if not source:
        if path:
            tree.steps.append(None)
        return
    first = tree.root
    if path and path[0] == source["id"] and len(path) > 1:
        first = tree.nodes[path[1]]
    sx, sy = 90, 62
    glyph = icon(name=source.get("icon", "globe"), color=flow["text"], size=52)
    style = TextStyle(font=tree.theme.sans, size=22, fill=flow["text"], weight=600)
    tree.out.append(f'<g transform="translate({sx},{sy})">{glyph}</g>')
    tree.out.append(
        text(x=sx + 40, y=sy + 8, s=source.get("label", source["id"]), style=style)
    )
    _lx, ly = first.slab.vertex("left")
    y_in = ly + first.slab.h * 0.45
    x_in = first.slab.hspan(y_in)[0]
    pts = [(sx, sy + 38), (sx, y_in), (x_in, y_in)]
    tree.reg.connector(
        name=f"{source['id']}->{first.id}", points=pts, target=first.slab
    )
    tree.placed.append(pts)
    tree.out.append(connector(points=pts, color=flow["text"], width=3))
    tree.steps.append((sx - 32, (sy + 38 + y_in) / 2, flow["text"]))


def draw_flows(tree: Tree) -> None:
    """Draw each sideways flow between two nodes, with its label, as a step of the path."""
    nodes, reg = tree.nodes, tree.reg
    for f in tree.spec.get("flows", []):
        a, b = nodes[f["from"]].slab, nodes[f["to"]].slab
        pts = route_flow(a=a, b=b, slabs=reg.slabs, placed=tree.placed)
        if pts is None:
            reg.issues.append(
                f"route: no clean route for flow '{a.name}' to '{b.name}'"
            )
            continue
        tree.placed.append(pts)
        tier = tree.tiers[f["from"]]
        reg.connector(name=f"{a.name}=>{b.name}", points=pts, source=a, target=b)
        tree.out.append(connector(points=pts, color=tier["stroke"], width=3))
        (x0, y0), (x1, y1) = max(itertools.pairwise(pts), key=lambda s: math.dist(*s))
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        tree.steps.append((mx, my, tier["stroke"]))
        if f.get("label"):
            style = TextStyle(
                font=tree.theme.mono,
                size=18,
                fill=tier["text"],
                weight=500,
                anchor="middle",
            )
            tree.out.append(text(x=mx, y=my + 34, s=f["label"], style=style))


def draw_badges(tree: Tree) -> None:
    """Draw a numbered badge on each step of the path, when it has more than one."""
    if len(tree.steps) < 2:
        return
    for i, st in enumerate(tree.steps, start=1):
        if st is not None:
            x, y, color = st
            tree.out.append(badge(at=(x, y), n=i, fill=color, font=tree.theme.sans))


def draw_cards(tree: Tree, *, card_x: float) -> float | None:
    """Draw a callout card, with its leader, for each level that has one.

    Returns the bottom of the lowest card, or None when no card is drawn.
    """
    reg = tree.reg
    level_specs = tree.spec.get("levels", [])
    reg.issues.extend(unused_cards(level_specs, len(tree.levels)))
    bottom = None
    for d, lvl in enumerate(tree.levels):
        card = level_specs[d].get("card") if d < len(level_specs) else None
        if not card:
            continue
        n = max(lvl, key=lambda k: k.slab.vertex("right")[0])
        color = tree.tiers[n.id]["stroke"]
        lx, ly = leader_point(tree, n)
        rows = math.ceil(len(card.get("items", [])) / 2)
        h = 104 + rows * 38 if rows else 90
        top = max((bottom or 0) + 30, 40, ly - 90)
        if not top + 24 <= ly <= top + h - 24:
            reg.issues.append(
                f"leader: '{card.get('title')}' card cannot sit level with its leader"
            )
        tree.out.append(
            f'<line x1="{lx:.1f}" y1="{ly:.1f}" x2="{card_x:.1f}" y2="{ly:.1f}" '
            f'stroke="{color}" stroke-width="2.5"/>'
        )
        tree.out.append(dot(x=lx, y=ly, color=color))
        tree.out.append(
            callout_card(
                tree,
                box=(card_x, top, CARD_W, h),
                color=color,
                title=card.get("title", n.label),
                items=card.get("items", []),
            )
        )
        bottom = top + h
    return bottom


def leader_point(tree: Tree, n: Node) -> Point:
    """Return where a card's leader starts on n: on its face, clear of connectors.

    Tries points along the top-right edge, nudged onto the face; records an issue when
    none is clear.
    """
    rx, ry = n.slab.vertex("right")
    tx, ty = n.slab.vertex("top")
    for t in (0.15, 0.3, 0.45, 0.6):
        ex, ey = rx + (tx - rx) * t, ry + (ty - ry) * t
        px, py = ex + (n.slab.cx - ex) * 0.15, ey + (n.slab.cy - ey) * 0.15
        if not any(
            abs(py - a[1]) < 22 and abs(a[1] - b[1]) < 0.5 and max(a[0], b[0]) > px
            for pts in tree.placed
            for a, b in itertools.pairwise(pts)
        ):
            return (px, py)
    tree.reg.issues.append(f"leader: '{n.id}' leader runs close to a connector")
    return (rx - 25, ry)


def unused_cards(level_specs: list[Spec], depth_count: int) -> list[str]:
    """Return an issue for each card on a level deeper than the tree, which nothing draws."""
    return [
        f"levels: levels[{d}] has a card, but the tree has {depth_count} levels"
        for d in range(depth_count, len(level_specs))
        if level_specs[d].get("card")
    ]


def default_caption(spec: Spec) -> str:
    """Return the story, plus a legend when the spec draws a path."""
    parts = [spec.get("story", "")]
    if spec.get("path"):
        parts.append("Faint lines: contains. Bold arrows: the path, steps numbered.")
    return " ".join(p for p in parts if p)


def draw_node(*, n: Node, t: Tier, theme: Theme, reg: Registry) -> str:
    """Return a node's slab and labels, shrinking the label to fit, and register them."""
    s = n.slab
    size = (
        max(20, min(46, round(min(s.w, s.d) * 0.17)))
        if not n.parent or not n.parent.stacked
        else 20
    )
    # Shrink to fit the surface, never below the floor; checks flag what still overflows.
    while (
        size > theme.min_surface_text
        and theme.measure(s=n.label, size=size, mono=n.mono, weight=600) > s.d - 28
    ):
        size -= 1
    lines = [(n.label, size, 600, n.mono)]
    if n.sublabel:
        lines.append((n.sublabel, 20, 500 if n.mono_sub else 400, n.mono_sub))
    gap = 6
    block = sum(size for _, size, _, _ in lines) + gap * (len(lines) - 1)
    front = s.w * 0.06 if len(lines) > 1 else 0
    y = front - block / 2
    texts = []
    for s_text, size, weight, mono in lines:
        cy = y + size / 2
        style = TextStyle(
            font=theme.mono if mono else theme.sans,
            size=size,
            fill=t["text"],
            weight=weight,
            anchor="middle",
            baseline="central",
        )
        texts.append(text(x=0, y=cy, s=s_text, style=style))
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
    title = f"<title>{escape(n.label)}</title>" + (
        f"<desc>{escape(n.desc)}</desc>" if n.desc else ""
    )
    labels = (
        f'<g transform="{plane_matrix(s.cx, s.cy)} rotate(-90)">{"".join(texts)}</g>'
    )
    return f"<g>{title}{s.svg(top=t['top'], side=t['side'], stroke=t['stroke'])}{labels}</g>"


def callout_card(
    tree: Tree,
    *,
    box: tuple[float, float, float, float],
    color: str,
    title: str,
    items: list[str],
) -> str:
    """Return a callout card in box (x, y, w, h): a title over its items in two columns.

    Registers the card's text, so the fit rule reports what runs past the card.
    """
    x, y, w, h = box
    theme, reg = tree.theme, tree.reg
    within = f"card '{title}'"
    reg.text(
        text=title,
        left=x + 30,
        right=x + 30 + theme.measure(s=title, size=32, weight=600),
        within=within,
        box=(x, x + w - 30),
    )
    title_style = TextStyle(font=theme.sans, size=32, fill=color, weight=600)
    item_style = TextStyle(font=theme.sans, size=19, fill=theme.ink["body"])
    out = [
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w}" height="{h}" rx="22" fill="#FFFFFF" '
        f'stroke="{color}" stroke-width="3"/>',
        text(x=x + 30, y=y + 52, s=title, style=title_style),
    ]
    per_col = math.ceil(len(items) / 2) if items else 0
    col_w = (w - 60) / 2
    for i, item in enumerate(items):
        col = i // per_col
        cx = x + 30 + col * col_w
        # Text in the first of two columns must stop short of the second.
        right = cx + col_w - 20 if col == 0 and len(items) > 1 else x + w - 30
        reg.text(
            text=item,
            left=cx,
            right=cx + theme.measure(s=item, size=19),
            within=within,
            box=(x, right),
        )
        out.append(text(x=cx, y=y + 100 + (i % per_col) * 38, s=item, style=item_style))
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
