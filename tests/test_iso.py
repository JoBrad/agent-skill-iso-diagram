"""Geometry and SVG building blocks in iso_diagram.iso."""

import gc
import math
import warnings

import pytest

from iso_diagram import iso
from iso_diagram.checks import Registry
from iso_diagram.iso import Slab
from iso_diagram.theme import Theme


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
    vspan, hspan = slab.vspan(200), slab.hspan(200)
    assert vspan is not None
    assert hspan is not None
    top, bottom = vspan
    assert top < 200 < bottom
    left, right = hspan
    assert left < 200 < right
    assert slab.vspan(10_000) is None
    assert slab.hspan(-10_000) is None


def test_slab_contains_respects_margin(slab: Slab) -> None:
    assert slab.contains(200, 200)
    assert not slab.contains(0, 0)
    span = slab.hspan(200)
    assert span is not None
    _, right = span
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


STYLE = iso.TextStyle(font="Roboto", size=20, fill="#000")


def test_text_escapes_and_sets_optional_attributes() -> None:
    out = iso.text(
        x=1,
        y=2,
        s="a < b & c",
        style=iso.TextStyle(
            font="Roboto", size=20, fill="#000", anchor="middle", baseline="central"
        ),
        transform="rotate(-90)",
    )
    assert "a &lt; b &amp; c" in out
    assert 'dominant-baseline="central"' in out
    assert 'transform="rotate(-90)"' in out
    plain = iso.text(
        x=1, y=2, s="x", style=iso.TextStyle(font="Roboto", size=20, fill="#000")
    )
    assert "dominant-baseline" not in plain
    assert "transform" not in plain


def test_text_is_keyword_only() -> None:
    with pytest.raises(TypeError):
        iso.text(1, 2, "x", STYLE)  # type: ignore[misc]
    with pytest.raises(TypeError):
        iso.TextStyle("Roboto", 20, "#000")  # type: ignore[misc]


def test_icon_draws_the_cached_icon() -> None:
    out = iso.icon(name="server", color="#123456", size=48)
    assert out.startswith('<g transform="scale(2.000) translate(-12,-12)"')
    assert 'stroke="#123456"' in out
    assert "<path" in out


def test_icon_inner_strips_comments(icon_cache) -> None:
    path = icon_cache / "feather" / "globe.svg"
    path.write_text('<!-- note --><svg viewBox="0 0 24 24"><circle r="1"/></svg>')
    assert iso.icon_inner("globe") == '<circle r="1"/>'


def test_icon_inner_rejects_a_file_without_an_svg(icon_cache) -> None:
    (icon_cache / "feather" / "globe.svg").write_text("<html>not an icon</html>")
    with pytest.raises(ValueError, match=r"icon 'globe': .* holds no <svg> element"):
        iso.icon_inner("globe")


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
    badge = iso.badge(at=(10, 20), n=3, fill="#00F", font="Roboto", size=18)
    assert '<circle cx="10.0" cy="20.0"' in badge
    assert 'r="15"' in badge
    assert ">3</text>" in badge
    assert iso.dot(x=1, y=2, color="#F00") == (
        '<circle cx="1.0" cy="2.0" r="6" fill="#F00"/>'
    )


def test_svg_doc_includes_markers_metadata_and_background() -> None:
    pts = [(0, 0), (0, 50)]
    body = "".join(
        [
            iso.connector(points=pts, color="#B00"),
            iso.connector(points=pts, color="#A00"),
            iso.connector(points=pts, color="#B00"),
            iso.connector(points=pts, color="#C00", arrow=False),
        ]
    )
    doc = iso.svg_doc(
        size=(100.4, 50), body=body, background="#FFF", title="T & co", desc="D"
    )
    assert doc.startswith('<svg xmlns="http://www.w3.org/2000/svg" width="100"')
    assert "<title>T &amp; co</title><desc>D</desc>" in doc
    assert doc.count("<marker") == 2
    assert doc.index("arrow-A00") < doc.index("arrow-B00")
    assert "arrow-C00" not in doc
    assert doc.endswith(f'fill="#FFF"/>{body}</svg>\n')


def test_svg_doc_omits_empty_metadata() -> None:
    doc = iso.svg_doc(size=(10, 10), body="", background="#FFF")
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


def test_caption_wraps_registers_and_sizes_the_canvas() -> None:
    theme = Theme()
    reg = Registry(theme)
    story = "word " * 40
    svg, height = iso.caption(s=story, top=100, width=400, theme=theme, reg=reg)
    lines = svg.count("<text")
    assert lines > 1
    assert height == 100 + 30 + (lines - 1) * 26
    assert len(reg.texts) == lines
    assert reg.check(400, height) == []
    one, one_height = iso.caption(s="short", top=100, width=400, theme=theme, reg=reg)
    assert one.count("<text") == 1
    assert one_height == 130
