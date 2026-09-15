from __future__ import annotations

import pytest

from g6_gui import app as app_module
from tests.g6_gui.fake_api import FakeG6Api


def test_parse_args_defaults():
    args = app_module.parse_args([])
    assert args.dry_run is False
    assert args.debug is False
    assert args.no_persist is False


def test_parse_args_flags():
    args = app_module.parse_args(["--dry-run", "--debug", "--no-persist"])
    assert args.dry_run is True
    assert args.debug is True
    assert args.no_persist is True


def test_visible_pages_skip_unavailable_modules(monkeypatch):
    monkeypatch.setattr("g6_gui.pages.mixer.AUDIO_INTERFACE_SUPPORTED", False)
    titles = [module.TITLE for module in app_module.visible_pages()]
    assert "Mixer" not in titles
    assert "Playback" in titles and "SBX" in titles


def test_visible_pages_include_mixer_on_linux(monkeypatch):
    monkeypatch.setattr("g6_gui.pages.mixer.AUDIO_INTERFACE_SUPPORTED", True)
    assert "Mixer" in [module.TITLE for module in app_module.visible_pages()]


def test_build_api_surfaces_missing_device_as_io_error(monkeypatch):
    def boom(**kwargs):
        raise IOError("No SoundBlaster X G6 device could be found")

    monkeypatch.setattr("g6_gui.app.G6Api", boom)
    args = app_module.parse_args([])
    with pytest.raises(IOError):
        app_module.build_api(args)


def test_build_api_passes_flags_through(monkeypatch):
    seen = {}

    def spy(**kwargs):
        seen.update(kwargs)
        return FakeG6Api()

    monkeypatch.setattr("g6_gui.app.G6Api", spy)
    app_module.build_api(app_module.parse_args(["--dry-run", "--debug", "--no-persist"]))
    assert seen == {"dry_run": True, "debug": True, "persist_model": False}


def test_build_pages_returns_a_tab_per_visible_page(monkeypatch):
    monkeypatch.setattr("g6_gui.pages.mixer.AUDIO_INTERFACE_SUPPORTED", False)
    from g6_gui.controller import G6Controller

    controller = G6Controller(FakeG6Api())
    tabs, gated = app_module.build_pages(controller)
    assert [title for title, _ in tabs] == ["Playback", "Recording", "SBX", "Lighting", "System"]
    assert gated == []  # nothing audio-gated is built on a non-Linux platform
    controller.shutdown()


def test_build_pages_collects_audio_gated_boxes_on_linux(monkeypatch):
    for page in ("mixer", "playback", "recording", "system"):
        monkeypatch.setattr(f"g6_gui.pages.{page}.AUDIO_INTERFACE_SUPPORTED", True)
    from g6_gui.controller import G6Controller

    controller = G6Controller(FakeG6Api())
    tabs, gated = app_module.build_pages(controller)
    assert [title for title, _ in tabs][0] == "Playback"
    assert len(gated) == 3  # mixer page + playback audio_section + recording audio_section
    controller.shutdown()
