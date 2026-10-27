"""PNG export through headless Chrome in iso_diagram.render."""

import subprocess

from pathlib import Path

import pytest

from iso_diagram import render
from iso_diagram.iso import svg_doc


def test_browser_takes_the_first_absolute_candidate_that_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chrome = tmp_path / "chrome"
    chrome.touch()
    monkeypatch.setattr(render, "CANDIDATES", [str(tmp_path / "missing"), str(chrome)])
    assert render.browser() == str(chrome)


def test_browser_looks_up_bare_names_on_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chromium = tmp_path / "chromium"
    chromium.touch()
    monkeypatch.setattr(render, "CANDIDATES", ["chromium"])
    monkeypatch.setattr(render.shutil, "which", lambda name: str(chromium))
    assert render.browser() == str(chromium)


def test_browser_exits_when_none_is_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(render, "CANDIDATES", ["no-such-browser"])
    monkeypatch.setattr(render.shutil, "which", lambda name: None)
    with pytest.raises(SystemExit, match="needs Chrome or Chromium"):
        render.browser()


def test_png_screenshots_the_svg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(render, "browser", lambda: "chrome")
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kwargs: calls.append(cmd))
    svg = tmp_path / "d.svg"
    render.png(
        svg_path=svg, png_path=tmp_path / "d.png", width=100.6, height=50, scale=3
    )
    (cmd,) = calls
    assert cmd[0] == "chrome"
    assert "--window-size=101,50" in cmd
    assert "--force-device-scale-factor=3" in cmd
    assert cmd[-1] == svg.resolve().as_uri()


@pytest.mark.parametrize(("width", "size"), [(1234.6, "1235"), (1234.4, "1234")])
def test_png_window_matches_the_svg_size(
    width: float, size: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(render, "browser", lambda: "chrome")
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kwargs: calls.append(cmd))
    render.png(
        svg_path=tmp_path / "d.svg",
        png_path=tmp_path / "d.png",
        width=width,
        height=width,
    )
    doc = svg_doc(size=(width, width), body="", background="#FFF")
    assert f'width="{size}"' in doc
    assert f"--window-size={size},{size}" in calls[0]
