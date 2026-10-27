"""End-to-end builds through iso-build, checked against golden SVGs.

The golden files in tests/golden/ hold each example's output with the embedded font
data blanked, since the WOFF2 bytes change from build to build. After a deliberate
change to the drawing, regenerate them and review the diff:

    UPDATE_GOLDEN=1 uv run pytest tests/test_build.py
"""

import copy
import json
import os
import re
import sys

from pathlib import Path

import pytest

from iso_diagram import build, render, stack
from iso_diagram.theme import SKILL_DIR, Theme


EXAMPLES = SKILL_DIR / "examples"
GOLDEN = Path(__file__).parent / "golden"
FONT_DATA = re.compile(r"base64,[A-Za-z0-9+/=]+")


def normalized(svg: str) -> str:
    """Return svg with embedded font data blanked, one tag per line for readable diffs."""
    return FONT_DATA.sub("base64,FONT", svg).replace("><", ">\n<")


def run_build(monkeypatch: pytest.MonkeyPatch, *args: str | Path) -> None:
    """Run iso-build with args as its command line."""
    monkeypatch.setattr(sys, "argv", ["iso-build", *map(str, args)])
    build.main()


def write_spec(tmp_path: Path, spec: dict) -> Path:
    """Write spec to a temp file and return its path."""
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    return path


def example(name: str) -> dict:
    """Return a parsed copy of an example spec."""
    return json.loads((EXAMPLES / f"{name}.json").read_text())


@pytest.mark.parametrize("name", ["aws-tree", "aws-stack"])
def test_example_matches_golden(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / f"{name}.svg"
    run_build(monkeypatch, EXAMPLES / f"{name}.json", "-o", out)
    actual = normalized(out.read_text())
    golden = GOLDEN / f"{name}.svg"
    if os.environ.get("UPDATE_GOLDEN"):
        golden.parent.mkdir(exist_ok=True)
        golden.write_text(actual)
    assert actual == golden.read_text()


def test_build_reports_what_it_wrote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "nested" / "tree.svg"
    run_build(monkeypatch, EXAMPLES / "aws-tree.json", "-o", out)
    assert re.fullmatch(
        rf"wrote {re.escape(str(out))} \(\d+ KB, \d+x\d+, theme default\)\n",
        capsys.readouterr().out,
    )


def test_build_png_hands_the_svg_to_render(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(render, "png", lambda **kwargs: calls.append(kwargs))
    out = tmp_path / "tree.svg"
    run_build(
        monkeypatch, EXAMPLES / "aws-tree.json", "-o", out, "--png", "--scale", "3"
    )
    (call,) = calls
    assert call["svg_path"] == out
    assert call["png_path"] == out.with_suffix(".png")
    assert call["scale"] == 3


def test_theme_option_overrides_the_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = example("aws-stack")
    spec["theme"] = "no-such-theme"
    out = tmp_path / "stack.svg"
    run_build(monkeypatch, write_spec(tmp_path, spec), "-o", out, "--theme", "default")
    assert "theme default" in capsys.readouterr().out


@pytest.mark.parametrize("key", ["style", "story", "points"])
def test_spec_must_state_its_story(
    key: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = example("aws-tree")
    del spec[key]
    with pytest.raises(SystemExit, match=f"spec is missing '{key}'"):
        run_build(monkeypatch, write_spec(tmp_path, spec), "-o", tmp_path / "x.svg")


def test_unknown_style_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = example("aws-tree")
    spec["style"] = "iso-cube"
    with pytest.raises(SystemExit, match="unknown style 'iso-cube'"):
        run_build(monkeypatch, write_spec(tmp_path, spec), "-o", tmp_path / "x.svg")


def lengthen_labels(spec: dict, suffix: str) -> dict:
    """Return a copy of spec with suffix appended to every label."""
    spec = copy.deepcopy(spec)

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "label" and isinstance(value, str):
                    node[key] = value + suffix
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(spec)
    return spec


@pytest.mark.parametrize("name", ["aws-tree", "aws-stack"])
def test_layout_issues_block_output(
    name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec = lengthen_labels(example(name), " with a much longer label")
    out = tmp_path / "x.svg"
    with pytest.raises(SystemExit, match=r"layout issue\(s\); nothing written"):
        run_build(monkeypatch, write_spec(tmp_path, spec), "-o", out)
    assert not out.exists()
    assert "ISSUE surface: label" in capsys.readouterr().out


def test_allow_issues_writes_anyway(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = lengthen_labels(example("aws-stack"), " with a much longer label")
    out = tmp_path / "x.svg"
    run_build(monkeypatch, write_spec(tmp_path, spec), "-o", out, "--allow-issues")
    assert out.exists()


def test_theme_option_accepts_a_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    theme = SKILL_DIR / "themes" / "default.json"
    out = tmp_path / "tree.svg"
    run_build(monkeypatch, EXAMPLES / "aws-tree.json", "-o", out, "--theme", theme)
    assert "theme default" in capsys.readouterr().out


def test_markup_in_titles_is_escaped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree_spec = example("aws-tree")
    tree_spec["root"]["label"] = "R&D"
    tree_spec["root"]["desc"] = "Teams <and> partners"
    stack_spec = example("aws-stack")
    stack_spec["layers"][0]["title"] = "R&D <region>"
    for name, spec in [("tree", tree_spec), ("stack", stack_spec)]:
        out = tmp_path / f"{name}.svg"
        run_build(monkeypatch, write_spec(tmp_path, spec), "-o", out, "--allow-issues")
        svg = out.read_text()
        assert "<title>R&amp;D" in svg
        assert "&lt;" in svg


def test_mono_labels_are_measured_in_the_mono_font() -> None:
    spec = example("aws-stack")
    marker = spec["layers"][1]["markers"][0]
    resource = spec["layers"][4]["resources"][0]
    marker["mono"] = resource["mono"] = True
    theme = Theme()
    _, reg, _ = stack.build(spec, theme)
    lengths = {lb.text: lb.length for lb in reg.labels}
    for label in (marker["label"], resource["label"]):
        mono = theme.measure(s=label, size=20, mono=True, weight=600)
        assert mono != theme.measure(s=label, size=20, mono=False, weight=600)
        assert lengths[label] == mono


def test_spec_issues_stop_the_build_before_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = example("aws-tree")
    spec["flows"] = [{"from": spec["root"]["id"], "to": "dbb"}]
    out = tmp_path / "x.svg"
    with pytest.raises(SystemExit, match=r"1 spec issue\(s\); nothing built"):
        run_build(monkeypatch, write_spec(tmp_path, spec), "-o", out, "--allow-issues")
    assert not out.exists()
    assert "ISSUE spec: flows[0].to names no node 'dbb'" in capsys.readouterr().out


def test_spec_theme_path_is_relative_to_the_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    data = json.loads((SKILL_DIR / "themes" / "default.json").read_text())
    data["name"] = "brand"
    (tmp_path / "brand.json").write_text(json.dumps(data))
    spec = example("aws-tree")
    spec["theme"] = "brand.json"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    run_build(monkeypatch, write_spec(tmp_path, spec), "-o", tmp_path / "x.svg")
    assert "theme brand" in capsys.readouterr().out


def test_long_plate_titles_are_issues() -> None:
    spec = example("aws-stack")
    layer = spec["layers"][0]
    layer["title"] = "A plate title far too long to sit between its leader and edge"
    layer["subtitle"] = "A subtitle " * 12
    _, reg, (width, height) = stack.build(spec, Theme())
    issues = reg.check(width, height)
    assert f"fit: '{layer['title']}' runs past the leader of '{layer['id']}'" in issues
    assert any(i.startswith("fit: 'A subtitle A subtitle") for i in issues)
