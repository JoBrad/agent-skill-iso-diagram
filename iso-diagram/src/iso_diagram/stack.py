"""iso-stack: an exploded stack of plates, one per containment level, with traffic pipes.

Things that nest line up vertically: a column holds the same position on every plate. Pipes
run between plates in lanes, A lanes carry traffic down and B lanes carry it up; a sideways
hop happens flat on the plate named as its 'via'.
"""

import math

from collections.abc import Callable
from typing import Any

from iso_diagram.checks import Registry
from iso_diagram.iso import (
    C,
    Point,
    S,
    Slab,
    badge,
    icon,
    plane_matrix,
    rounded_path,
    svg_doc,
    text,
    to_screen,
)
from iso_diagram.shared import Spec
from iso_diagram.theme import Theme, Tier


GAP = 260  # screen distance between plate centers
H = 24  # plate thickness
SPACING = 130  # plane distance between column centers, along each axis
INSET = 18
LANE = 16  # plane offset of the A and B lanes from a column's center
ZONE_MIN, ZONE_MAX = 100, SPACING - 6
RES_SIZE, RES_H = 64, 18
RES_OFFSETS = {1: [(0, 6)], 2: [(-34, 40), (34, 58)], 3: [(-50, 30), (0, 52), (50, 74)]}

# Column name to its plane center, shared by every plate.
Columns = dict[str, Point]
# (layer index, column) to the zone's side length.
ZoneWidths = dict[tuple[int, str], float]
# Column to the (first, last) layer index its lane spans.
Lanes = dict[str, tuple[int, int]]
# (via layer index, from column, to column).
Hop = tuple[int, str, str]
# Plane point of a column's lane: lane(column, "A" or "B").
LaneFn = Callable[[str, str], Point]


def build(spec: Spec, theme: Theme) -> tuple[str, Registry, Point]:
    """Lay out and draw an iso-stack spec; return the SVG, its registry, and its size."""
    reg = Registry(theme)
    cols = spec["columns"]
    n = len(cols)
    colpos = {
        c: (30 + SPACING * (i - (n - 1) / 2), 30 - SPACING * (i - (n - 1) / 2))
        for i, c in enumerate(cols)
    }
    layers = spec["layers"]
    index = {l["id"]: i for i, l in enumerate(layers)}
    slots = theme.level_slots(len(layers))
    tiers = [theme.tier(l.get("slot") or slots[i]) for i, l in enumerate(layers)]

    zone_w = {}
    for i, l in enumerate(layers):
        for z in l.get("zones", []):
            length = theme.measure(
                s=z["label"], size=20, mono=z.get("mono", False), weight=500
            )
            zone_w[i, z["column"]] = z.get("size") or max(
                ZONE_MIN, min(ZONE_MAX, round(length + 34))
            )
        widest = max((w for (li, _), w in zone_w.items() if li == i), default=None)
        for z in l.get(
            "zones", []
        ):  # zones on one plate share a size, so siblings read as peers
            zone_w[i, z["column"]] = widest
    # The plate grows until every zone, resource, and label sits inset from its edge.
    reach = (
        max(max(abs(x), abs(y)) for x, y in colpos.values())
        + max(zone_w.values(), default=ZONE_MAX) / 2
    )
    for l in layers:
        for r in l.get("resources", []):
            col = colpos[r["column"]]
            for dx, dy in RES_OFFSETS[r.get("count", 1)]:
                px, py = (dx / C + dy / S) / 2 + col[0], (dy / S - dx / C) / 2 + col[1]
                reach = max(reach, abs(px) + RES_SIZE / 2, abs(py) + RES_SIZE / 2)
            lx, ly = res_label_pos(col, r.get("count", 1))
            half = theme.measure(s=r["label"], size=20, mono=False, weight=600) / 2
            reach = max(reach, abs(lx) + 9, abs(ly) + half)
    W = 2 * (reach + INSET)
    cx = 35 + W * C
    flow = theme.flow

    def lane(col: str, side: str) -> Point:
        x, y = colpos[col]
        k = -LANE if side == "A" else LANE
        return (x + k, y - k)

    # Collect lane ranges and sideways hops from the steps.
    down, up, hops, step_marks = {}, {}, [], []
    for s in spec.get("steps", []):
        if s.get("from") == "source":
            c = s["column"]
            rng = down.get(c, (math.inf, -math.inf))
            down[c] = (min(rng[0], -1), max(rng[1], index[s["to"]]))
            step_marks.append(("source", c))
        else:
            a, b, via, at = s["from"], s["to"], index[s["via"]], index[s["at"]]
            for lanes, col in ((up, a), (down, b)):
                rng = lanes.get(col, (math.inf, -math.inf))
                lanes[col] = (min(rng[0], via), max(rng[1], at))
            hops.append((via, a, b))
            step_marks.append(("hop", a, at))

    # Plates sit far enough apart that nothing the story needs is hidden by the plate above.
    keys = key_points(
        layers=layers,
        colpos=colpos,
        zone_w=zone_w,
        lane=lane,
        down=down,
        up=up,
        hops=hops,
        step_marks=step_marks,
        theme=theme,
    )
    gap = GAP
    while True:
        cys = [350 + gap * i for i in range(len(layers))]
        hidden = []
        for i in range(1, len(layers)):
            above = Slab(name="", cx=cx, cy=cys[i - 1], w=W, d=W, h=H, r=26)
            for p in keys[i]:
                x, y = to_screen(cx=cx, cy=cys[i], x=p[0], y=p[1])
                r = p[2] if len(p) > 2 else 8
                if any(
                    above.contains(x + dx, y + dy)
                    for dx, dy in ((0, 0), (r, 0), (-r, 0), (0, r), (0, -r))
                ):
                    hidden.append((i, p))
        if not hidden or gap >= 600:
            break
        gap += 10
    for i, p in hidden:
        reg.issues.append(
            f"hidden: something on '{layers[i]['id']}' at plane {p[0]:.0f},{p[1]:.0f} is under the plate above"
        )
    plates = [
        reg.slab(Slab(name=l["id"], cx=cx, cy=cys[i], w=W, d=W, h=H, r=26))
        for i, l in enumerate(layers)
    ]

    def pt(i: int, p: Point) -> Point:
        return to_screen(cx=cx, cy=cys[i], x=p[0], y=p[1])

    def ports(i: int) -> list[str]:
        out = []
        for lanes, side in ((down, "A"), (up, "B")):
            for col, (lo, hi) in lanes.items():
                if max(lo, 0) <= i <= hi:
                    x, y = pt(i, lane(col, side))
                    out.append(
                        f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="13" ry="7.5" fill="{flow["text"]}" '
                        f'opacity="0.75"/>'
                    )
        return out

    def pipes_to(i: int) -> list[str]:
        out = []
        for lanes, side, is_up in ((down, "A", False), (up, "B", True)):
            for col, (lo, hi) in lanes.items():
                if lo <= i - 1 and i <= hi and i >= 1:
                    (x, y0), (_, y1) = (
                        pt(i - 1, lane(col, side)),
                        pt(i, lane(col, side)),
                    )
                    out.append(
                        f'<line x1="{x:.1f}" y1="{y0:.1f}" x2="{x:.1f}" y2="{y1:.1f}" '
                        f'stroke="{flow["hue"]}" stroke-width="18"/>'
                        + chevron(x=x, y=y1 - 45, up=is_up, flow=flow)
                    )
        return out

    out = [plates[-1].shadow(dy=50)]
    for i in reversed(range(len(layers))):
        l, t, p = layers[i], tiers[i], plates[i]
        out.append(
            f"<g><title>{l['title']}</title>{p.svg(top=t['top'], side=t['side'], stroke=t['stroke'])}</g>"
        )
        out.append(
            plate_content(
                i=i,
                l=l,
                t=t,
                W=W,
                colpos=colpos,
                zone_w=zone_w,
                lane=lane,
                hops=hops,
                flow=flow,
                theme=theme,
                reg=reg,
                cx=cx,
                cy=cys[i],
            )
        )
        out.extend(ports(i))
        out.extend(pipes_to(i))
        if l.get("resources"):
            out.append(
                resources(
                    i=i,
                    l=l,
                    t=t,
                    colpos=colpos,
                    theme=theme,
                    reg=reg,
                    cx=cx,
                    cy=cys[i],
                    W=W,
                )
            )

    # Source feed into the top plate.
    source = spec.get("source")
    badges = []
    if source:
        col = source["column"]
        x, y = pt(0, lane(col, "A"))
        out.append(
            f'<line x1="{x:.1f}" y1="100" x2="{x:.1f}" y2="{y:.1f}" stroke="{flow["hue"]}" '
            f'stroke-width="18"/>' + chevron(x=x, y=y - 60, up=False, flow=flow)
        )
        out.extend(p for p in ports(0) if f'cx="{x:.1f}"' in p)
        out.append(
            f'<g transform="translate({x:.1f},60)">{icon(name=source.get("icon", "globe"), color=flow["text"], size=52)}</g>'
        )
        out.append(
            text(
                x=x + 40,
                y=68,
                s=source.get("label", "Source"),
                font=theme.sans,
                size=22,
                fill=flow["text"],
                weight=600,
            )
        )
        badges.append(("screen", x - 34, 150))
    for mark in step_marks:
        if mark[0] == "hop":
            _, col, at = mark
            bx, by = lane(col, "B")
            badges.append(("plane", at, bx + 20, by - 60))
    if len(badges) > 1:
        for n_, b in enumerate(badges, start=1):
            if b[0] == "screen":
                out.append(
                    badge(x=b[1], y=b[2], n=n_, fill=flow["text"], font=theme.sans)
                )
            else:
                _, at, bx, by = b
                out.append(
                    f'<g transform="{plane_matrix(cx, cys[at])} translate({bx:.1f},{by:.1f}) rotate(-90)">'
                    f"{badge(x=0, y=0, n=n_, fill=flow['text'], font=theme.sans, size=20)}</g>"
                )

    # Leader lines and plate titles on the right.
    lead_x = cx + W * C - 75
    label_x = lead_x + 850
    for i, l in enumerate(layers):
        t, p = tiers[i], plates[i]
        top_edge = p.vspan(lead_x)[0]
        y = cys[i] - 90
        out.append(
            f'<path d="{rounded_path([(label_x, y), (lead_x, y), (lead_x, top_edge + 14)], 18)}" '
            f'fill="none" stroke="{t["stroke"]}" stroke-width="2.5"/>'
            f'<circle cx="{lead_x:.1f}" cy="{top_edge + 14:.1f}" r="6" fill="{t["stroke"]}"/>'
        )
        out.append(
            text(
                x=label_x,
                y=y - 14,
                s=l["title"],
                font=theme.sans,
                size=40,
                fill=t["text"],
                weight=500,
                anchor="end",
            )
        )
        if l.get("subtitle"):
            out.append(
                text(
                    x=label_x,
                    y=y + 30,
                    s=l["subtitle"],
                    font=theme.sans,
                    size=18,
                    fill=theme.ink["caption"],
                    weight=400,
                    anchor="end",
                )
            )

    width = label_x + 60
    bottom = max(p_[1] for p_ in plates[-1].body)
    caption_y = bottom + 70
    out.append(
        text(
            x=40,
            y=caption_y,
            s=spec.get("caption") or spec["story"],
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
            marker_colors=[],
            background=theme.background,
            title=spec.get("title"),
            desc=spec.get("story"),
        ),
        reg,
        (width, height),
    )


def key_points(
    *,
    layers: list[Spec],
    colpos: Columns,
    zone_w: ZoneWidths,
    lane: LaneFn,
    down: Lanes,
    up: Lanes,
    hops: list[Hop],
    step_marks: list[tuple[Any, ...]],
    theme: Theme,
) -> dict[int, list[tuple[float, ...]]]:
    """Plane points on each plate that must stay visible: ports, hops, badges, labels, resources."""
    keys = {i: [] for i in range(len(layers))}
    for lanes, side in ((down, "A"), (up, "B")):
        for col, (lo, hi) in lanes.items():
            for i in range(max(lo, 0), hi + 1):
                keys[i].append(lane(col, side))
    for via, a, b in hops:
        pa, pb = lane(a, "B"), lane(b, "A")
        keys[via] += [pa, (pa[0] - 45, pa[1] - 45), (pb[0] - 45, pb[1] - 45), pb]
    for m in step_marks:
        if m[0] == "hop":
            bx, by = lane(m[1], "B")
            keys[m[2]].append(
                (bx + 20, by - 60, 22)
            )  # a badge: keep its whole disc clear
    for i, l in enumerate(layers):
        for z in l.get("zones", []):
            x, y = colpos[z["column"]]
            keys[i].append((x + zone_w[i, z["column"]] / 2 - 18, y))
        for m in l.get("markers", []):
            x, y = colpos[m["column"]]
            keys[i].append((x + 34, y + 6))
        for r in l.get("resources", []):
            col = colpos[r["column"]]
            for dx, dy in RES_OFFSETS[r.get("count", 1)]:
                keys[i].append(
                    ((dx / C + dy / S) / 2 + col[0], (dy / S - dx / C) / 2 + col[1])
                )
            keys[i].append(res_label_pos(col, r.get("count", 1)))
    return keys


def chevron(*, x: float, y: float, up: bool, flow: Tier) -> str:
    """Return a chevron at (x, y) pointing up or down, in the flow's text shade."""
    d = -1 if up else 1
    return (
        f'<polyline points="{x - 6:.1f},{y - 3.5 * d:.1f} {x:.1f},{y + 3.5 * d:.1f} {x + 6:.1f},{y - 3.5 * d:.1f}" '
        f'fill="none" stroke="{flow["text"]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def ptext(
    *,
    x: float,
    y: float,
    s: str,
    fill: str,
    theme: Theme,
    mono: bool = False,
    weight: int = 500,
    size: float = 20,
) -> str:
    """Return text lying flat on a plate at plane (x, y), upright to the reader."""
    font = theme.mono if mono else theme.sans
    return text(
        x=0,
        y=0,
        s=s,
        font=font,
        size=size,
        fill=fill,
        weight=weight,
        anchor="middle",
        baseline="central",
        transform=f"translate({x:.1f},{y:.1f}) rotate(-90)",
    )


def plate_content(
    *,
    i: int,
    l: Spec,
    t: Tier,
    W: float,
    colpos: Columns,
    zone_w: ZoneWidths,
    lane: LaneFn,
    hops: list[Hop],
    flow: Tier,
    theme: Theme,
    reg: Registry,
    cx: float,
    cy: float,
) -> str:
    """Return a plate's zones, hops, markers, and note, registering them for checks."""
    inner = []
    for z in l.get("zones", []):
        x, y = colpos[z["column"]]
        w = zone_w[i, z["column"]]
        dash = ' stroke-dasharray="8 7"' if z.get("style") == "dashed" else ""
        fill = "none" if z.get("fill") is False else "#FFFFFF"
        inner.append(
            f'<rect x="{x - w / 2:.1f}" y="{y - w / 2:.1f}" width="{w}" height="{w}" rx="14" fill="{fill}" '
            f'stroke="{t["stroke"]}" stroke-width="2.5"{dash}/>'
        )
        mono = z.get("mono", False)
        weight = 500 if mono or z.get("style") == "dashed" else 600
        inner.append(
            ptext(
                x=x + w / 2 - 18,
                y=y,
                s=z["label"],
                fill=t["text"],
                theme=theme,
                mono=mono,
                weight=weight,
            )
        )
        reg.child(parent=l["id"], pw=W, pd=W, name=z["label"], rect=(x, y, w, w))
        reg.label(
            surface=f"{l['id']}/{z['label']}",
            sw=w,
            sd=w,
            s=z["label"],
            center=(w / 2 - 18, 0),
            size=20,
            length=theme.measure(s=z["label"], size=20, mono=mono, weight=weight),
        )
    for via, a, b in hops:
        if via != i:
            continue
        pa, pb = lane(a, "B"), lane(b, "A")
        pts = [pa, (pa[0] - 45, pa[1] - 45), (pb[0] - 45, pb[1] - 45), pb]
        inner.append(
            f'<path d="{rounded_path(pts, 20)}" fill="none" stroke="{flow["hue"]}" stroke-width="18" '
            f'stroke-linecap="round"/>'
        )
    for m in l.get("markers", []):
        x, y = colpos[m["column"]]
        inner.append(
            ptext(
                x=x + 34,
                y=y + 6,
                s=m["label"],
                fill=t["text"],
                theme=theme,
                mono=m.get("mono", False),
                weight=600,
            )
        )
        reg.label(
            surface=l["id"],
            sw=W,
            sd=W,
            s=m["label"],
            center=(x + 34, y + 6),
            size=20,
            length=theme.measure(s=m["label"], size=20, mono=False, weight=600),
        )
    if l.get("note"):
        note = l["note"]
        length = theme.measure(
            s=note["text"], size=20, mono=note.get("mono"), weight=500
        )
        nx, ny = (
            W / 2 - 34,
            W / 2 - 30 - length / 2,
        )  # along the front-right edge, near the front corner
        inner.append(
            ptext(
                x=nx,
                y=ny,
                s=note["text"],
                fill=t["text"],
                theme=theme,
                mono=note.get("mono", False),
            )
        )
        reg.label(
            surface=l["id"],
            sw=W,
            sd=W,
            s=note["text"],
            center=(nx, ny),
            size=20,
            length=length,
        )
    return f'<g transform="{plane_matrix(cx, cy)}">{"".join(inner)}</g>'


def res_label_pos(col: Point, count: int) -> Point:
    """Return the plane position of the flat label in front of a resource group."""
    dx, dy = max(RES_OFFSETS[count], key=lambda o: o[1])  # the frontmost slab
    px, py = (dx / C + dy / S) / 2 + col[0], (dy / S - dx / C) / 2 + col[1]
    return (px + 54, py)


def resources(
    *,
    i: int,
    l: Spec,
    t: Tier,
    colpos: Columns,
    theme: Theme,
    reg: Registry,
    cx: float,
    cy: float,
    W: float,
) -> str:
    """Return a layer's resource slabs and labels, registering them for checks."""
    out, labels = [], []
    for r in l["resources"]:
        col = colpos[r["column"]]
        sx, sy = to_screen(cx=cx, cy=cy, x=col[0], y=col[1])
        count = r.get("count", 1)
        for dx, dy in RES_OFFSETS[count]:
            x, y = sx + dx, sy + dy
            top_y = y - RES_H
            slab = Slab(
                name=f"{l['id']}/{r['label']}",
                cx=x,
                cy=top_y,
                w=RES_SIZE,
                d=RES_SIZE,
                h=RES_H,
                r=10,
            )
            out.append(slab.svg(top="#FFFFFF", side=t["side"], stroke=t["stroke"]))
            out.append(
                f'<g transform="{plane_matrix(x, top_y)} rotate(-90)">{icon(name=r["icon"], color=t["text"], size=50, stroke=1.8)}</g>'
            )
            px, py = (dx / C + dy / S) / 2 + col[0], (dy / S - dx / C) / 2 + col[1]
            reg.child(
                parent=l["id"],
                pw=W,
                pd=W,
                name=r["label"],
                rect=(px, py, RES_SIZE, RES_SIZE),
            )
        lx, ly = res_label_pos(col, count)
        labels.append(
            ptext(
                x=lx,
                y=ly,
                s=r["label"],
                fill=t["text"],
                theme=theme,
                mono=r.get("mono", False),
                weight=600,
            )
        )
        reg.label(
            surface=l["id"],
            sw=W,
            sd=W,
            s=r["label"],
            center=(lx, ly),
            size=20,
            length=theme.measure(s=r["label"], size=20, mono=False, weight=600),
        )
    out.append(f'<g transform="{plane_matrix(cx, cy)}">{"".join(labels)}</g>')
    return "".join(out)
