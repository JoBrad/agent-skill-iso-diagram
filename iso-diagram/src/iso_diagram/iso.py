"""Isometric geometry and SVG building blocks shared by every style.

Plane coordinates (x, y) lie on a top face; screen coordinates are SVG user units. A plane
point maps to the screen with to_screen(); a whole group maps with plane_matrix().
"""

import math
import re

from collections.abc import Iterable, Sequence
from typing import Any
from xml.sax.saxutils import escape

from iso_diagram import icons


C = math.cos(math.radians(30))
S = 0.5
TAN30 = math.tan(math.radians(30))

Point = tuple[float, float]
# A parsed JSON spec, or one of its nested objects.
Spec = dict[str, Any]


# --- geometry -------------------------------------------------------------------------


def to_screen(*, cx: float, cy: float, x: float, y: float) -> Point:
    """Screen point of plane point (x, y) on a face whose center sits at screen (cx, cy)."""
    return (cx + (x - y) * C, cy + (x + y) * S)


def plane_matrix(cx: float, cy: float) -> str:
    """SVG transform that maps plane coordinates onto a face centered at screen (cx, cy)."""
    return f"translate({cx:.1f},{cy:.1f}) matrix({C:.5f},{S},{-C:.5f},{S},0,0)"


def rr_points(*, w: float, d: float, r: float, steps: int = 8) -> list[Point]:
    """Outline of a w x d rounded rectangle centered on the plane origin."""
    r = min(r, w / 2, d / 2)
    pts = []
    corners = [
        (w / 2 - r, -d / 2 + r, -90),
        (w / 2 - r, d / 2 - r, 0),
        (-w / 2 + r, d / 2 - r, 90),
        (-w / 2 + r, -d / 2 + r, 180),
    ]
    for ox, oy, a0 in corners:
        for i in range(steps + 1):
            a = math.radians(a0 + 90 * i / steps)
            pts.append((ox + r * math.cos(a), oy + r * math.sin(a)))
    return pts


def hull(points: Iterable[Point]) -> list[Point]:
    """Return the convex hull of points (Andrew's monotone chain), first point not repeated."""
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts

    def cross(o: Point, a: Point, b: Point) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def point_in_poly(x: float, y: float, poly: list[Point]) -> bool:
    """Return whether (x, y) is inside polygon poly, by the even-odd rule."""
    inside = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1], strict=False):
        if (y0 > y) != (y1 > y) and x < x0 + (x1 - x0) * (y - y0) / (y1 - y0):
            inside = not inside
    return inside


def poly(points: Iterable[Point]) -> str:
    """Return points as an SVG points attribute."""
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


class Slab:
    """A rounded isometric slab. (cx, cy) is the screen center of its top face."""

    def __init__(
        self,
        *,
        name: str,
        cx: float,
        cy: float,
        w: float,
        d: float,
        h: float,
        r: float = 18,
    ) -> None:
        """Build a w x d slab, h deep, with corner radius r, its top centered at (cx, cy)."""
        self.name, self.cx, self.cy, self.w, self.d, self.h, self.r = (
            name,
            cx,
            cy,
            w,
            d,
            h,
            r,
        )
        self.top_pts = [
            to_screen(cx=cx, cy=cy, x=x, y=y) for x, y in rr_points(w=w, d=d, r=r)
        ]
        self.body = hull(self.top_pts + [(x, y + h) for x, y in self.top_pts])

    def vertex(self, which: str) -> Point:
        """Screen point of a top-face corner: 'top', 'right', 'bottom', 'left'."""
        x, y = {
            "top": (-self.w / 2, -self.d / 2),
            "right": (self.w / 2, -self.d / 2),
            "bottom": (self.w / 2, self.d / 2),
            "left": (-self.w / 2, self.d / 2),
        }[which]
        return to_screen(cx=self.cx, cy=self.cy, x=x, y=y)

    def vspan(self, x: float) -> tuple[float, float] | None:
        """(top, bottom) screen y where a vertical line at x meets the outline, or None."""
        ys = [
            y0 + (y1 - y0) * (x - x0) / (x1 - x0)
            for (x0, y0), (x1, y1) in zip(
                self.body, self.body[1:] + self.body[:1], strict=False
            )
            if x0 != x1 and min(x0, x1) <= x <= max(x0, x1)
        ]
        return (min(ys), max(ys)) if ys else None

    def hspan(self, y: float) -> tuple[float, float] | None:
        """(left, right) screen x where a horizontal line at y meets the outline, or None."""
        xs = [
            x0 + (x1 - x0) * (y - y0) / (y1 - y0)
            for (x0, y0), (x1, y1) in zip(
                self.body, self.body[1:] + self.body[:1], strict=False
            )
            if y0 != y1 and min(y0, y1) <= y <= max(y0, y1)
        ]
        return (min(xs), max(xs)) if xs else None

    def contains(self, x: float, y: float, margin: float = 0.0) -> bool:
        """Return whether (x, y) is inside the outline by more than margin screen units."""
        if not point_in_poly(x, y, self.body):
            return False
        if margin <= 0:
            return True
        return all(
            point_in_poly(x + dx, y + dy, self.body)
            for dx, dy in ((margin, 0), (-margin, 0), (0, margin), (0, -margin))
        )

    def svg(self, *, top: str, side: str, stroke: str, sw: float = 2.0) -> str:
        """Return the slab as SVG: body in the side color, top face in the top color."""
        return (
            f'<polygon points="{poly(self.body)}" fill="{side}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linejoin="round"/>'
            f'<polygon points="{poly(self.top_pts)}" fill="{top}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linejoin="round"/>'
        )

    def shadow(self, dy: float = 40) -> str:
        """Return a soft shadow of the top face, dy below the slab's bottom."""
        pts = [(x, y + self.h + dy) for x, y in self.top_pts]
        return f'<polygon points="{poly(pts)}" fill="#1e293b" opacity="0.10" filter="url(#soft)"/>'


# --- text and icons ---------------------------------------------------------------------


def text(
    *,
    x: float,
    y: float,
    s: object,
    font: str,
    size: float,
    fill: str,
    weight: int = 400,
    anchor: str = "start",
    baseline: str | None = None,
    transform: str | None = None,
) -> str:
    """Return an SVG text element; s is escaped."""
    tr = f' transform="{transform}"' if transform else ""
    bl = f' dominant-baseline="{baseline}"' if baseline else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}"{tr} text-anchor="{anchor}"{bl} font-family="{font}" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}">{escape(str(s))}</text>'
    )


def icon_inner(name: str) -> str:
    """Return the inner SVG content of an icon."""
    path = icons.source(name=name)
    if not path:
        raise KeyError(
            f"icon '{name}' is in neither Feather nor Lucide; draw it in Feather style"
        )
    raw = re.sub(r"<!--.*?-->", "", path.read_text(), flags=re.S)
    return re.search(r"<svg[^>]*>(.*)</svg>", raw, re.S).group(1).strip()


def icon(
    *,
    name: str,
    color: str,
    size: float,
    stroke: float = 1.6,
) -> str:
    """Return an icon centered on the origin, drawn to Feather's stroke rules."""
    s = size / 24
    return (
        f'<g transform="scale({s:.3f}) translate(-12,-12)" fill="none" stroke="{color}" '
        f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{icon_inner(name)}</g>'
    )


# --- connectors ---------------------------------------------------------------------------


def rounded_path(points: Sequence[Point], r: float = 16) -> str:
    """Return SVG path data for a polyline with corners rounded to radius r."""
    if len(points) < 3:
        return "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    out = [f"M {points[0][0]:.1f},{points[0][1]:.1f}"]
    for i in range(1, len(points) - 1):
        (x0, y0), (x1, y1), (x2, y2) = points[i - 1], points[i], points[i + 1]
        l1, l2 = math.hypot(x1 - x0, y1 - y0), math.hypot(x2 - x1, y2 - y1)
        k = min(r, l1 / 2, l2 / 2)
        a = (x1 - (x1 - x0) * k / l1, y1 - (y1 - y0) * k / l1)
        b = (x1 + (x2 - x1) * k / l2, y1 + (y2 - y1) * k / l2)
        out.append(f"L {a[0]:.1f},{a[1]:.1f} Q {x1:.1f},{y1:.1f} {b[0]:.1f},{b[1]:.1f}")
    out.append(f"L {points[-1][0]:.1f},{points[-1][1]:.1f}")
    return " ".join(out)


def marker_id(color: str) -> str:
    """Return the id of the arrowhead marker for color."""
    return "arrow-" + color.lstrip("#")


def connector(
    *,
    points: Sequence[Point],
    color: str,
    width: float = 3.0,
    arrow: bool = True,
    opacity: float = 1.0,
    r: float = 16,
) -> str:
    """Return a rounded connector path, with an arrowhead at its end when arrow is set."""
    marker = f' marker-end="url(#{marker_id(color)})"' if arrow else ""
    op = f' opacity="{opacity}"' if opacity < 1 else ""
    return (
        f'<path d="{rounded_path(points, r)}" fill="none" stroke="{color}" stroke-width="{width}" '
        f'stroke-linecap="round"{op}{marker}/>'
    )


def arrow_marker(color: str) -> str:
    """Return the arrowhead marker definition for color."""
    return (
        f'<marker id="{marker_id(color)}" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="13" '
        f'markerHeight="13" markerUnits="userSpaceOnUse" orient="auto-start-reverse">'
        f'<path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>'
    )


def badge(
    *, x: float, y: float, n: object, fill: str, font: str, size: float = 18
) -> str:
    """Return a numbered step badge: a filled disc with n in white."""
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{size - 3}" fill="{fill}"/>' + text(
        x=x,
        y=y,
        s=n,
        font=font,
        size=size,
        fill="#FFFFFF",
        weight=600,
        anchor="middle",
        baseline="central",
    )


def dot(*, x: float, y: float, color: str, r: float = 6) -> str:
    """Return a filled circle."""
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{color}"/>'


# --- document -----------------------------------------------------------------------------


def svg_doc(
    *,
    width: float,
    height: float,
    body: str,
    marker_colors: Iterable[str],
    background: str,
    title: str | None = None,
    desc: str | None = None,
) -> str:
    """Return a complete SVG document: metadata, arrow markers, background, and body."""
    defs = "".join(arrow_marker(c) for c in sorted(set(marker_colors)))
    meta = (f"<title>{escape(title)}</title>" if title else "") + (
        f"<desc>{escape(desc)}</desc>" if desc else ""
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}">{meta}'
        f'<defs>{defs}<filter id="soft" x="-30%" y="-30%" width="160%" height="160%">'
        f'<feGaussianBlur stdDeviation="18"/></filter></defs>'
        f'<rect width="{width:.0f}" height="{height:.0f}" fill="{background}"/>{body}</svg>\n'
    )
