from __future__ import annotations

import pytest

from g6_cli.g6_spec import BOTH_CHANNELS, Channel
from g6_gui.controller import G6Controller
from g6_gui.pages import mixer
from tests.g6_gui.fake_api import FakeG6Api

GROUPS = [
    ("monitoring_line_in", "mixer_monitoring_line_in"),
    ("monitoring_external_mic", "mixer_monitoring_external_mic"),
    ("monitoring_spdif_in", "mixer_monitoring_spdif_in"),
    ("recording_line_in", "mixer_recording_line_in"),
    ("recording_external_mic", "mixer_recording_external_mic"),
    ("recording_spdif_in", "mixer_recording_spdif_in"),
    ("recording_what_u_hear", "mixer_recording_what_u_hear"),
]


@pytest.fixture
def built(monkeypatch):
    monkeypatch.setattr("g6_gui.pages.mixer.AUDIO_INTERFACE_SUPPORTED", True)
    api = FakeG6Api()
    controller = G6Controller(api)
    content = mixer.build(controller)
    yield api, controller, content
    controller.shutdown()


async def test_playback_mute(built):
    api, controller, content = built
    content.playback_mute.switch.value = True
    await controller.flush()
    assert api.calls == [("mixer_playback_mute", {"mute": True})]


@pytest.mark.parametrize("attr,prefix", GROUPS, ids=[g[0] for g in GROUPS])
async def test_every_group_mute(built, attr, prefix):
    api, controller, content = built
    getattr(content, attr).mute.switch.value = True
    await controller.flush()
    assert api.calls == [(f"{prefix}_mute", {"mute": True})]


@pytest.mark.parametrize("attr,prefix", GROUPS, ids=[g[0] for g in GROUPS])
async def test_every_group_volume_snaps_to_ten_and_debounces(built, attr, prefix):
    api, controller, content = built
    group = getattr(content, attr)
    group.volume.slider.value = 44
    group.volume.slider.value = 66
    await controller.flush()
    assert api.calls == [
        (f"{prefix}_volume", {"volume_percent": 70, "channels": BOTH_CHANNELS})
    ]


async def test_channel_selection_reaches_the_volume_call(built):
    api, controller, content = built
    content.monitoring_line_in.channels.selection.value = "Left"
    content.monitoring_line_in.volume.slider.value = 30
    await controller.flush()
    assert api.calls[-1][1]["channels"] == {Channel.CHANNEL_1}


def test_page_starts_disabled_until_the_interface_is_claimed(built):
    _, _, content = built
    assert content.playback_mute.switch.enabled is False


def test_page_is_unavailable_on_macos(monkeypatch):
    monkeypatch.setattr("g6_gui.pages.mixer.AUDIO_INTERFACE_SUPPORTED", False)
    assert mixer.is_available() is False
