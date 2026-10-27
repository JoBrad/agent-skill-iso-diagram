# iso-stack

An exploded stack: one plate per level, outermost on top, leaf at the bottom, with thick
pipes carrying traffic between plates and leader-line titles on the right. Modeled on
platform-layer diagrams such as "Schedules > Webhooks > UIs > Flows > Scripts > Workers".

## When it fits

- The story is movement through every layer: a request, a deployment, a data flow.
- Things nest, so a column can hold the same position on every plate.
- Two to four columns and four to six plates. More columns crowd each plate; more plates
  make the image taller than it is useful.

## Layout the script does

- **Columns** sit on a diagonal across each plate, 130 apart, so each plate shows them as a
  row from left to right. The plate grows to keep every zone 18 units in from its edge.
- **Plates** are at least 260 apart, and the script spreads them further until no port, hop,
  badge, label, or resource is under the plate above. The back of each plate may still be
  hidden; that occlusion is intended.
- **Zones** on one plate share one size. Their labels run along the zone's front-right edge.
- **Lanes:** each column has an A lane (down) and a B lane (up), 16 units either side of its
  center, so a column can carry traffic both ways. Pipes are drawn between plates with a
  chevron for direction and a port on each plate they pass.
- **Hops** between columns rise to the `via` plate, cross it as a flat pipe, and drop. Use
  the plate that routes between columns (for AWS, the VPC).
- **Resources** are small slabs with an icon on top and a flat label in front. A count of 2
  or 3 fans the slabs forward.
- **Titles** sit on the right, joined to each plate by an elbow leader in the plate's color.

## Writing a good one

- Name plates for the level, not the instance (`Subnets`, not `subnet-0a1b`); put instance
  names on zones and notes.
- Keep step count to three or four. More pipes than that read as plumbing, not a story.
- Put identifiers in `note` or mono zone labels, not in titles.
