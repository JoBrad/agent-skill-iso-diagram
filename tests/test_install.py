import subprocess

from pathlib import Path

import pytest

from scripts import install


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """A small stand-in for the skill folder, with the clutter the copy must skip."""
    root = tmp_path / "repo" / "iso-diagram"
    for rel, text in {
        "SKILL.md": "skill",
        "themes/default.json": "{}",
        "src/iso_diagram/__init__.py": "",
        "src/iso_diagram/__pycache__/x.pyc": "",
        ".venv/pyvenv.cfg": "",
        "assets/icons/feather/box.svg": "<svg/>",
        "assets/icons/feather/box.svg.part": "",
    }.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


@pytest.fixture
def skills(tmp_path: Path) -> Path:
    path = tmp_path / "skills"
    path.mkdir()
    return path


def test_copy_skips_build_output(source, skills):
    dest = skills / "iso-diagram"
    install.install_copy(dest=dest, source=source)
    assert (dest / "SKILL.md").read_text() == "skill"
    assert (dest / "assets/icons/feather/box.svg").exists()
    assert not (dest / ".venv").exists()
    assert not (dest / "src/iso_diagram/__pycache__").exists()
    assert not (dest / "assets/icons/feather/box.svg.part").exists()
    assert [p.name for p in skills.iterdir()] == ["iso-diagram"]


def test_copy_update_keeps_saved_files_and_drops_removed_ones(source, skills):
    dest = skills / "iso-diagram"
    install.install_copy(dest=dest, source=source)
    (dest / "themes/mine.json").write_text("{}")
    (dest / "themes/default.json").write_text("stale")
    (dest / "assets/icons/lucide").mkdir()
    (dest / "assets/icons/lucide/router.svg").write_text("<svg/>")
    (dest / "notes.txt").write_text("")
    (source / "themes/default.json").write_text("new")

    kept = install.install_copy(dest=dest, source=source)

    assert kept == [Path("themes/mine.json"), Path("assets/icons/lucide/router.svg")]
    assert (dest / "themes/default.json").read_text() == "new"
    assert (dest / "themes/mine.json").exists()
    assert (dest / "assets/icons/lucide/router.svg").exists()
    assert not (dest / "notes.txt").exists()


def test_copy_failure_restores_earlier_copy(source, skills, monkeypatch):
    dest = skills / "iso-diagram"
    install.install_copy(dest=dest, source=source)
    real_rename = Path.rename

    def fail_on_new(self, target):
        if self.name == "new":
            raise OSError("boom")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_on_new)
    with pytest.raises(OSError, match="boom"):
        install.install_copy(dest=dest, source=source)
    assert (dest / "SKILL.md").exists()
    assert [p.name for p in skills.iterdir()] == ["iso-diagram"]


def test_link_creates_and_replaces_symlink(source, skills, tmp_path):
    dest = skills / "iso-diagram"
    dest.symlink_to(tmp_path)
    install.install_link(dest=dest, source=source)
    assert dest.is_symlink()
    assert dest.resolve() == source.resolve()


def test_link_failure_explains(source, skills, monkeypatch):
    def refuse(*_args, **_kwargs):
        raise OSError("not permitted")

    monkeypatch.setattr(Path, "symlink_to", refuse)
    with pytest.raises(SystemExit, match="Developer Mode"):
        install.install_link(dest=skills / "iso-diagram", source=source)


@pytest.mark.parametrize(
    ("setup", "link", "expected"),
    [
        ("none", False, None),
        ("none", True, None),
        ("symlink", True, None),
        ("symlink", False, "is a symlink"),
        ("copy", False, None),
        ("copy", True, "is a copy"),
        ("other", False, "is not an iso-diagram install"),
    ],
)
def test_conflict(source, skills, setup, link, expected):
    dest = skills / "iso-diagram"
    if setup == "symlink":
        dest.symlink_to(source)
    elif setup == "copy":
        install.install_copy(dest=dest, source=source)
    elif setup == "other":
        dest.mkdir()
    reason = install.conflict(dest=dest, source=source, link=link)
    if expected is None:
        assert reason is None
    else:
        assert expected in reason


def test_conflict_refuses_source_folder(source):
    reason = install.conflict(dest=source, source=source.resolve(), link=False)
    assert reason is not None
    assert "source folder" in reason


def fake_run(*, returncodes: list[int], calls: list[list[str]]):
    def run(cmd, **kwargs):
        calls.append(cmd)
        assert "VIRTUAL_ENV" not in kwargs["env"]
        return subprocess.CompletedProcess(
            cmd, returncodes.pop(0), stdout="/bin/chrome\n"
        )

    return run


@pytest.mark.parametrize(
    ("returncodes", "code", "message"),
    [
        ([0, 0], 0, "PNG export will use /bin/chrome"),
        ([0, 1], 0, "PNG export will not"),
        ([1], 1, "Could not build"),
    ],
)
def test_check(monkeypatch, capsys, tmp_path, returncodes, code, message):
    calls = []
    monkeypatch.setenv("VIRTUAL_ENV", "/elsewhere")
    monkeypatch.setattr(install.shutil, "which", lambda _name: "/bin/uv")
    monkeypatch.setattr(
        install.subprocess, "run", fake_run(returncodes=returncodes, calls=calls)
    )
    assert install.check(dest=tmp_path) == code
    assert message in capsys.readouterr().out
    assert calls[0][:2] == ["/bin/uv", "sync"]


def test_check_without_uv(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(install.shutil, "which", lambda _name: None)
    assert install.check(dest=tmp_path) == 1
    assert "uv was not found" in capsys.readouterr().out


def test_main_copies_then_updates(source, skills, monkeypatch, capsys):
    monkeypatch.setattr(install, "SOURCE", source)
    assert install.main([str(skills), "--no-check"]) == 0
    (skills / "iso-diagram/themes/mine.json").write_text("{}")
    assert install.main([str(skills), "--no-check"]) == 0
    out = capsys.readouterr().out
    assert "Kept 1 saved files" in out
    assert "new agent session" in out


def test_main_links_and_creates_skills_dir(source, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(install, "SOURCE", source)
    monkeypatch.setattr(install, "check", lambda *, dest: 0)
    skills = tmp_path / "new" / "skills"
    assert install.main([str(skills), "--link"]) == 0
    assert (skills / "iso-diagram").is_symlink()
    assert "Linked" in capsys.readouterr().out


def test_main_stops_on_conflict(source, skills, monkeypatch):
    monkeypatch.setattr(install, "SOURCE", source)
    (skills / "iso-diagram").mkdir()
    with pytest.raises(SystemExit, match="not an iso-diagram install"):
        install.main([str(skills), "--no-check"])


@pytest.mark.parametrize(
    "func",
    [
        install.conflict,
        install.carry_over,
        install.install_copy,
        install.install_link,
        install.check,
    ],
)
def test_public_functions_are_keyword_only(func):
    with pytest.raises(TypeError):
        func(Path())
