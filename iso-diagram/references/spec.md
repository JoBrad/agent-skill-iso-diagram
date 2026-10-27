# Spec format

A spec is a JSON file. `examples/aws-tree.json` and `examples/aws-stack.json` are complete,
working specs; copy the closer one and edit it.

## Fields every spec has

| Field | Required | Meaning |
| --- | --- | --- |
| `style` | yes | `iso-tree` or `iso-stack` |
| `story` | yes | the one-sentence story; also the SVG `<desc>` and the default caption |
| `points` | yes | three to five key points; each must be visible in the drawing |
| `title` | no | the SVG `<title>` |
| `color_by` | no | the color encoding, for the record; the scripts implement `level` |
| `caption` | no | text under the diagram; defaults to the story plus a line legend |
| `theme` | no | theme name in `themes/` or a path; `--theme` overrides it |

## iso-tree

| Field | Meaning |
| --- | --- |
| `root` | the root node. A node has `id`, `label`, optional `sublabel`, `mono` (label is an identifier), `mono_sublabel`, `desc` (hover text), `slot` (color override), and `children` |
| `levels` | one entry per depth, in order: `{"name": ..., "card": {"title": ..., "items": [...]}}`. A level without `card` gets no callout |
| `source` | optional outside source drawn top-left: `{"id", "label", "icon"}` |
| `path` | optional ids, source first, along parent-child links. Those connectors are emphasized and the rest muted |
| `flows` | optional sideways steps after the path: `{"from", "to", "label"}`. `label` is usually a port, drawn in mono |
| `stack_leaves` | default `true`: two or more leaf children are drawn as overlapping tiles |

Steps are numbered in order: the path is step 1, then each flow.

## iso-stack

| Field | Meaning |
| --- | --- |
| `columns` | column ids, left to right. A column holds the same position on every plate, so nested things line up vertically |
| `layers` | plates, top (outermost) to bottom (leaf): `id`, `title`, `subtitle`, and any of `zones`, `markers`, `note`, `resources` |
| `zones` | areas on a plate: `{"column", "label", "mono", "style": "dashed", "fill": false, "size"}`. Zones on one plate share a size |
| `markers` | a small label beside a column's lane, such as `IGW`: `{"column", "label"}` |
| `note` | an identifier for the whole plate, such as a CIDR: `{"text", "mono"}`; drawn along the front edge |
| `resources` | small slabs with an icon: `{"column", "label", "icon", "count"}`; count up to 3 |
| `source` | `{"label", "icon", "column"}`: the feed into the top plate |
| `steps` | in order. `{"from": "source", "column", "to": LAYER}` drops from the source to a layer. `{"from": COL, "to": COL, "via": LAYER, "at": LAYER}` rises from `at` to `via`, crosses on `via`, and drops back to `at` |

Down traffic uses each column's A lane and up traffic its B lane, so a column can carry
both without overlap. Badge 1 sits by the source; later steps get a badge flat on their
`at` plate.
