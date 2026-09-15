from __future__ import annotations

import pytest

from g6_cli.g6_spec import PlaybackFilter
from g6_cli.g6_spec.decoder import DecoderMode
from g6_gui.controller import G6Controller
from g6_gui.pages import playback
from tests.g6_gui.fake_api import FakeG6Api


@pytest.fixture
def built():
    api = FakeG6Api()
    controller = G6Controller(api)
    content = playback.build(controller)
    yield api, controller, content
    controller.shutdown()


async def test_selecting_headphones_toggles_output(built):
    api, controller, content = built
    content.output.selection.value = "Headphones"
    await controller.flush()
    assert api.method_names() == ["playback_toggle_to_headphones"]


async def test_selecting_speakers_toggles_output(built):
    api, controller, content = built
    content.output.selection.value = "Headphones"
    content.output.selection.value = "Speakers"
    await controller.flush()
    assert api.method_names()[-1] == "playback_toggle_to_speakers"


async def test_direct_mode_switch(built):
    api, controller, content = built
    content.direct_mode.switch.value = True
    await controller.flush()
    assert api.calls == [("playback_enable_direct_mode", {"enable": True})]


async def test_spdif_direct_mode_switch(built):
    api, controller, content = built
    content.spdif_direct_mode.switch.value = True
    await controller.flush()
    assert api.calls == [("playback_enable_spdif_out_direct_mode", {"enable": True})]


async def test_filter_selection_sends_the_enum(built):
    api, controller, content = built
    content.filter.selection.value = "Slow Roll Off - Linear Phase"
    await controller.flush()
    assert api.calls == [
        ("playback_filter", {"playback_filter_enum": PlaybackFilter.SLOW_ROLL_OFF_LINEAR_PHASE})
    ]


async def test_decoder_selection_sends_the_enum(built):
    api, controller, content = built
    content.decoder.selection.value = "Night"
    await controller.flush()
    assert api.calls == [("decoder_mode", {"decoder_mode_enum": DecoderMode.NIGHT})]


def test_audio_controls_are_absent_on_macos(monkeypatch):
    monkeypatch.setattr("g6_gui.pages.playback.AUDIO_INTERFACE_SUPPORTED", False)
    controller = G6Controller(FakeG6Api())
    content = playback.build(controller)
    assert not hasattr(content, "volume")
    assert not hasattr(content, "mute")
    controller.shutdown()


def test_audio_controls_exist_but_start_disabled_on_linux(monkeypatch):
    monkeypatch.setattr("g6_gui.pages.playback.AUDIO_INTERFACE_SUPPORTED", True)
    controller = G6Controller(FakeG6Api())
    content = playback.build(controller)
    assert content.volume.slider.enabled is False
    controller.shutdown()


async def test_volume_is_debounced_into_one_write(monkeypatch):
    monkeypatch.setattr("g6_gui.pages.playback.AUDIO_INTERFACE_SUPPORTED", True)
    api = FakeG6Api()
    controller = G6Controller(api)
    content = playback.build(controller)
    for value in (10, 20, 30):
        content.volume.slider.value = value
    await controller.flush()
    assert len(api.calls) == 1
    assert api.calls[0][0] == "playback_volume"
    assert api.calls[0][1]["volume_percent"] == 30
    controller.shutdown()
