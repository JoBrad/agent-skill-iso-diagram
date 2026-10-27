# iso-tree

An isometric hierarchy: the root slab at the top, each level of children below it, and one
color-keyed callout card per level on the right. Modeled on hierarchy diagrams such as
"Control Tower > Account > Environment > Workspace".

## When it fits

- The story is about what each level holds, and the cards carry that detail.
- Three to five levels, and no more than about four nodes on the widest level. Past that
  the slabs shrink and labels fall to the 20px floor; split the diagram instead.
- At most one path to emphasize, plus a few sideways flows.

## Layout the script does

- **Sizes by depth:** 260 for the first two levels, 150 for the third, 110 and 90 below.
  Two or more leaf children of one parent are drawn as overlapping tiles (70 x 130), the
  way the reference image draws workspaces.
- **Overlap:** a level with one same-size child per node overlaps it, the parent drawn on
  top (Region over VPC). Other levels sit 100 below the level above.
- **Labels** lie flat on each top face, running up and to the right, shifted toward the
  front edge when there is a sublabel. A label too long for its slab shrinks to fit, never
  below 20px.
- **Connectors:** parent to child, straight down when the two line up, else out of the
  parent's side corner and down: one bend at most. They stay 30 units in from a shape's
  far corners so they never graze a silhouette. Emphasized path connectors take the color
  of the level they leave, full stroke with arrowheads; the rest are muted.
- **Source:** drops from the top-left, then one bend into the first path node's left side.
  That keeps the top of the diagram clear.
- **Flows** run straight across, level with the target's side corner, when that line is
  clear; otherwise under and up.
- **Cards:** leader from the rightmost node of each level, horizontal to the card. A leader
  that would run beside a connector moves up the slab's face.

## Writing a good one

- Put the story's subject in the path. If every node is equally important, drop the path
  and let the cards carry the story.
- Keep card items short: two columns of three rows reads well; more than eight items says
  the level needs its own diagram.
- Flow labels are usually ports or protocols, in mono.
