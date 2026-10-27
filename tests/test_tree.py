"""iso-tree layout and routing in iso_diagram.tree, beyond the AWS example."""

import json
import os

from pathlib import Path

import pytest

from tests.test_build import GOLDEN, normalized

from iso_diagram import tree
from iso_diagram.iso import Slab
from iso_diagram.theme import Theme


def leaf(node_id: str) -> dict:
    return {"id": node_id, "label": node_id}


# Exercises what the AWS example does not: unstacked leaves, a labeled flow, a path
# with no source, a slot override, a level without a card, and no caption.
VARIANT = {
    "style": "iso-tree",
    "title": "Variant",
    "story": "Two teams share a platform; one service calls the other.",
    "points": ["Two teams", "One call"],
    "stack_leaves": False,
    "path": ["platform", "team-a", "svc-a"],
    "flows": [{"from": "svc-a", "to": "svc-b", "label": "HTTPS"}],
    "levels": [
        {"card": {"title": "Platform", "items": ["Shared"]}},
        {},
        {"card": {"title": "Services", "items": ["svc-a", "svc-b", "svc-c"]}},
    ],
    "root": {
        "id": "platform",
        "label": "Platform",
        "children": [
            {
                "id": "team-a",
                "label": "Team A",
                "slot": "rose",
                "children": [leaf("svc-a"), leaf("svc-c")],
            },
            {"id": "team-b", "label": "Team B", "children": [leaf("svc-b")]},
        ],
    },
}


def test_variant_matches_golden() -> None:
    svg, reg, (width, height) = tree.build(VARIANT, Theme())
    actual = normalized(svg) + "\n" + json.dumps(reg.check(width, height), indent=1)
    golden = GOLDEN / "tree-variant.txt"
    if os.environ.get("UPDATE_GOLDEN"):
        golden.write_text(actual)
    assert actual == golden.read_text()


def test_default_caption() -> None:
    assert tree.default_caption({"story": "S"}) == "S"
    assert tree.default_caption({"story": "S", "path": ["a"]}).startswith(
        "S Faint lines"
    )
    assert tree.default_caption({}) == ""


def test_only_child_keeps_its_parents_size() -> None:
    root = tree.Node(
        {"id": "r", "children": [{"id": "c", "children": [leaf("x"), leaf("y")]}]}, 0
    )
    child = root.children[0]
    assert tree.size_step(child) == 0
    assert tree.size_step(child.children[0]) == 1
    assert [n.id for n in root.walk()] == ["r", "c", "x", "y"]


def test_stacked_leaves_use_tiles() -> None:
    root = tree.Node({"id": "r", "children": [leaf("x"), leaf("y")]}, 0)
    root.stacked = True
    assert tree.footprint(root.children[0]) == tree.STACK_TILE
    assert tree.subtree_width(root) >= tree.screen_width(root.children[0])


def slab(name: str, cx: float, cy: float, size: float = 100) -> Slab:
    return Slab(name=name, cx=cx, cy=cy, w=size, d=size, h=20)


def test_clear_rejects_crossing_and_crowding() -> None:
    wall = slab("wall", 300, 300)
    assert tree.clear(pts=[(100, 100), (100, 500)], slabs=[wall], placed=[])
    assert not tree.clear(pts=[(300, 100), (300, 500)], slabs=[wall], placed=[])
    vertical = [[(105, 100), (105, 500)]]
    assert not tree.clear(pts=[(100, 100), (100, 500)], slabs=[], placed=vertical)
    horizontal = [[(100, 105), (500, 105)]]
    assert not tree.clear(pts=[(100, 100), (500, 100)], slabs=[], placed=horizontal)
    assert tree.clear(pts=[(100, 100), (100, 500)], slabs=[], placed=horizontal)


def test_route_parent_child_straight_down() -> None:
    parent, child = slab("p", 300, 100), slab("c", 300, 400)
    pts = tree.route_parent_child(p=parent, q=child, slabs=[parent, child], placed=[])
    assert len(pts) == 2
    assert pts[0][0] == pts[1][0]


def test_route_parent_child_bends_out_a_side_corner() -> None:
    parent, child = slab("p", 300, 100), slab("c", 700, 400)
    pts = tree.route_parent_child(p=parent, q=child, slabs=[parent, child], placed=[])
    assert len(pts) == 3
    assert pts[0][1] == pts[1][1]
    assert pts[1][0] == pts[2][0]


def test_route_parent_child_gives_up_when_blocked() -> None:
    parent, child = slab("p", 300, 100), slab("c", 300, 400)
    wall = Slab(name="wall", cx=300, cy=250, w=900, d=900, h=20)
    assert tree.route_parent_child(p=parent, q=child, slabs=[wall], placed=[]) is None


def test_route_flow_straight_across() -> None:
    a, b = slab("a", 200, 300), slab("b", 600, 300)
    pts = tree.route_flow(a=a, b=b, slabs=[a, b], placed=[])
    assert len(pts) == 2
    assert pts[0][1] == pts[1][1]
    assert pts[0][0] < pts[1][0]
    back = tree.route_flow(a=b, b=a, slabs=[a, b], placed=[])
    assert back[0][0] > back[1][0]


def test_route_flow_goes_under_when_not_level() -> None:
    a, b = slab("a", 200, 100), slab("b", 600, 500)
    pts = tree.route_flow(a=a, b=b, slabs=[a, b], placed=[])
    assert len(pts) == 4


def test_route_flow_gives_up_when_blocked() -> None:
    a, b = slab("a", 200, 100), slab("b", 600, 500)
    wall = Slab(name="wall", cx=400, cy=700, w=900, d=300, h=20)
    assert tree.route_flow(a=a, b=b, slabs=[a, b, wall], placed=[]) is None


def test_unroutable_children_and_flows_become_issues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tree, "route_parent_child", lambda **kwargs: None)
    monkeypatch.setattr(tree, "route_flow", lambda **kwargs: None)
    _, reg, _ = tree.build(VARIANT, Theme())
    assert "route: no clean route from 'platform' to 'team-a'" in reg.issues
    assert "route: no clean route for flow 'svc-a' to 'svc-b'" in reg.issues


def test_card_without_room_for_its_leader(tmp_path: Path) -> None:
    spec = json.loads(json.dumps(VARIANT))
    spec["levels"][0]["card"]["items"] = [f"item {i}" for i in range(40)]
    _, reg, _ = tree.build(spec, Theme())
    assert any(
        i.startswith("leader: 'Services' card cannot sit level") for i in reg.issues
    )
