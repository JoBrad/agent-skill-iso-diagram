"""Theme loading and text measurement in iso_diagram.theme."""

import json

from pathlib import Path

import pytest

from iso_diagram.shared import SKILL_DIR
from iso_diagram.theme import Theme, tint


DEFAULT = SKILL_DIR / "themes" / "default.json"


def test_tint_mixes_toward_white() -> None:
    assert tint("#000000", 0) == "#000000"
    assert tint("#000000", 1) == "#FFFFFF"
    assert tint("#204080", 0.5) == "#90A0C0"


def test_default_theme_loads_by_name() -> None:
    theme = Theme()
    assert theme.data["name"] == "default"
    assert theme.path == DEFAULT
    assert theme.sans.startswith("Roboto, ")
    assert theme.mono.startswith("'Roboto Mono', ")


def test_theme_loads_from_a_path_object(tmp_path: Path) -> None:
    data = json.loads(DEFAULT.read_text())
    data["name"] = "copy"
    path = tmp_path / "copy.json"
    path.write_text(json.dumps(data))
    assert Theme(path).data["name"] == "copy"


def test_theme_loads_from_a_str_path() -> None:
    assert Theme(str(DEFAULT)).data["name"] == "default"


def test_tier_uses_the_text_shade_to_outline_light_slots() -> None:
    theme = Theme()
    light = theme.data["light_slots"][0]
    dark = next(s for s in theme.order if s not in theme.data["light_slots"])
    light_tier, dark_tier = theme.tier(light), theme.tier(dark)
    assert light_tier["stroke"] == light_tier["text"]
    assert dark_tier["stroke"] == dark_tier["hue"]
    assert set(dark_tier) == {"slot", "hue", "top", "side", "stroke", "text"}


def test_flow_is_the_flow_slot() -> None:
    theme = Theme()
    assert theme.flow == theme.tier(theme.flow_slot)


def test_level_slots_end_with_the_leaf() -> None:
    theme = Theme()
    assert theme.level_slots(3) == [*theme.order[:2], theme.leaf]
    assert theme.level_slots(1) == [theme.leaf]


def test_level_slots_rejects_more_levels_than_slots() -> None:
    theme = Theme()
    with pytest.raises(ValueError, match="levels but the theme has"):
        theme.level_slots(len(theme.order) + 2)


def test_font_file_and_spec() -> None:
    theme = Theme()
    assert theme.font_file("sans").is_file()
    assert theme.font_spec("mono")["family"] == "Roboto Mono"


def test_measure_scales_with_size_weight_and_font() -> None:
    theme = Theme()
    base = theme.measure(s="Hello", size=20)
    assert base > 0
    assert theme.measure(s="Hello", size=40) == pytest.approx(2 * base)
    assert theme.measure(s="Hello", size=20, weight=700) > base
    mono = theme.measure(s="iiii", size=20, mono=True)
    assert mono == pytest.approx(theme.measure(s="WWWW", size=20, mono=True))
    assert theme.measure(s="", size=20) == 0


def test_measure_is_keyword_only() -> None:
    with pytest.raises(TypeError):
        Theme().measure("x", 20)  # type: ignore[misc]
