"""Embed subset WOFF2 fonts in an SVG: one @font-face per family and weight it uses."""

import base64
import io
import re
import xml.etree.ElementTree as ET

from collections.abc import Iterable

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

from iso_diagram.theme import Theme


NS = "{http://www.w3.org/2000/svg}"


def family_of(attr: str) -> str:
    """Return the first family in a CSS font-family list, unquoted."""
    return attr.split(",")[0].strip().strip("'\"")


def used_faces(svg_text: str) -> dict[tuple[str, int], set[str]]:
    """Map (family, weight) to the characters drawn in that face."""
    used = {}
    for el in ET.fromstring(svg_text).iter(f"{NS}text"):
        fam = family_of(el.get("font-family", ""))
        weight = int(el.get("font-weight", 400))
        used.setdefault((fam, weight), set()).update("".join(el.itertext()))
    return used


def woff2(theme: Theme, kind: str, weight: int, chars: Iterable[str]) -> str:
    """Return the theme's kind font at weight, subset to chars, as base64 WOFF2."""
    spec = theme.font_spec(kind)
    font = TTFont(theme.font_file(kind))
    if "fvar" in font:
        axes = {a.axisTag for a in font["fvar"].axes}
        loc = {"wght": weight} if "wght" in axes else {}
        loc.update({k: v for k, v in spec.get("fixed_axes", {}).items() if k in axes})
        font = instantiateVariableFont(font, loc)
    opts = Options()
    opts.flavor = "woff2"
    opts.layout_features = ["kern", "liga"]
    sub = Subsetter(opts)
    sub.populate(text="".join(sorted(chars)))
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


def embed(svg_text: str, theme: Theme) -> str:
    """Return svg_text with an embedded @font-face for each family and weight it uses."""
    kinds = {theme.font_spec(k)["family"]: k for k in ("sans", "mono")}
    faces = []
    for (fam, weight), chars in sorted(used_faces(svg_text).items()):
        if fam not in kinds:
            raise ValueError(
                f"text uses font '{fam}', which the theme does not provide"
            )
        data = woff2(theme, kinds[fam], weight, chars)
        faces.append(
            f"@font-face{{font-family:'{fam}';font-weight:{weight};"
            f"src:url(data:font/woff2;base64,{data}) format('woff2');}}"
        )
    svg_text = re.sub(r"<style>.*?</style>", "", svg_text, flags=re.S)
    return svg_text.replace("<defs>", "<defs><style>" + "".join(faces) + "</style>", 1)
