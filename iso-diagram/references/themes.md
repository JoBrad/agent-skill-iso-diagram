# Themes

A theme is a JSON file in `themes/`. Layout code never names a color or font; it asks the
theme for slots, so a new theme changes the look without touching layout.

## Format

See `themes/default.json`. Keys:

| Key | Meaning |
| --- | --- |
| `slots` | named colors, each `{"stroke", "text"}`. Text shades need 4.5:1 on the background |
| `order` | slots for levels, top first |
| `leaf` | slot for the deepest level |
| `flow` | slot for traffic: pipes, ports, the source |
| `light_slots` | slots whose stroke is under 3:1; their outlines use the text shade |
| `tints` | `top` and `side`: how far toward white the faces mix |
| `muted_opacity` | opacity for de-emphasized connectors |
| `ink` | title, body, label, and caption text colors |
| `background` | canvas color |
| `fonts` | `sans` and `mono`: `family`, `file` (under the skill folder), `fixed_axes`, `fallback` |
| `min_surface_text` | text size floor on surfaces |

## Custom themes

### Creating a custom theme

Query the user for required information for the theme, using `default.json` as a guide for inputs.

1. Copy `default.json` to `themes/NAME.json` (where `NAME` is the theme name) and replace values. Keep slot names
   descriptive of the hue.
2. Run `uv run --project SKILL_DIR iso-palette NAME -o OUT.svg --png` and read both the sheet and the
   printed color-blindness report. Every closest pair should be 15 or more.
3. Show the user the sheet before using the theme in a diagram.

### Applying ad-hoc custom themes

The user may request that you use their own colors, fonts, icons, or other theme-related resources. You should accommodate these requests where possible.

Check whether the custom detail provided by the user is sufficient to complete the task. For example, if the user's color palette does not provide enough colors for your use, prompt them for additional colors, or suggest additional colors that align with the design principles for this skill (e.g. accessibility and clarity).

When the custom theme conflicts with the design principles of this skill, this skill's design should be priority unless directed otherwise by the user.

If an ad-hoc theme is routinely used, ask the user if they'd like to save the theme, and use the `Creating a custom theme` instructions to do this, with their input.
