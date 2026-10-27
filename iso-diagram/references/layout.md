# Layout rules

The rules behind principles 3 to 9, with the numbers the scripts use. `src/iso_diagram/checks.py`
enforces the ones marked **checked**; review the rest by eye.

## Containment

- **checked** A child zone or resource sits at least 16 plane units inside its parent's
  edge. If it does not fit, grow the parent; never shrink a child below its label.
- Siblings on one surface share a size, so they read as peers.

## Labels and markers

- **checked** A label on a surface fits inside that surface with 4 units to spare. Labels
  shrink to fit, never below the 20px floor (**checked**).
- A label, badge, or marker lies flat on the surface of what it describes. A step badge for
  something on the Resources plate lies on that plate, not on the side of the plate above.
- Text runs up and to the right on a top face (rotate -90 in plane coordinates).

## Connectors

- **checked** Orthogonal segments only, at most one bend. A route that needs two is allowed
  only when no one-bend route is clear; the check reports it so you can say why.
- **checked** A connector touches a shape only at its outline: it leaves at the parent's
  edge and ends with the arrow tip on the child's edge. It never crosses into any shape.
- Exit and entry points are whichever outline points allow the fewest bends: bottom edge,
  top edge, or a side corner. Stay 30 units in from a shape's far corners.
- Parallel connectors keep 12 units apart. Leader lines keep 22 apart from connectors.
- Leader lines to callouts are exempt from the outline rule; their dot sits on the face.
- Pipes in iso-stack pass between plates by design and are exempt.

## Emphasis

- One connector set. A story path is emphasized (full stroke, arrowheads, numbered steps)
  and everything else muted (1.5 stroke at the theme's `muted_opacity`, about 55%). Never
  draw a second line beside a connector to show the same path.
- Emphasized segments take the color of the level they leave.

## Depth

- **checked** In iso-stack, nothing the story needs (ports, hops, badges, labels, resources)
  sits under the plate above. The script widens plate spacing until that holds.
- One projection: 30 degree isometric. Shadows fall straight down, soft.
- Draw back to front. Occlusion of lower layers is fine.

## Canvas

- **checked** Nothing extends past the canvas. Keep a 40-unit margin and room above the top
  shape for a source.
