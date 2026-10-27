"""iso-stack: an exploded stack of plates, one per containment level, with traffic pipes.

Things that nest line up vertically: a column holds the same position on every plate. Pipes
run between plates in lanes, A lanes carry traffic down and B lanes carry it up; a sideways
hop happens flat on the plate named as its 'via'.
"""

from dataclasses import dataclass, field
from typing import Any
from xml.sax.saxutils import escape

from iso_diagram.checks import Label, Registry, Surface
from iso_diagram.iso import (
    C,
    Point,
    S,
    Slab,
    Spec,
    TextStyle,
    badge,
    caption,
    icon,
    plane_matrix,
    rounded_path,
    svg_doc,
    text,
    to_screen,
)
from iso_diagram.theme import Theme, Tier


GAP = 260  # screen distance between plate centers
MAX_GAP = 600
H = 24  # plate thickness
SPACING = 170  # plane distance between column centers, along each axis
INSET = 18
LANE = 16  # plane offset of the A and B lanes from a column's center
ZONE_MIN, ZONE_MAX = 100, SPACING - 6
RES_SIZE, RES_H = 64, 18
LABEL = 26  # surface label size, in line with iso-tree slab labels
RES_OFFSETS = {1: [(0, 6)], 2: [(-34, 40), (34, 58)], 3: [(-50, 30), (0, 52), (50, 74)]}

# Column name to its plane center, shared by every plate.
Columns = dict[str, Point]
# (layer index, column) to the zone's side length.
ZoneWidths = dict[tuple[int, str], float]
# Column to the (first, last) layer index its lane spans.
Lanes = dict[str, tuple[int, int]]
# (via layer index, from column, to column).
Hop = tuple[int, str, str]
# A numbered step: ("source", column) or ("hop", column, layer index).
Mark = tuple[Any, ...]
# Plane point on a plate that must stay visible: (x, y), or (x, y, radius) for a disc.
KeyPoint = tuple[float, ...]


@dataclass
class Plan:
    """An iso-stack spec resolved into geometry that every drawing step shares.

    Every plate has the same size and column positions, so a column holds the same
    place on each. `down` (A lanes) and `up` (B lanes) map a column to the first and last
    layer index its pipe spans; -1 means the pipe starts above the top plate.
    """

    spec: Spec
    theme: Theme
    reg: Registry
    colpos: Columns
    zone_w: ZoneWidths
    plate_w: float
    tiers: list[Tier]
    down: Lanes = field(default_factory=dict)
    up: Lanes = field(default_factory=dict)
    hops: list[Hop] = field(default_factory=list)
    marks: list[Mark] = field(default_factory=list)
    cys: list[float] = field(default_factory=list)  # screen y of each plate's center

    @property
    def layers(self) -> list[Spec]:
        """The spec's layers, top plate first."""
        return self.spec["layers"]

    @property
    def cx(self) -> float:
        """Screen x of every plate's center."""
        return 35 + self.plate_w * C

    @property
    def lead_x(self) -> float:
        """Screen x where each plate's title leader drops onto the plate."""
        return self.cx + self.plate_w * C - 75

    @property
    def label_x(self) -> float:
        """Screen x where each plate's title ends."""
        return self.lead_x + 850

    def lane(self, col: str, side: str) -> Point:
        """Plane point of a column's A or B lane."""
        x, y = self.colpos[col]
        k = -LANE if side == "A" else LANE
        return (x + k, y - k)

    def pt(self, i: int, p: Point) -> Point:
        """Screen point of plane point p on plate i."""
        return to_screen(cx=self.cx, cy=self.cys[i], x=p[0], y=p[1])

    def flat_text(
        self, *, at: Point, s: str, fill: str, mono: bool = False, weight: int = 500
    ) -> str:
        """Return text lying flat on a plate at plane point at, upright to the reader."""
        style = TextStyle(
            font=self.theme.mono if mono else self.theme.sans,
            size=LABEL,
            fill=fill,
            weight=weight,
            anchor="middle",
            baseline="central",
        )
        return text(
            x=0,
            y=0,
            s=s,
            style=style,
            transform=f"translate({at[0]:.1f},{at[1]:.1f}) rotate(-90)",
        )


def build(spec: Spec, theme: Theme) -> tuple[str, Registry, Point]:
    """Lay out and draw an iso-stack spec; return the SVG, its registry, and its size."""
    plan = make_plan(spec, theme)
    plan.cys = spread_plates(plan)
    plates = [
        plan.reg.slab(
            Slab(
                name=layer["id"],
                cx=plan.cx,
                cy=plan.cys[i],
                w=plan.plate_w,
                d=plan.plate_w,
                h=H,
                r=26,
            )
        )
        for i, layer in enumerate(plan.layers)
    ]
    out = [plates[-1].shadow(dy=50)]
    for i in reversed(range(len(plates))):
        out.extend(draw_plate(plan, i, plates[i]))
    out.extend(draw_source(plan))
    out.extend(draw_badges(plan))
    for i, plate in enumerate(plates):
        out.extend(draw_title(plan, i, plate))

    width = plan.label_x + 60
    bottom = max(p[1] for p in plates[-1].body)
    caption_svg, height = caption(
        s=spec.get("caption") or spec["story"],
        top=bottom + 70,
        width=width,
        theme=theme,
        reg=plan.reg,
    )
    out.append(caption_svg)
    doc = svg_doc(
        size=(width, height),
        body="".join(out),
        background=theme.background,
        title=spec.get("title"),
        desc=spec.get("story"),
    )
    return doc, plan.reg, (width, height)


# --- planning ---------------------------------------------------------------------------


def make_plan(spec: Spec, theme: Theme) -> Plan:
    """Place columns, size zones and plates, and collect lanes and hops from the steps."""
    cols = spec["columns"]
    n = len(cols)
    colpos = {
        c: (30 + SPACING * (i - (n - 1) / 2), 30 - SPACING * (i - (n - 1) / 2))
        for i, c in enumerate(cols)
    }
    layers = spec["layers"]
    slots = theme.level_slots(len(layers))
    zone_w = zone_widths(layers, theme)
    plan = Plan(
        spec=spec,
        theme=theme,
        reg=Registry(theme),
        colpos=colpos,
        zone_w=zone_w,
        plate_w=plate_width(layers=layers, colpos=colpos, zone_w=zone_w, theme=theme),
        tiers=[
            theme.tier(layer.get("slot") or slots[i]) for i, layer in enumerate(layers)
        ],
    )
    collect_steps(plan)
    return plan


def zone_widths(layers: list[Spec], theme: Theme) -> ZoneWidths:
    """Size each zone to its label; zones on one plate share the widest size, as peers."""
    zone_w: ZoneWidths = {}
    for i, layer in enumerate(layers):
        zones = layer.get("zones", [])
        for z in zones:
            length = theme.measure(
                s=z["label"], size=LABEL, mono=z.get("mono", False), weight=500
            )
            zone_w[i, z["column"]] = z.get("size") or max(
                ZONE_MIN, min(ZONE_MAX, round(length + 34))
            )
        if zones:
            widest = max(zone_w[i, z["column"]] for z in zones)
            for z in zones:
                zone_w[i, z["column"]] = widest
    return zone_w


def res_plane(col: Point, offset: Point) -> Point:
    """Plane point of a resource slab placed at a screen offset from its column."""
    dx, dy = offset
    return ((dx / C + dy / S) / 2 + col[0], (dy / S - dx / C) / 2 + col[1])


def res_label_pos(col: Point, count: int) -> Point:
    """Return the plane position of the flat label in front of a resource group."""
    px, py = res_plane(col, max(RES_OFFSETS[count], key=lambda o: o[1]))  # frontmost
    return (px + 54, py)


def plate_width(
    *, layers: list[Spec], colpos: Columns, zone_w: ZoneWidths, theme: Theme
) -> float:
    """Grow the plate until every zone, resource, and label sits inset from its edge."""
    reach = (
        max(max(abs(x), abs(y)) for x, y in colpos.values())
        + max(zone_w.values(), default=ZONE_MAX) / 2
    )
    for layer in layers:
        for r in layer.get("resources", []):
            col = colpos[r["column"]]
            for offset in RES_OFFSETS[r.get("count", 1)]:
                px, py = res_plane(col, offset)
                reach = max(reach, abs(px) + RES_SIZE / 2, abs(py) + RES_SIZE / 2)
            lx, ly = res_label_pos(col, r.get("count", 1))
            half = (
                theme.measure(s=r["label"], size=LABEL, mono=r.get("mono"), weight=600)
                / 2
            )
            reach = max(reach, abs(lx) + 9, abs(ly) + half)
    return 2 * (reach + INSET)


def collect_steps(plan: Plan) -> None:
    """Fill the plan's lane ranges, sideways hops, and step marks from the spec's steps."""
    index = {layer["id"]: i for i, layer in enumerate(plan.layers)}
    for s in plan.spec.get("steps", []):
        if s.get("from") == "source":
            c = s["column"]
            widen(plan.down, col=c, span=(-1, index[s["to"]]))
            plan.marks.append(("source", c))
        else:
            a, b, via, at = s["from"], s["to"], index[s["via"]], index[s["at"]]
            widen(plan.up, col=a, span=(via, at))
            widen(plan.down, col=b, span=(via, at))
            plan.hops.append((via, a, b))
            plan.marks.append(("hop", a, at))


def widen(lanes: Lanes, *, col: str, span: tuple[int, int]) -> None:
    """Grow a column's lane to cover span, a (first, last) layer index range."""
    lo, hi = lanes.get(col, span)
    lanes[col] = (min(lo, span[0]), max(hi, span[1]))


def spread_plates(plan: Plan) -> list[float]:
    """Return plate centers far enough apart that the plate above hides nothing that matters.

    Records an issue for each key point still hidden at the widest gap.
    """
    keys = key_points(plan)
    gap = GAP
    while True:
        cys: list[float] = [350 + gap * i for i in range(len(plan.layers))]
        hidden = hidden_points(plan, cys=cys, keys=keys)
        if not hidden or gap >= MAX_GAP:
            break
        gap += 10
    for i, p in hidden:
        plan.reg.issues.append(
            f"hidden: something on '{plan.layers[i]['id']}' at plane "
            f"{p[0]:.0f},{p[1]:.0f} is under the plate above"
        )
    return cys


def hidden_points(
    plan: Plan, *, cys: list[float], keys: dict[int, list[KeyPoint]]
) -> list[tuple[int, KeyPoint]]:
    """Return the key points the plate above covers when plates sit at cys."""
    hidden = []
    for i in range(1, len(cys)):
        above = Slab(
            name="",
            cx=plan.cx,
            cy=cys[i - 1],
            w=plan.plate_w,
            d=plan.plate_w,
            h=H,
            r=26,
        )
        for p in keys[i]:
            x, y = to_screen(cx=plan.cx, cy=cys[i], x=p[0], y=p[1])
            r = p[2] if len(p) > 2 else 8
            if any(
                above.contains(x + dx, y + dy)
                for dx, dy in ((0, 0), (r, 0), (-r, 0), (0, r), (0, -r))
            ):
                hidden.append((i, p))
    return hidden


def key_points(plan: Plan) -> dict[int, list[KeyPoint]]:
    """Plane points on each plate that must stay visible: ports, hops, badges, labels, resources."""
    keys: dict[int, list[KeyPoint]] = {i: [] for i in range(len(plan.layers))}
    for lanes, side in ((plan.down, "A"), (plan.up, "B")):
        for col, (lo, hi) in lanes.items():
            for i in range(max(lo, 0), hi + 1):
                keys[i].append(plan.lane(col, side))
    for via, a, b in plan.hops:
        pa, pb = plan.lane(a, "B"), plan.lane(b, "A")
        keys[via] += [pa, (pa[0] - 45, pa[1] - 45), (pb[0] - 45, pb[1] - 45), pb]
    for m in plan.marks:
        if m[0] == "hop":
            bx, by = plan.lane(m[1], "B")
            keys[m[2]].append(
                (bx + 20, by - 60, 22)
            )  # a badge: keep its whole disc clear
    for i, layer in enumerate(plan.layers):
        keys[i] += item_key_points(plan, i, layer)
    return keys


def item_key_points(plan: Plan, i: int, layer: Spec) -> list[KeyPoint]:
    """Plane points of one plate's zone labels, markers, resources, and resource labels."""
    keys: list[KeyPoint] = []
    for z in layer.get("zones", []):
        x, y = plan.colpos[z["column"]]
        keys.append((x + plan.zone_w[i, z["column"]] / 2 - 18, y))
    for m in layer.get("markers", []):
        x, y = plan.colpos[m["column"]]
        keys.append((x + 34, y + 6))
    for r in layer.get("resources", []):
        col = plan.colpos[r["column"]]
        keys += [res_plane(col, o) for o in RES_OFFSETS[r.get("count", 1)]]
        keys.append(res_label_pos(col, r.get("count", 1)))
    return keys


# --- drawing ----------------------------------------------------------------------------


def chevron(*, x: float, y: float, up: bool, flow: Tier) -> str:
    """Return a chevron at (x, y) pointing up or down, in the flow's text shade."""
    d = -1 if up else 1
    pts = f"{x - 6:.1f},{y - 3.5 * d:.1f} {x:.1f},{y + 3.5 * d:.1f} {x + 6:.1f},{y - 3.5 * d:.1f}"
    return (
        f'<polyline points="{pts}" fill="none" stroke="{flow["text"]}" stroke-width="3" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
    )


def ports(plan: Plan, i: int) -> list[str]:
    """Return the port ellipses on plate i where a lane passes through it."""
    fill = plan.theme.flow["text"]
    out = []
    for lanes, side in ((plan.down, "A"), (plan.up, "B")):
        for col, (lo, hi) in lanes.items():
            if max(lo, 0) <= i <= hi:
                x, y = plan.pt(i, plan.lane(col, side))
                out.append(
                    f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="13" ry="7.5" fill="{fill}" '
                    f'opacity="0.75"/>'
                )
    return out


def pipes_to(plan: Plan, i: int) -> list[str]:
    """Return the pipes from plate i - 1 down to plate i, each with a direction chevron."""
    flow = plan.theme.flow
    out = []
    for lanes, side, is_up in ((plan.down, "A", False), (plan.up, "B", True)):
        for col, (lo, hi) in lanes.items():
            if lo <= i - 1 and i <= hi and i >= 1:
                (x, y0), (_, y1) = (
                    plan.pt(i - 1, plan.lane(col, side)),
                    plan.pt(i, plan.lane(col, side)),
                )
                out.append(
                    f'<line x1="{x:.1f}" y1="{y0:.1f}" x2="{x:.1f}" y2="{y1:.1f}" '
                    f'stroke="{flow["hue"]}" stroke-width="18"/>'
                    + chevron(x=x, y=y1 - 45, up=is_up, flow=flow)
                )
    return out


def draw_plate(plan: Plan, i: int, plate: Slab) -> list[str]:
    """Return plate i with everything on it: zones, hops, markers, ports, pipes, resources."""
    layer, t = plan.layers[i], plan.tiers[i]
    body = plate.svg(top=t["top"], side=t["side"], stroke=t["stroke"])
    out = [
        f"<g><title>{escape(layer['title'])}</title>{body}</g>",
        plate_content(plan, i),
        *ports(plan, i),
        *pipes_to(plan, i),
    ]
    if layer.get("resources"):
        out.append(resources(plan, i))
    return out


def plate_content(plan: Plan, i: int) -> str:
    """Return a plate's zones, hops, markers, and note, registering them for checks."""
    layer, t, reg = plan.layers[i], plan.tiers[i], plan.reg
    plate = Surface(name=layer["id"], w=plan.plate_w, d=plan.plate_w)
    inner = [*zones(plan, i), *hop_paths(plan, i)]
    for m in layer.get("markers", []):
        x, y = plan.colpos[m["column"]]
        inner.append(
            plan.flat_text(
                at=(x + 34, y + 6),
                s=m["label"],
                fill=t["text"],
                mono=m.get("mono", False),
                weight=600,
            )
        )
        length = plan.theme.measure(
            s=m["label"], size=LABEL, mono=m.get("mono"), weight=600
        )
        reg.label(
            Label(
                surface=plate,
                text=m["label"],
                center=(x + 34, y + 6),
                size=LABEL,
                length=length,
            )
        )
    if layer.get("note"):
        note = layer["note"]
        length = plan.theme.measure(
            s=note["text"], size=LABEL, mono=note.get("mono"), weight=500
        )
        # Along the front-right edge, near the front corner.
        nx, ny = plan.plate_w / 2 - 34, plan.plate_w / 2 - 30 - length / 2
        inner.append(
            plan.flat_text(
                at=(nx, ny),
                s=note["text"],
                fill=t["text"],
                mono=note.get("mono", False),
            )
        )
        reg.label(
            Label(
                surface=plate,
                text=note["text"],
                center=(nx, ny),
                size=LABEL,
                length=length,
            )
        )
    return f'<g transform="{plane_matrix(plan.cx, plan.cys[i])}">{"".join(inner)}</g>'


def zones(plan: Plan, i: int) -> list[str]:
    """Return plate i's zones and their labels in plane coordinates, registering them."""
    layer, t = plan.layers[i], plan.tiers[i]
    plate = Surface(name=layer["id"], w=plan.plate_w, d=plan.plate_w)
    out = []
    for z in layer.get("zones", []):
        x, y = plan.colpos[z["column"]]
        w = plan.zone_w[i, z["column"]]
        dash = ' stroke-dasharray="8 7"' if z.get("style") == "dashed" else ""
        fill = "none" if z.get("fill") is False else "#FFFFFF"
        out.append(
            f'<rect x="{x - w / 2:.1f}" y="{y - w / 2:.1f}" width="{w}" height="{w}" '
            f'rx="14" fill="{fill}" stroke="{t["stroke"]}" stroke-width="2.5"{dash}/>'
        )
        mono = z.get("mono", False)
        weight = 500 if mono or z.get("style") == "dashed" else 600
        out.append(
            plan.flat_text(
                at=(x + w / 2 - 18, y),
                s=z["label"],
                fill=t["text"],
                mono=mono,
                weight=weight,
            )
        )
        plan.reg.child(parent=plate, name=z["label"], rect=(x, y, w, w))
        plan.reg.label(
            Label(
                surface=Surface(name=f"{layer['id']}/{z['label']}", w=w, d=w),
                text=z["label"],
                center=(w / 2 - 18, 0),
                size=LABEL,
                length=plan.theme.measure(
                    s=z["label"], size=LABEL, mono=mono, weight=weight
                ),
            )
        )
    return out


def hop_paths(plan: Plan, i: int) -> list[str]:
    """Return the sideways pipes that run flat on plate i."""
    hue = plan.theme.flow["hue"]
    out = []
    for via, a, b in plan.hops:
        if via != i:
            continue
        pa, pb = plan.lane(a, "B"), plan.lane(b, "A")
        pts = [pa, (pa[0] - 45, pa[1] - 45), (pb[0] - 45, pb[1] - 45), pb]
        out.append(
            f'<path d="{rounded_path(pts, 20)}" fill="none" stroke="{hue}" '
            f'stroke-width="18" stroke-linecap="round"/>'
        )
    return out


def resources(plan: Plan, i: int) -> str:
    """Return a layer's resource slabs and labels, registering them for checks."""
    layer, t = plan.layers[i], plan.tiers[i]
    cx, cy = plan.cx, plan.cys[i]
    plate = Surface(name=layer["id"], w=plan.plate_w, d=plan.plate_w)
    out, labels = [], []
    for r in layer["resources"]:
        col = plan.colpos[r["column"]]
        sx, sy = to_screen(cx=cx, cy=cy, x=col[0], y=col[1])
        count = r.get("count", 1)
        for dx, dy in RES_OFFSETS[count]:
            x, top_y = sx + dx, sy + dy - RES_H
            slab = Slab(
                name=f"{layer['id']}/{r['label']}",
                cx=x,
                cy=top_y,
                w=RES_SIZE,
                d=RES_SIZE,
                h=RES_H,
                r=10,
            )
            glyph = icon(name=r["icon"], color=t["text"], size=50, stroke=1.8)
            out.append(slab.svg(top="#FFFFFF", side=t["side"], stroke=t["stroke"]))
            out.append(
                f'<g transform="{plane_matrix(x, top_y)} rotate(-90)">{glyph}</g>'
            )
            px, py = res_plane(col, (dx, dy))
            plan.reg.child(
                parent=plate, name=r["label"], rect=(px, py, RES_SIZE, RES_SIZE)
            )
        lx, ly = res_label_pos(col, count)
        labels.append(
            plan.flat_text(
                at=(lx, ly),
                s=r["label"],
                fill=t["text"],
                mono=r.get("mono", False),
                weight=600,
            )
        )
        plan.reg.label(
            Label(
                surface=plate,
                text=r["label"],
                center=(lx, ly),
                size=LABEL,
                length=plan.theme.measure(
                    s=r["label"], size=LABEL, mono=r.get("mono"), weight=600
                ),
            )
        )
    out.append(f'<g transform="{plane_matrix(cx, cy)}">{"".join(labels)}</g>')
    return "".join(out)


def draw_source(plan: Plan) -> list[str]:
    """Return the source's feed pipe into the top plate, with its icon and label."""
    source = plan.spec.get("source")
    if not source:
        return []
    flow = plan.theme.flow
    x, y = plan.pt(0, plan.lane(source["column"], "A"))
    glyph = icon(name=source.get("icon", "globe"), color=flow["text"], size=52)
    style = TextStyle(font=plan.theme.sans, size=22, fill=flow["text"], weight=600)
    return [
        f'<line x1="{x:.1f}" y1="100" x2="{x:.1f}" y2="{y:.1f}" stroke="{flow["hue"]}" '
        f'stroke-width="18"/>' + chevron(x=x, y=y - 60, up=False, flow=flow),
        *(p for p in ports(plan, 0) if f'cx="{x:.1f}"' in p),
        f'<g transform="translate({x:.1f},60)">{glyph}</g>',
        text(x=x + 40, y=68, s=source.get("label", "Source"), style=style),
    ]


def draw_badges(plan: Plan) -> list[str]:
    """Return numbered step badges, one on the source feed and one by each hop, if 2 or more."""
    fill, font = plan.theme.flow["text"], plan.theme.sans
    source = plan.spec.get("source")
    hops = [m for m in plan.marks if m[0] == "hop"]
    if len(hops) + bool(source) < 2:
        return []
    out = []
    if source:
        x, _ = plan.pt(0, plan.lane(source["column"], "A"))
        out.append(badge(at=(x - 34, 150), n=1, fill=fill, font=font))
    for n, (_, col, at) in enumerate(hops, start=len(out) + 1):
        bx, by = plan.lane(col, "B")
        disc = badge(at=(0, 0), n=n, fill=fill, font=font, size=20)
        out.append(
            f'<g transform="{plane_matrix(plan.cx, plan.cys[at])} '
            f'translate({bx + 20:.1f},{by - 60:.1f}) rotate(-90)">{disc}</g>'
        )
    return out


def draw_title(plan: Plan, i: int, plate: Slab) -> list[str]:
    """Return plate i's leader line, title, and subtitle, registering the text for fit."""
    layer, t, theme = plan.layers[i], plan.tiers[i], plan.theme
    lead_x, label_x = plan.lead_x, plan.label_x
    span = plate.vspan(lead_x)
    assert span is not None, "lead_x sits inside the plate's right corner"
    top_edge = span[0]
    y = plan.cys[i] - 90
    leader_path = rounded_path([(label_x, y), (lead_x, y), (lead_x, top_edge + 14)], 18)
    out = [
        f'<path d="{leader_path}" fill="none" stroke="{t["stroke"]}" stroke-width="2.5"/>'
        f'<circle cx="{lead_x:.1f}" cy="{top_edge + 14:.1f}" r="6" fill="{t["stroke"]}"/>'
    ]
    lines = [
        (
            layer["title"],
            y - 14,
            TextStyle(
                font=theme.sans, size=40, fill=t["text"], weight=500, anchor="end"
            ),
        )
    ]
    if layer.get("subtitle"):
        lines.append(
            (
                layer["subtitle"],
                y + 30,
                TextStyle(
                    font=theme.sans, size=18, fill=theme.ink["caption"], anchor="end"
                ),
            )
        )
    for s, line_y, style in lines:
        plan.reg.text(
            text=s,
            left=label_x - theme.measure(s=s, size=style.size, weight=style.weight),
            right=label_x,
            within=f"leader of '{layer['id']}'",
            box=(lead_x, label_x),
        )
        out.append(text(x=label_x, y=line_y, s=s, style=style))
    return out
