# AGENTS.md

This file serves as instructions for agents.

Process the `README.md` file in the root of this repo. It contains an overview of what this project is for.

## Project organization

```txt
.
├── iso-diagram/
|    This directory contains the skill.
├── .gitignore
|   Super tailored to this project. It should stay that way.
├── AGENTS.md
|   This file! It is primarily for agents, not humans.
├── CLAUDE.md
|   Just includes a reference to this file.
├── devbox.json
|   Development environment for working on this repo. Not part of the skill.
├── LICENSE
|   License detail for this project.
├── pyproject.toml
|   Development dependencies and tooling. Not part of the skill.
├── README.md
|   An overview file primarily for humans. Agents should also read it.
├── scripts/
|   Repo scripts, run with `uv run scripts/NAME.py`. Not part of the skill.
└── tests/
    Tests for the skill's package and the repo scripts. Not part of the skill.
```

# Installing the skill

There are instructions on using the `gh` CLI to install the skill in the README.md file. An advanced user may also wish to simply use a symlink to install the skill, targeting a locally-cloned copy of the repository.

# Requirements

This skill requires 2 applications:

1. `uv`: Used to install dependencies for several python scripts, and to invoke them.
2. `chrome` or `chromium`: Required for png exports.

You should prompt the user to install these requirements if they are missing. You should not attempt to install any applications unless explicitly directed to do so by the user.

## Check for `uv`

Run the following command to check if `uv` is installed:

```bash
uv --version
```

If `uv` is not installed, you have 2 options:

1. (Preferred): When working from this repo, use `devbox`. Prompt the user to install `devbox` if it is not installed. Then run `devbox run install` to setup the virtual environment. Devbox is for development only; the skill itself never uses it.
2. Prompt the user to install `uv` from its official source: `https://docs.astral.sh/uv/getting-started/installation/`

## Check for `chrome` or `chromium`

Run `uv run --project iso-diagram python -c "from iso_diagram.render import browser; print(browser())"` to see if this tool is accessible.

# Skill checks

When the skill is updated, you should perform several checks:

- Except for noted requirements, the skill should be self-contained, and not require any other skills or tools.
- Nothing in the skill should reference resources (e.g. color palettes, etc.) that are not part of the skill, or would violate either the license of the utilized resource or the licensing of this skill.
- Scan the skill detail to ensure secrets, keys, etc. are not included. Nothing in the skill should require access to privileged info. If present, you may use a tool such as `gitleaks` to scan the code.
