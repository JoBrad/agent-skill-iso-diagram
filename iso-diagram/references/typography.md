# Typography

# Fonts

- **Roboto** for names, titles, card text, and captions.
- **Roboto Mono** for literal identifiers: resource names (`alb-sg`), addresses
  (`10.0.0.0/16`), regions (`us-east-1`), ports (`:8080`).

Both ship in `assets/fonts/` as variable fonts (OFL), so any weight renders true: 600 is a
real SemiBold, not a substituted Bold.


## Embedding

`src/iso_diagram/fonts.py` runs as part of every build. For each family and weight the SVG uses, it
instances the variable font at that weight, cuts it down to the characters drawn, and embeds
it as base64 WOFF2 in an `@font-face` rule. A diagram adds about 30 to 45 KB. The SVG then
renders the same on a machine without the fonts.

A theme that names other fonts must ship their files in `assets/fonts/` and point to them
in its `fonts` block. The build stops if text uses a family the theme does not provide.

## Sizes

| Use | Size | Weight |
| --- | --- | --- |
| Text on a surface | 20px minimum (theme `min_surface_text`) | 500 to 600 |
| Root slab label | up to 46px, scaled to the slab | 600 |
| Plate titles (iso-stack) | 40px | 500 |
| Card titles (iso-tree) | 32px | 600 |
| Card items, upright labels | 18 to 22px | 400 to 600 |
| Caption | 18px | 400 |

Text on a surface is sheared by the isometric transform, and sheared text below 20px
antialiases badly. Anything smaller than 20px goes upright in open space instead.

## Measuring

`Theme.measure()` reads advance widths from the font files, so label fitting and the label
checks use real widths, not estimates.
