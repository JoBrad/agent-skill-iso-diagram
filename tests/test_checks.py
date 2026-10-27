"""Layout rules in iso_diagram.checks."""

import pytest

from iso_diagram.checks import INSET, Label, Registry, Surface
from iso_diagram.iso import Slab
from iso_diagram.theme import Theme


@pytest.fixture
def reg() -> Registry:
    return Registry(Theme())


PLATE = Surface(name="plate", w=200, d=200)


def label(**overrides: object) -> Label:
    """Return a label that passes every rule, with fields overridden."""
    fields: dict = {
        "surface": PLATE,
        "text": "ok",
        "center": (0, 0),
        "size": 20,
        "length": 40,
    }
    fields.update(overrides)
    return Label(**fields)


def test_empty_registry_has_no_issues(reg: Registry) -> None:
    assert reg.check(1000, 1000) == []


def test_layout_issues_pass_through(reg: Registry) -> None:
    reg.issues.append("route: none")
    assert reg.check(1000, 1000) == ["route: none"]


def test_slab_returns_what_it_records(reg: Registry) -> None:
    s = Slab(name="a", cx=100, cy=100, w=50, d=50, h=10)
    assert reg.slab(s) is s
    assert reg.slabs == [s]


def test_child_inset_ok_and_too_close(reg: Registry) -> None:
    reg.child(parent=PLATE, name="fits", rect=(0, 0, 100, 100))
    reg.child(parent=PLATE, name="tight", rect=(40, 0, 100, 100))
    assert reg.check(1000, 1000) == [
        f"inset: 'tight' is 10 units from the edge of 'plate' (needs {INSET})"
    ]


def test_label_below_the_text_floor(reg: Registry) -> None:
    floor = reg.theme.min_surface_text
    reg.label(label(text="tiny", size=floor - 1))
    assert reg.check(1000, 1000) == [
        f"text: 'tiny' on 'plate' is {floor - 1}px (floor {floor})"
    ]


def test_label_running_off_its_surface(reg: Registry) -> None:
    reg.label(label(text="long", length=500))
    reg.label(label(text="across", length=500, along_y=False))
    reg.label(label(text="edge", center=(95, 0)))
    assert reg.check(1000, 1000) == [
        "surface: label 'long' runs off 'plate'",
        "surface: label 'across' runs off 'plate'",
        "surface: label 'edge' runs off 'plate'",
    ]


def test_slab_past_the_canvas(reg: Registry) -> None:
    reg.slab(Slab(name="inside", cx=100, cy=100, w=50, d=50, h=10))
    reg.slab(Slab(name="outside", cx=990, cy=100, w=50, d=50, h=10))
    assert reg.check(1000, 1000) == ["canvas: 'outside' extends past the canvas"]


def test_connector_route_shape(reg: Registry) -> None:
    reg.connector(name="diag", points=[(0, 0), (50, 50)])
    reg.connector(name="zigzag", points=[(0, 0), (0, 50), (50, 50), (50, 100)])
    reg.connector(name="elbow", points=[(0, 0), (0, 50), (50, 50)])
    assert reg.check(1000, 1000) == [
        "route: 'diag' has a diagonal segment",
        "route: 'zigzag' has 2 bends",
    ]


def test_connector_crossing_a_slab(reg: Registry) -> None:
    reg.slab(Slab(name="wall", cx=300, cy=300, w=80, d=80, h=10))
    reg.connector(name="through", points=[(300, 100), (300, 600)])
    reg.connector(name="past", points=[(100, 100), (100, 600)])
    issues = reg.check(1000, 1000)
    assert len(issues) == 1
    assert issues[0].startswith("connector: 'through' crosses 'wall' near (300,")


def test_connector_ends_on_outlines(reg: Registry) -> None:
    top = reg.slab(Slab(name="top", cx=300, cy=200, w=80, d=80, h=10))
    bottom = reg.slab(Slab(name="bottom", cx=300, cy=500, w=80, d=80, h=10))
    _, top_low = top.vspan(300)
    bottom_high, _ = bottom.vspan(300)
    reg.connector(
        name="good",
        points=[(300, top_low), (300, bottom_high)],
        source=top,
        target=bottom,
    )
    reg.connector(
        name="short", points=[(300, top_low), (300, bottom_high - 30)], target=bottom
    )
    reg.connector(
        name="late", points=[(300, top_low + 30), (300, bottom_high)], source=top
    )
    issues = reg.check(1000, 1000)
    assert "connector: 'short' end does not sit on the outline of 'bottom'" in issues
    assert "connector: 'late' start does not sit on the outline of 'top'" in issues
    assert not any("'good'" in i for i in issues)


def test_record_methods_are_keyword_only(reg: Registry) -> None:
    with pytest.raises(TypeError):
        reg.child(PLATE, "c", (0, 0, 1, 1))  # type: ignore[misc]
    with pytest.raises(TypeError):
        reg.connector("c", [(0, 0), (0, 1)])  # type: ignore[misc]
