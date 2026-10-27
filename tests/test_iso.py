"""Geometry and SVG building blocks in iso_diagram.iso."""

import gc
import math
import warnings

import pytest

from iso_diagram import iso
from iso_diagram.iso import Slab


def test_to_screen_maps_plane_axes_to_isometric_screen() -> None:
    assert iso.to_screen(cx=100, cy=50, x=0, y=0) == (100, 50)
    x, y = iso.to_screen(cx=0, cy=0, x=10, y=0)
    assert x == pytest.approx(10 * iso.C)
    assert y == pytest.approx(5)
    x, y = iso.to_screen(cx=0, cy=0, x=0, y=10)
    assert x == pytest.approx(-10 * iso.C)
    assert y == pytest.approx(5)


def test_plane_matrix_formats_translate_and_matrix() -> None:
    assert iso.plane_matrix(12.345, 6) == (
        f"translate(12.3,6.0) matrix({iso.C:.5f},0.5,{-iso.C:.5f},0.5,0,0)"
    )


def test_rr_points_stay_within_the_rectangle() -> None:
    pts = iso.rr_points(w=100, d=60, r=10, steps=4)
    assert len(pts) == 4 * 5
    assert all(-50 - 1e-9 <= x <= 50 + 1e-9 for x, _ in pts)
    assert all(-30 - 1e-9 <= y <= 30 + 1e-9 for _, y in pts)


def test_rr_points_clamps_radius_to_half_the_short_side() -> None:
    pts = iso.rr_points(w=100, d=20, r=50, steps=2)
    assert min(y for _, y in pts) == pytest.approx(-10)
    assert max(y for _, y in pts) == pytest.approx(10)


def test_hull_drops_interior_points_and_duplicates() -> None:
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    hull = iso.hull([*square, (5, 5), (0, 0)])
    assert sorted(hull) == sorted(square)


def test_hull_returns_short_inputs_unchanged() -> None:
    assert iso.hull([(1, 2), (1, 2), (3, 4)]) == [(1, 2), (3, 4)]


def test_point_in_poly() -> None:
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert iso.point_in_poly(5, 5, square)
    assert not iso.point_in_poly(15, 5, square)


def test_poly_formats_points() -> None:
    assert iso.poly([(1, 2.25), (3.5, 4)]) == "1.0,2.2 3.5,4.0"


@pytest.fixture
def slab() -> Slab:
    return Slab(name="s", cx=200, cy=200, w=100, d=100, h=20, r=10)


def test_slab_vertex_corners(slab: Slab) -> None:
    top, right = slab.vertex("top"), slab.vertex("right")
    bottom, left = slab.vertex("bottom"), slab.vertex("left")
    assert top[1] < left[1] < bottom[1]
    assert left[1] == pytest.approx(right[1])
    assert left[0] < top[0] < right[0]
    assert top[0] == pytest.approx(bottom[0])


def test_slab_spans_cover_the_body(slab: Slab) -> None:
    top, bottom = slab.vspan(200)
    assert top < 200 < bottom
    left, right = slab.hspan(200)
    assert left < 200 < right
    assert slab.vspan(10_000) is None
    assert slab.hspan(-10_000) is None


def test_slab_contains_respects_margin(slab: Slab) -> None:
    assert slab.contains(200, 200)
    assert not slab.contains(0, 0)
    _, right = slab.hspan(200)
    assert slab.contains(right - 2, 200)
    assert not slab.contains(right - 2, 200, margin=5)


def test_slab_svg_and_shadow(slab: Slab) -> None:
    svg = slab.svg(top="#111111", side="#222222", stroke="#333333", sw=1.5)
    assert svg.count("<polygon") == 2
    assert 'fill="#222222"' in svg
    assert 'fill="#111111"' in svg
    assert 'stroke-width="1.5"' in svg
    assert 'filter="url(#soft)"' in slab.shadow(dy=10)


def test_slab_is_keyword_only() -> None:
    with pytest.raises(TypeError):
        Slab("s", 0, 0, 10, 10, 2)  # type: ignore[misc]


def test_text_escapes_and_sets_optional_attributes() -> None:
    out = iso.text(
        x=1,
        y=2,
        s="a < b & c",
        font="Roboto",
        size=20,
        fill="#000",
        anchor="middle",
        baseline="central",
        transform="rotate(-90)",
    )
    assert "a &lt; b &amp; c" in out
    assert 'dominant-baseline="central"' in out
    assert 'transform="rotate(-90)"' in out
    plain = iso.text(x=1, y=2, s="x", font="Roboto", size=20, fill="#000")
    assert "dominant-baseline" not in plain
    assert "transform" not in plain


def test_text_is_keyword_only() -> None:
    with pytest.raises(TypeError):
        iso.text(1, 2, "x", "Roboto", 20, "#000")  # type: ignore[misc]


def test_icon_draws_the_cached_icon() -> None:
    out = iso.icon(name="server", color="#123456", size=48)
    assert out.startswith('<g transform="scale(2.000) translate(-12,-12)"')
    assert 'stroke="#123456"' in out
    assert "<path" in out


def test_icon_inner_strips_comments(icon_cache) -> None:
    path = icon_cache / "feather" / "globe.svg"
    path.write_text('<!-- note --><svg viewBox="0 0 24 24"><circle r="1"/></svg>')
    assert iso.icon_inner("globe") == '<circle r="1"/>'


def test_icon_inner_rejects_unknown_names() -> None:
    with pytest.raises(KeyError, match="draw it in Feather style"):
        iso.icon_inner("no-such-icon")


def test_rounded_path_straight_and_cornered() -> None:
    assert iso.rounded_path([(0, 0), (10, 0)]) == "M 0.0,0.0 L 10.0,0.0"
    path = iso.rounded_path([(0, 0), (100, 0), (100, 100)], r=10)
    assert path.startswith("M 0.0,0.0 L 90.0,0.0 Q 100.0,0.0 100.0,10.0")
    assert path.endswith("L 100.0,100.0")


def test_rounded_path_clamps_radius_on_short_legs() -> None:
    path = iso.rounded_path([(0, 0), (4, 0), (4, 4)], r=10)
    assert "L 2.0,0.0 Q 4.0,0.0 4.0,2.0" in path


def test_connector_marker_and_opacity() -> None:
    pts = [(0, 0), (0, 50)]
    plain = iso.connector(points=pts, color="#AA0000")
    assert 'marker-end="url(#arrow-AA0000)"' in plain
    assert "opacity" not in plain
    faint = iso.connector(points=pts, color="#AA0000", arrow=False, opacity=0.4)
    assert "marker-end" not in faint
    assert 'opacity="0.4"' in faint


def test_arrow_marker_id_matches_connector() -> None:
    assert iso.marker_id("#AA0000") == "arrow-AA0000"
    assert 'id="arrow-AA0000"' in iso.arrow_marker("#AA0000")


def test_badge_and_dot() -> None:
    badge = iso.badge(x=10, y=20, n=3, fill="#00F", font="Roboto", size=18)
    assert 'r="15"' in badge
    assert ">3</text>" in badge
    assert iso.dot(x=1, y=2, color="#F00") == (
        '<circle cx="1.0" cy="2.0" r="6" fill="#F00"/>'
    )


def test_svg_doc_includes_markers_metadata_and_background() -> None:
    doc = iso.svg_doc(
        width=100.4,
        height=50,
        body="<g/>",
        marker_colors=["#B00", "#A00", "#B00"],
        background="#FFF",
        title="T & co",
        desc="D",
    )
    assert doc.startswith('<svg xmlns="http://www.w3.org/2000/svg" width="100"')
    assert "<title>T &amp; co</title><desc>D</desc>" in doc
    assert doc.count("<marker") == 2
    assert doc.index("arrow-A00") < doc.index("arrow-B00")
    assert doc.endswith('fill="#FFF"/><g/></svg>\n')


def test_svg_doc_omits_empty_metadata() -> None:
    doc = iso.svg_doc(width=10, height=10, body="", marker_colors=[], background="#FFF")
    assert "<title>" not in doc
    assert "<desc>" not in doc


def test_iso_constants() -> None:
    assert pytest.approx(math.sqrt(3) / 2) == iso.C
    assert pytest.approx(1 / math.sqrt(3)) == iso.TAN30


def test_icon_inner_closes_the_icon_file() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ResourceWarning)
        iso.icon_inner("globe")
        gc.collect()
    assert not [w for w in caught if issubclass(w.category, ResourceWarning)]
