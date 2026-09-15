from __future__ import annotations

import pytest

from g6_cli.g6_spec.recording import MicrophoneEqualizerPreset
from g6_gui import convert
from g6_gui.controller import G6Controller
from g6_gui.pages import recording
from tests.g6_gui.fake_api import FakeG6Api


@pytest.fixture
def built():
    api = FakeG6Api()
    controller = G6Controller(api)
    content = recording.build(controller)
    yield api, controller, content
    controller.shutdown()


async def test_mic_boost_snaps_to_ten(built):
    api, controller, content = built
    content.mic_boost.slider.value = 17
    await controller.flush()
    assert api.calls == [("recording_mic_boost", {"decibel": 20})]


async def test_noise_reduction_switch(built):
    api, controller, content = built
    content.noise_reduction.switch.value = True
    await controller.flush()
    assert api.calls == [
        ("recording_voice_clarity_noise_reduction_enabled", {"enable": True})
    ]


async def test_noise_reduction_level_snaps_to_twenty(built):
    api, controller, content = built
    content.noise_reduction_level.slider.value = 33
    await controller.flush()
    assert api.calls == [
        ("recording_voice_clarity_noise_reduction_level", {"level_percent": 40})
    ]


def test_noise_reduction_level_is_disabled_until_noise_reduction_is_on(built):
    _, _, content = built
    assert content.noise_reduction_level.slider.enabled is False
    content.noise_reduction.switch.value = True
    assert content.noise_reduction_level.slider.enabled is True


async def test_aec_switch(built):
    api, controller, content = built
    content.aec.switch.value = True
    await controller.flush()
    assert api.calls == [
        ("recording_voice_clarity_acoustic_echo_cancellation_enabled", {"enable": True})
    ]


async def test_smart_volume_switch(built):
    api, controller, content = built
    content.smart_volume.switch.value = True
    await controller.flush()
    assert api.calls == [
        ("recording_voice_clarity_smart_volume_enabled", {"enable": True})
    ]


async def test_mic_eq_switch_and_preset(built):
    api, controller, content = built
    content.mic_eq.switch.value = True
    content.mic_eq_preset.selection.value = convert.EQ_PRESET_LABELS[2]
    await controller.flush()
    assert api.calls[0] == ("recording_voice_clarity_mic_equalizer_enabled", {"enable": True})
    assert api.calls[1][0] == "recording_voice_clarity_mic_equalizer_preset"
    assert api.calls[1][1]["preset"] is list(MicrophoneEqualizerPreset)[2]


def test_voice_clarity_and_noise_reduction_are_labelled_separately(built):
    _, _, content = built
    assert content.noise_reduction.switch.text == "Noise Reduction"


def test_audio_controls_absent_on_macos(monkeypatch):
    monkeypatch.setattr("g6_gui.pages.recording.AUDIO_INTERFACE_SUPPORTED", False)
    controller = G6Controller(FakeG6Api())
    content = recording.build(controller)
    assert not hasattr(content, "rec_volume")
    controller.shutdown()


async def test_audio_controls_present_on_linux(monkeypatch):
    monkeypatch.setattr("g6_gui.pages.recording.AUDIO_INTERFACE_SUPPORTED", True)
    api = FakeG6Api()
    controller = G6Controller(api)
    content = recording.build(controller)
    assert content.rec_volume.slider.enabled is False
    controller.shutdown()
