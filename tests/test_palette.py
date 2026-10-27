"""Theme swatch sheets and color-vision math in iso_diagram.palette."""

import sys

from pathlib import Path

import pytest

from iso_diagram import palette, render
from iso_diagram.theme import Theme


def test_rgb_and_linear_round_trip() -> None:
    assert palette.rgb("#FF8000") == [255, 128, 0]
    assert palette.lin(0) == 0
    assert palette.lin(255) == pytest.approx(1)
    assert palette.lin(10) == pytest.approx(10 / 255 / 12.92)
    linear = [palette.lin(c) for c in palette.rgb("#3366CC")]
    assert palette.to_hex(linear) == "#3366CC"


def test_to_hex_clamps_out_of_gamut_values() -> None:
    assert palette.to_hex([-0.5, 2.0, 0.0]) == "#00FF00"


def test_contrast_against_white() -> None:
    assert palette.contrast("#FFFFFF") == pytest.approx(1)
    assert palette.contrast("#000000") == pytest.approx(21)


def test_lab_of_white_and_black() -> None:
    assert palette.lab([1, 1, 1]) == pytest.approx((100, 0, 0), abs=0.05)
    assert palette.lab([0, 0, 0]) == pytest.approx((0, 0, 0), abs=1e-6)


def test_simulate_linear_with_identity_is_unchanged() -> None:
    identity = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    linear = [palette.lin(c) for c in palette.rgb("#3366CC")]
    assert palette.simulate_linear("#3366CC", identity) == pytest.approx(linear)


def test_build_reports_each_simulation() -> None:
    svg, report, width = palette.build(Theme())
    assert svg.startswith("<svg")
    assert "default palette" in svg
    assert [line.split()[0] for line in report] == ["Typical", *palette.MACHADO]
    assert all("closest pair" in line for line in report)
    assert width > 0


def test_main_writes_the_sheet_into_a_new_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "new" / "sheet.svg"
    monkeypatch.setattr(sys, "argv", ["iso-palette", "default", "-o", str(out)])
    palette.main()
    assert out.read_text().startswith("<svg")
    printed = capsys.readouterr().out
    assert f"wrote {out}" in printed
    assert "Deuteranopia" in printed


def test_main_png_hands_the_sheet_to_render(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(render, "png", lambda **kwargs: calls.append(kwargs))
    out = tmp_path / "new" / "sheet.svg"
    monkeypatch.setattr(sys, "argv", ["iso-palette", "-o", str(out), "--png"])
    palette.main()
    (call,) = calls
    assert call["svg_path"] == out
    assert call["png_path"] == out.with_suffix(".png")
    assert call["height"] == 1070


def test_main_writes_into_an_existing_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "sheet.svg"
    monkeypatch.setattr(sys, "argv", ["iso-palette", "-o", str(out)])
    palette.main()
    assert out.exists()
