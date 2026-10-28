# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Install the iso-diagram skill into an agent's skills directory.

    uv run scripts/install.py [SKILLS_DIR] [--link] [--no-check]

The skill lands in SKILLS_DIR/iso-diagram. SKILLS_DIR defaults to ~/.claude/skills.

A copy is the default. Rerunning it replaces the skill's files and keeps what the skill
saved into its own folder since the last install: custom themes and downloaded icons.
--link symlinks the repo's iso-diagram folder instead, so the installed skill always
matches the checked-out branch.

After installing, the script builds the skill's .venv and looks for Chrome or Chromium,
which PNG export needs. Both need uv, and the first build needs network access.
--no-check skips both; the skill then builds its .venv on first use.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

from pathlib import Path


SKILL_NAME = "iso-diagram"
SOURCE = Path(__file__).resolve().parents[1] / SKILL_NAME
DEFAULT_SKILLS_DIR = Path("~/.claude/skills")

# Never copied: build output and OS clutter. The .venv is rebuilt, not carried over.
IGNORE = shutil.ignore_patterns(".venv", "__pycache__", "*.pyc", ".DS_Store", "*.part")

# What the skill saves into its own folder at runtime. An update keeps these unless the
# new copy has a file at the same path.
SAVED_FILES = ["themes/*.json", "assets/icons/*/*.svg"]


def conflict(*, dest: Path, source: Path, link: bool) -> str | None:
    """Return why dest cannot take this kind of install, or None if it can."""
    if dest.is_symlink():
        if link:
            return None
        return f"{dest} is a symlink. Remove it, then rerun to install a copy."
    if not dest.exists():
        return None
    if dest.resolve() == source:
        return f"{dest} is the skill's source folder."
    if not (dest / "SKILL.md").is_file():
        return f"{dest} exists and is not an {SKILL_NAME} install. Remove or rename it."
    if link:
        return (
            f"{dest} is a copy. Move any custom themes out of its themes/ folder,"
            " remove it, then rerun to install a link."
        )
    return None


def carry_over(*, old: Path, new: Path) -> list[Path]:
    """Copy saved files from old into new where new lacks them. Return what was kept."""
    kept = []
    for pattern in SAVED_FILES:
        for path in sorted(old.glob(pattern)):
            target = new / path.relative_to(old)
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                kept.append(path.relative_to(old))
    return kept


def install_copy(*, dest: Path, source: Path) -> list[Path]:
    """Copy source to dest, replacing an earlier copy. Return the saved files kept."""
    temp = Path(tempfile.mkdtemp(prefix=f".{SKILL_NAME}-", dir=dest.parent))
    staged, retired = temp / "new", temp / "old"
    kept = []
    try:
        shutil.copytree(source, staged, ignore=IGNORE)
        if dest.exists():
            kept = carry_over(old=dest, new=staged)
            dest.rename(retired)
        staged.rename(dest)
    except BaseException:
        if retired.exists() and not dest.exists():
            retired.rename(dest)
        raise
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    return kept


def install_link(*, dest: Path, source: Path) -> None:
    """Point dest at source with a symlink, replacing an earlier symlink."""
    if dest.is_symlink():
        dest.unlink()
    try:
        dest.symlink_to(source, target_is_directory=True)
    except OSError as e:
        raise SystemExit(
            f"Could not create the symlink: {e}\n"
            "On Windows, turn on Developer Mode, or install a copy instead."
        ) from e


def check(*, dest: Path) -> int:
    """Build the skill's .venv and look for a browser. Return an exit code."""
    uv = shutil.which("uv")
    if uv is None:
        print(
            "uv was not found. The skill needs it:"
            " https://docs.astral.sh/uv/getting-started/installation/"
        )
        return 1
    # uv warns when an outer environment (such as this script's) is active.
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    sync = subprocess.run(
        [uv, "sync", "--quiet", "--project", str(dest)], env=env, check=False
    )
    if sync.returncode != 0:
        print("Could not build the skill's .venv. The skill retries on first use.")
        return 1
    probe = "from iso_diagram.render import browser; print(browser())"
    found = subprocess.run(
        [uv, "run", "--quiet", "--project", str(dest), "python", "-c", probe],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if found.returncode == 0:
        print(f"PNG export will use {found.stdout.strip()}")
    else:
        print("Chrome or Chromium was not found. SVG works; PNG export will not.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the installer."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "skills_dir",
        nargs="?",
        type=Path,
        default=DEFAULT_SKILLS_DIR,
        help="the agent's skills directory (default: %(default)s)",
    )
    parser.add_argument(
        "--link",
        action="store_true",
        help="symlink the repo's folder instead of copying",
    )
    parser.add_argument(
        "--no-check",
        action="store_true",
        help="skip building the .venv and the browser check",
    )
    args = parser.parse_args(argv)

    skills_dir = args.skills_dir.expanduser().absolute()
    dest = skills_dir / SKILL_NAME
    if reason := conflict(dest=dest, source=SOURCE, link=args.link):
        raise SystemExit(reason)
    skills_dir.mkdir(parents=True, exist_ok=True)

    if args.link:
        install_link(dest=dest, source=SOURCE)
        print(f"Linked {dest} -> {SOURCE}")
    else:
        kept = install_copy(dest=dest, source=SOURCE)
        print(f"Copied {SKILL_NAME} to {dest}")
        if kept:
            print(f"Kept {len(kept)} saved files from the earlier copy.")

    code = 0 if args.no_check else check(dest=dest)
    print("Start a new agent session to load the skill.")
    return code


if __name__ == "__main__":
    sys.exit(main())
