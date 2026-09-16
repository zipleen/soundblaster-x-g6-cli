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
    assert [title for title, _ in tabs] == [
        "macOS Audio", "Playback", "Recording", "SBX", "Lighting", "System",
    ]
    assert gated == []  # nothing audio-gated is built on a non-Linux platform
    controller.shutdown()


def test_build_pages_collects_audio_gated_boxes_on_linux(monkeypatch):
    for page in ("mixer", "playback", "recording", "system"):
        monkeypatch.setattr(f"g6_gui.pages.{page}.AUDIO_INTERFACE_SUPPORTED", True)
    from g6_gui.controller import G6Controller

    controller = G6Controller(FakeG6Api())
    tabs, gated = app_module.build_pages(controller)
    assert [title for title, _ in tabs][0] == "macOS Audio"
    assert len(gated) == 3  # mixer page + playback audio_section + recording audio_section
    controller.shutdown()


def test_recording_and_sbx_are_disabled_when_stereo_direct_is_active(monkeypatch):
    """Reproduces the request directly: those tabs must be disabled whenever
    macOS's Clock Source is Stereo Direct, since the G6's DSP -- which is what
    Recording and SBX both drive -- is bypassed entirely in that mode."""
    from g6_gui import coreaudio as ca
    from g6_gui.controller import G6Controller
    from g6_gui.pages import macos_audio
    from tests.g6_gui.fake_coreaudio import FakeHal

    hal = FakeHal(current_clock_source_code=1)  # 1 = Stereo Direct, see FakeHal defaults
    monkeypatch.setattr(macos_audio, "_make_clock_controller", lambda: ca.ClockController(hal=hal))

    controller = G6Controller(FakeG6Api())
    tabs, _ = app_module.build_pages(controller)
    by_title = dict(tabs)

    # set_enabled recurses into a box's children/content but never sets
    # .enabled on the box passed in itself -- same convention every other
    # gate in this app follows (claim-gating, audio-interface gating), so
    # check a representative leaf control, exactly as those pages' own tests
    # do (see recording_test.py / sbx_test.py).
    assert by_title["Recording"].mic_boost.slider.enabled is False
    assert by_title["SBX"].surround.toggle.switch.enabled is False
    # Everything else stays untouched by this particular gate.
    assert by_title["Playback"].output.selection.enabled is True
    controller.shutdown()


def test_recording_and_sbx_stay_enabled_when_dsp_clock_is_active(monkeypatch):
    from g6_gui import coreaudio as ca
    from g6_gui.controller import G6Controller
    from g6_gui.pages import macos_audio
    from tests.g6_gui.fake_coreaudio import FakeHal

    hal = FakeHal(current_clock_source_code=0)  # 0 = DSP Clock
    monkeypatch.setattr(macos_audio, "_make_clock_controller", lambda: ca.ClockController(hal=hal))

    controller = G6Controller(FakeG6Api())
    tabs, _ = app_module.build_pages(controller)
    by_title = dict(tabs)

    assert by_title["Recording"].mic_boost.slider.enabled is True
    assert by_title["SBX"].surround.toggle.switch.enabled is True
    controller.shutdown()


def test_recording_and_sbx_stay_enabled_when_the_clock_source_is_unrecognised(monkeypatch):
    """Conservative by design: an ambiguous read must not speculatively
    disable tabs that might still work fine. See _apply_clock_source_gate."""
    from g6_gui import coreaudio as ca
    from g6_gui.controller import G6Controller
    from g6_gui.pages import macos_audio
    from tests.g6_gui.fake_coreaudio import FakeHal

    hal = FakeHal(clock_sources=[ca.ClockSource(0, "Internal"), ca.ClockSource(1, "External")])
    monkeypatch.setattr(macos_audio, "_make_clock_controller", lambda: ca.ClockController(hal=hal))

    controller = G6Controller(FakeG6Api())
    tabs, _ = app_module.build_pages(controller)
    by_title = dict(tabs)

    assert by_title["Recording"].mic_boost.slider.enabled is True
    assert by_title["SBX"].surround.toggle.switch.enabled is True
    controller.shutdown()


def test_switching_to_stereo_direct_live_disables_recording_and_sbx(monkeypatch):
    """The gate must react to a change made *after* the tabs were built, not
    only reflect whatever the clock source was at startup."""
    from g6_gui import coreaudio as ca
    from g6_gui.controller import G6Controller
    from g6_gui.pages import macos_audio
    from tests.g6_gui.fake_coreaudio import FakeHal

    hal = FakeHal(current_clock_source_code=0)
    monkeypatch.setattr(macos_audio, "_make_clock_controller", lambda: ca.ClockController(hal=hal))

    controller = G6Controller(FakeG6Api())
    tabs, _ = app_module.build_pages(controller)
    by_title = dict(tabs)
    assert by_title["Recording"].mic_boost.slider.enabled is True

    by_title["macOS Audio"].clock_source.selection.value = "Stereo Direct"

    assert by_title["Recording"].mic_boost.slider.enabled is False
    assert by_title["SBX"].surround.toggle.switch.enabled is False
    controller.shutdown()
