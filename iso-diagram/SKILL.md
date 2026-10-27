---
name: iso-diagram
description: Draw isometric diagrams - stacked or exploded layers, nested containers, hierarchies with callout cards, and flows between them - as SVG (PNG on request). Two styles - iso-tree (isometric hierarchy of slabs with color-keyed callout cards) and iso-stack (exploded stack of plates with pipes and leader-line labels). Use when asked for an isometric, layered, 3D-looking, exploded, stacked, or "layer cake" diagram, for iso-tree or iso-stack by name, or to show how things nest and how traffic or data moves through the layers. Also use to re-theme such a diagram, for example "apply my custom style" or "apply my custom theme".
---

*NOTE: paths are relative to this skill's directory.*

# Isometric diagrams

Two styles, built by scripts from a JSON spec. The scripts enforce most rules below, so a
routine diagram needs only this file and the style's reference.

| Style | Shape | Use when the story is |
| --- | --- | --- |
| `iso-tree` | Slabs in a top-down hierarchy; a callout card per level on the right | what each level holds, plus one path through it |
| `iso-stack` | Exploded plates, one per level; pipes run between them | how something moves through every layer |

## Read for the task

| Task | Read |
| --- | --- |
| Any new diagram | `references/spec.md`, plus `references/iso-tree.md` or `references/iso-stack.md` |
| A check failed, or a layout needs a rule the scripts lack | `references/layout.md` |
| An icon the diagram needs | `references/icons.md` |
| Changing colors, color encoding, or contrast | `references/color.md` |
| Fonts, text sizes, or embedding | `references/typography.md` |
| Grammar rules | `references/grammar.md` |
| A new theme, "apply my custom style" | `references/themes.md`, then `references/color.md` |

## Principles

These outrank everything else here. When a new rule or request conflicts with one, say so
before drawing, and propose a resolution.

1. **The diagram tells a story.** State the story in one sentence, expand it into three to
   five key points, and draw from those. Every element serves a point; cut anything that
   does not, however accurate. The story decides what is shown and emphasized, never where
   a kind of thing sits.
2. **The diagram is for people.** Useful and pleasant to read. When a rule makes a drawing
   harder to read, legibility wins; say which rule gave way.
3. **Things sit in consistent places.** The same kind of thing lands in the same place in
   every diagram: outermost container at the top of a stack or the root of a tree, leaf
   tier last.
4. **Containment is visible.** A child sits fully inside its parent, inset from its edges.
   It never touches or crosses the parent's border; the parent grows instead.
5. **Connections are drawn, with direction.** Orthogonal lines only, as few bends as
   possible, touching shapes only at their outlines. Direction comes from arrowheads,
   chevrons, or step numbers, never color alone.
6. **The diagram reads at a glance; details live nearby.** Shapes carry a short name.
   Callouts, leader labels, and the caption hold detail. Per-shape metadata goes in the
   SVG `<title>` and `<desc>`.
7. **Color follows one encoding, chosen for the story.** By level, kind, status, or owner:
   pick one, hold it across the diagram, and keep it across a set of diagrams telling the
   same kind of story. Emphasize by muting the rest, not by recoloring. Color is never the
   only cue, and it stays distinguishable for color-blind readers.
8. **Labels live on the surface they describe.** A label, badge, or marker lies flat on the
   face of the thing it names, never on another shape's side or another plate. Only things
   in open space (a source like the Internet) get floating labels.
9. **Depth is honest.** One isometric projection, one light direction. An upper layer
   hiding part of a lower one is fine; it adds depth.
10. **Text stays legible.** Text on a surface is at least 20px. Fonts are embedded. Literal
    identifiers (`alb-sg`, `10.0.0.0/16`) use the mono font.

## Workflow

1. **Story first.** Write the story and its key points. If the user gave none, propose
   them and confirm before drawing. Name the color encoding (default: by level).
2. **Write the spec** as JSON, following `references/spec.md`. Keep it next to the output so
   the diagram can be rebuilt.
3. **Build:**

   ```sh
   uv run --project SKILL_DIR iso-build SPEC.json -o OUT.svg
   ```

   `SKILL_DIR` is the absolute path of this skill's directory. The first run creates
   `SKILL_DIR/.venv` and installs the `iso_diagram` package into it. Add `--png` only when the user asks for PNG (it needs Chrome or Chromium). The script
   first checks that every id the spec references exists, then checks insets, label and
   card text fit, text sizes, connector routes, and the canvas, and writes nothing while
   any check fails. Fix the spec rather than passing `--allow-issues`; if a
   check cannot be met, say which and why.
4. **Look at it.** Render a PNG for your own review (to a scratch path if the user wants SVG
   only) and read it. Check each key point is visible, then check the layout rules by eye:
   the scripts do not catch everything.
5. **Hand over** the SVG path, the story it tells, and anything that gave way.

## Output

SVG by default, with fonts embedded as subset WOFF2 so it renders the same anywhere. PNG
only on request (`--png`, 2x by default). Save the spec alongside the output.

## Beyond the two styles

If a diagram fits neither style, compose it in a one-off script from `iso_diagram.iso`
(slabs, in-plane text, icons, connectors) and record shapes, labels, and connectors in an
`iso_diagram.checks.Registry` so the same rules are checked. Run it with
`uv run --project SKILL_DIR python SCRIPT.py` so the package imports resolve. Before building a third style into the
skill, ask.

## Files

- `src/iso_diagram/` is the package. `iso-build` (`build.py`) builds a spec;
  `iso-palette THEME -o OUT.svg` (`palette.py`) draws a theme's swatch sheet with a
  color-blindness check.
- `themes/default.json` is the default theme.
  asking.
- `examples/` holds the AWS specs and their output: `aws-tree.json`, `aws-stack.json`.
- `assets/` holds the fonts (OFL) and the manifest and licenses for the Feather (MIT) and
  Lucide (ISC) icon sets. Icons download on first use; see `references/icons.md`.
