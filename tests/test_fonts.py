"""Font subsetting and embedding in iso_diagram.fonts."""

import base64

import pytest

from iso_diagram import fonts
from iso_diagram.theme import Theme


SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg"><defs><style>stale-rule</style></defs>'
    '<text font-family="Roboto, sans-serif">Hi</text>'
    '<text font-family="Roboto, sans-serif" font-weight="600">Bold</text>'
    '<text font-family="\'Roboto Mono\', monospace" font-weight="500">10.0</text>'
    "</svg>"
)


def test_family_of_takes_the_first_unquoted_family() -> None:
    assert fonts.family_of("'Roboto Mono', monospace") == "Roboto Mono"
    assert fonts.family_of('"Roboto", sans-serif') == "Roboto"
    assert fonts.family_of("Roboto") == "Roboto"


def test_used_faces_groups_characters_by_family_and_weight() -> None:
    assert fonts.used_faces(SVG) == {
        ("Roboto", 400): {"H", "i"},
        ("Roboto", 600): {"B", "o", "l", "d"},
        ("Roboto Mono", 500): {"1", "0", "."},
    }


def test_woff2_returns_base64_woff2() -> None:
    data = fonts.woff2(theme=Theme(), kind="sans", weight=600, chars="Hi")
    assert base64.b64decode(data)[:4] == b"wOF2"


def test_embed_adds_one_face_per_family_and_weight() -> None:
    out = fonts.embed(SVG, Theme())
    assert "stale-rule" not in out
    assert out.count("@font-face") == 3
    assert "font-family:'Roboto';font-weight:600;" in out
    assert "font-family:'Roboto Mono';font-weight:500;" in out
    assert out.index("<defs><style>@font-face") > 0


def test_embed_rejects_a_family_the_theme_lacks() -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><defs/><text font-family="Arial">x</text></svg>'
    with pytest.raises(ValueError, match="'Arial', which the theme does not provide"):
        fonts.embed(svg, Theme())


def test_woff2_is_byte_identical_across_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    first = fonts.woff2(theme=Theme(), kind="sans", weight=400, chars="Hello")
    # fontTools stamps the current time into the font unless told not to.
    monkeypatch.setattr("time.time", lambda: 4_102_444_800.0)
    assert fonts.woff2(theme=Theme(), kind="sans", weight=400, chars="Hello") == first
