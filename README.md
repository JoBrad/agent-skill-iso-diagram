# iso-diagram skill

## Overview

This skill creates isometric diagrams in 2 opinionated styles with text callouts and simplified detail. I got the idea from diagrams like the one in [this Scalr doc](https://docs.scalr.io/docs/structuring-scalr), and wanted to be able to use that diagram type elsewhere.

### `iso-tree`

An isometric hierarchy diagram which displays a multi-layered set of entities which may have multiple children as the diagram moves downwards.


![Example iso-tree diagram of an AWS network, illustrating relationships and connectivity between an AWS region, VPC, subnets, and security groups, with a color-matched callout card for each level.](./iso-diagram/examples/aws-tree.png)

### `iso-stack`

Also called an "exploded" or "exploded isometric view", this type of diagram displays several layers as self-contained "slabs" whose child items may be connected by a through-connector.

![Example iso-stack diagram of a request traveling through an AWS Region, VPC, subnets, security groups, and finally individual resources. Color-matched text callouts provide a brief description of each major resource type.](./iso-diagram/examples/aws-stack.png)

The default output is `svg`, but it also supports `png`. The assumption is that the user or agent invoking the skill can utilize a separate tool to convert the `svg` output into other image formats.

## Style

This skill has a default set of fonts, icons, color palettes, and design principles which guide the creation of each diagram. You may provide customization options as part of the skill invocation to change these.

## Installation

Nothing in the skill is agent-specific, so it should work with your agent of choice.

### Requirements

- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) installs the skill's Python dependencies and runs its scripts. It also runs the installer.
- Chrome or Chromium, for PNG export only. SVG output works without it.
- Network access on first use. `uv` downloads the Python dependencies, and the skill downloads each icon the first time a diagram uses it.

### Install with the script

From a clone of this repo:

```sh
# Copy the skill to ~/.claude/skills/iso-diagram (Claude Code's user skills folder)
uv run scripts/install.py

# Copy it to another agent's skills folder
uv run scripts/install.py ~/path/to/skills

# Symlink it instead, so the installed skill always matches the checked-out branch
uv run scripts/install.py --link
```

The script installs to `iso-diagram` inside the skills folder, creating the folder if needed. It then builds the skill's Python environment and reports whether it found Chrome or Chromium. `--no-check` skips that step; the skill builds its environment on first use instead. Start a new agent session afterward so the agent loads the skill.

To update a copy, pull this repo and rerun the script. The update replaces the skill's files and keeps custom themes and downloaded icons from the earlier copy. A link needs no update.

The script will not replace a copy with a link, or a link with a copy. Remove the old install first, after moving any custom themes out of its `themes/` folder.

On Windows, `--link` needs Developer Mode turned on. A copy works without it.

### Install by hand

Copy the `iso-diagram` folder into your agent's skills folder. Keep the folder name `iso-diagram`, since it matches the skill's name. Leave out any `.venv` and `__pycache__` folders.

The installed folder must be writable. The skill writes its Python environment to `.venv`, downloaded icons to `assets/icons/`, and saved custom themes to `themes/`. Copying over an existing install by hand can delete saved themes, so move them out first.

## License

License detail is in [LICENSE](./LICENSE). Note that this skill includes bundled fonts, and downloads Feather and Lucide icons on first use. Both have their own licenses which should be respected.

In short: Feel free to copy it, but keep it open, and please contribute your changes here. :)
