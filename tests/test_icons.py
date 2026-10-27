"""On-demand icon fetching in iso_diagram.icons."""

import io
import sys
import urllib.error
import urllib.request

from pathlib import Path

import pytest

from tests.conftest import UNCACHED, fake_svg

from iso_diagram import icons


class FakeResponse(io.BytesIO):
    """A urlopen() result: bytes plus context-manager support."""

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def serve(monkeypatch: pytest.MonkeyPatch, body: bytes) -> list[str]:
    """Make urlopen return body, and return the list of URLs requested."""
    urls: list[str] = []

    def fake_urlopen(url: str, **kwargs: object) -> FakeResponse:
        urls.append(url)
        return FakeResponse(body)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return urls


def test_find_matches_substrings_in_lookup_order() -> None:
    assert icons.find(word="ROUTE") == [("lucide", "router")]
    assert icons.find(word="shield") == [("feather", "shield"), ("lucide", "shield")]
    assert icons.find(word="zzz") == []


def test_source_prefers_the_first_set(icon_cache: Path) -> None:
    assert icons.source(name="shield") == icon_cache / "feather" / "shield.svg"


def test_source_unknown_name_is_none() -> None:
    assert icons.source(name="no-such-icon") is None


def test_source_downloads_and_caches_a_missing_icon(
    icon_cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_name, name = UNCACHED
    urls = serve(monkeypatch, fake_svg(name))
    path = icons.source(name=name)
    assert path is not None
    assert path == icon_cache / set_name / f"{name}.svg"
    assert path.read_bytes() == fake_svg(name)
    assert urls == [f"{icons.CDN}/lucide-pkg@1.0.0/icons/{name}.svg"]
    assert icons.source(name=name) == path
    assert len(urls) == 1


def test_download_refuses_a_hash_mismatch(
    icon_cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_name, name = UNCACHED
    serve(monkeypatch, b"<svg>tampered</svg>")
    with pytest.raises(ValueError, match="does not match the manifest hash"):
        icons.source(name=name)
    assert not (icon_cache / set_name / f"{name}.svg").exists()
    assert not (icon_cache / set_name / f"{name}.part").exists()


def test_download_reports_network_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(url: str, **kwargs: object) -> None:
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", fail)
    with pytest.raises(OSError, match=f"icon '{UNCACHED[1]}': download from .* failed"):
        icons.source(name=UNCACHED[1])


def test_main_find_prints_matches(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["iso-icons", "find", "data"])
    icons.main()
    assert capsys.readouterr().out == "database\tfeather\n"


def test_main_find_exits_when_nothing_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["iso-icons", "find", "zzz"])
    with pytest.raises(SystemExit, match="no icon name contains 'zzz'"):
        icons.main()
