# Icons

## Lookup order

1. **Feather** (4.29.2, 287 icons, MIT).
2. **Lucide** (0.460.0, about 1,500 icons, ISC). A Feather fork with the same design rules,
   and more technical icons: `network`, `router`, `container`, `cloud-cog`.
3. **Draw it** in Feather style (below).

Find a name with `uv run --project SKILL_DIR iso-icons find WORD`. It searches
`assets/icons/manifest.json`, so it works offline. The skill ships no icon files: the first
build that uses an icon downloads it from jsDelivr, checks its SHA-256 against the
manifest, and saves it under `assets/icons/<set>/`. That first use needs network access.
Pick by meaning, not by look. A good fit used consistently beats a perfect fit in one place.

Common picks for infrastructure: `server` (instance), `database` (database), `globe`
(Internet), `network` (load balancer), `shield` (firewall, policy), `lock` (encryption),
`key` (secret), `hard-drive` (volume), `layers` (stack), `cloud` (provider), `cpu`
(compute), `box` (package), `git-branch` (pipeline).

## Drawing a new icon in Feather style

- A 24 x 24 grid with about 2 units of padding.
- Stroke only, no fills. 2-unit stroke at 24px, round caps and round joins.
- Built from simple geometry: lines, circles, rounded rectangles, short arcs.
- As little detail as still reads at 24px. If it needs a legend, it is too detailed.
- Save it as an SVG in the same shape as the bundled ones (`viewBox="0 0 24 24"`,
  `fill="none"`, `stroke="currentColor"`), under the output folder, not in `assets/`.
  Ask before adding it to the skill.

## Placement

- `iso.icon(name, color, size, stroke)` draws an icon centered on the origin. Inside a
  `plane_matrix(...) rotate(-90)` group it lies flat on a surface, upright to the reader.
- On a surface: 40 to 52 units, stroke 1.6 to 1.8, in the surface's text shade.
- Upright in open space (a source): about 52px in the flow color.
