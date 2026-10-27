"""Layout rules and spec checks in iso_diagram.checks."""

import pytest

from iso_diagram import stack
from iso_diagram.checks import (
    INSET,
    RESOURCE_COUNTS,
    Label,
    Registry,
    Surface,
    spec_issues,
)
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
    top_span, bottom_span = top.vspan(300), bottom.vspan(300)
    assert top_span is not None
    assert bottom_span is not None
    _, top_low = top_span
    bottom_high, _ = bottom_span
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


def test_screen_text_inside_its_box_and_the_canvas(reg: Registry) -> None:
    reg.text(text="fits", left=10, right=90, within="card", box=(0, 100))
    reg.text(text="caption", left=40, right=960)
    assert reg.check(1000, 1000) == []


def test_screen_text_past_its_box_or_the_canvas(reg: Registry) -> None:
    reg.text(text="wide", left=10, right=120, within="card 'A'", box=(0, 100))
    reg.text(text="left", left=-5, right=50, within="card 'A'", box=(0, 100))
    reg.text(text="caption", left=40, right=1040)
    assert reg.check(1000, 1000) == [
        "fit: 'wide' runs past the card 'A'",
        "fit: 'left' runs past the card 'A'",
        "fit: 'caption' runs past the canvas",
    ]


def tree_spec(**overrides: object) -> dict:
    """Return a minimal valid iso-tree spec, with top-level keys overridden."""
    spec: dict = {
        "style": "iso-tree",
        "story": "S",
        "points": [],
        "root": {"id": "r", "children": [{"id": "a"}, {"id": "b"}]},
    }
    spec.update(overrides)
    return spec


def stack_spec(**overrides: object) -> dict:
    """Return a minimal valid iso-stack spec, with top-level keys overridden."""
    spec: dict = {
        "style": "iso-stack",
        "story": "S",
        "points": [],
        "columns": ["web", "db"],
        "layers": [
            {"id": "top", "title": "Top"},
            {
                "id": "bottom",
                "title": "Bottom",
                "resources": [{"column": "db", "label": "DB", "icon": "database"}],
            },
        ],
    }
    spec.update(overrides)
    return spec


def test_valid_specs_have_no_spec_issues() -> None:
    assert (
        spec_issues(tree_spec(path=["r", "a"], flows=[{"from": "a", "to": "b"}])) == []
    )
    assert spec_issues(tree_spec(source={"id": "net"}, path=["net", "r", "a"])) == []
    steps = [
        {"from": "source", "column": "web", "to": "bottom"},
        {"from": "web", "to": "db", "via": "top", "at": "bottom"},
    ]
    assert spec_issues(stack_spec(steps=steps, source={"column": "web"})) == []


def test_duplicate_tree_ids_are_spec_issues() -> None:
    root = {
        "id": "r",
        "children": [
            {"id": "vpc-1", "children": [{"id": "private"}]},
            {"id": "vpc-2", "children": [{"id": "private"}]},
        ],
    }
    assert spec_issues(tree_spec(root=root)) == [
        "spec: node id 'private' is used 2 times; ids must be unique"
    ]


def test_tree_references_are_spec_issues() -> None:
    spec = tree_spec(
        root={"id": "r", "children": [{"label": "no id"}]},
        flows=[{"from": "a", "to": "dbb"}],
        path=["r", "zz"],
    )
    spec["root"]["children"].append({"id": "a"})
    assert spec_issues(spec) == [
        "spec: root.children[0] is missing 'id'",
        "spec: flows[0].to names no node 'dbb'",
        "spec: path[1] names no node 'zz'",
    ]
    assert spec_issues(tree_spec(root=None)) == ["spec: missing 'root'"]


def test_stack_references_are_spec_issues() -> None:
    spec = stack_spec(
        steps=[
            {"from": "source", "column": "app", "to": "middle"},
            {"from": "web", "to": "db", "via": "nowhere", "at": "bottom"},
        ],
        source={"column": "app"},
    )
    spec["layers"][1]["resources"][0]["count"] = 4
    spec["layers"][1]["zones"] = [{"column": "cache", "label": "Cache"}]
    spec["layers"].append({"id": "top", "title": "Again"})
    assert spec_issues(spec) == [
        "spec: layer id 'top' is used 2 times; ids must be unique",
        "spec: layers[1].zones[0].column names no column 'cache'",
        "spec: layers[1].resources[0].count is 4; use 1, 2, or 3",
        "spec: steps[0].column names no column 'app'",
        "spec: steps[0].to names no layer 'middle'",
        "spec: steps[1].via names no layer 'nowhere'",
        "spec: source.column names no column 'app'",
    ]


def test_stack_required_keys_are_spec_issues() -> None:
    spec = stack_spec(steps=[{"from": "web"}])
    del spec["columns"]
    del spec["layers"][0]["title"]
    assert spec_issues(spec) == ["spec: missing 'columns'"]
    spec = stack_spec(steps=[{"from": "web", "to": "db"}])
    del spec["layers"][0]["title"]
    assert spec_issues(spec) == [
        "spec: layers[0] is missing 'title'",
        "spec: steps[0] is missing 'via'",
        "spec: steps[0] is missing 'at'",
    ]


def test_resource_counts_match_what_iso_stack_draws() -> None:
    assert set(RESOURCE_COUNTS) == set(stack.RES_OFFSETS)
