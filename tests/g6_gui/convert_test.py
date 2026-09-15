from __future__ import annotations

import pytest

from g6_cli.g6_model.sbx import Profile
from g6_cli.g6_spec import BOTH_CHANNELS, Channel, PlaybackFilter, SmartVolumeSpecialHex
from g6_cli.g6_spec.decoder import DecoderMode
from g6_cli.g6_spec.recording import MicrophoneEqualizerPreset
from g6_gui import convert


def test_channel_labels_are_the_cli_choices():
    assert convert.CHANNEL_LABELS == ["Both", "Left", "Right"]


@pytest.mark.parametrize(
    "label,expected",
    [
        ("Both", BOTH_CHANNELS),
        ("Left", {Channel.CHANNEL_1}),
        ("Right", {Channel.CHANNEL_2}),
    ],
)
def test_channels_from_label(label, expected):
    assert convert.channels_from_label(label) == expected


def test_channels_round_trip():
    for label in convert.CHANNEL_LABELS:
        assert convert.label_from_channels(convert.channels_from_label(label)) == label


def test_channels_from_label_rejects_unknown():
    with pytest.raises(ValueError):
        convert.channels_from_label("Middle")


def test_profile_labels_match_model_enum():
    assert convert.PROFILE_LABELS == ["Gaming", "Music", "Cinema", "Special"]
    assert convert.profile_from_label("Music") is Profile.Name.MUSIC


def test_filter_labels_are_human_readable_and_round_trip():
    assert "Fast Roll Off - Minimum Phase" in convert.FILTER_LABELS
    assert len(convert.FILTER_LABELS) == len(list(PlaybackFilter))
    for label in convert.FILTER_LABELS:
        assert convert.label_from_filter(convert.filter_from_label(label)) == label


def test_decoder_labels():
    assert convert.DECODER_LABELS == ["Normal", "Full", "Night"]
    assert convert.decoder_from_label("Night") is DecoderMode.NIGHT


def test_eq_presets_cover_every_enum_member():
    assert len(convert.EQ_PRESET_LABELS) == len(list(MicrophoneEqualizerPreset))
    assert convert.eq_preset_from_label(convert.EQ_PRESET_LABELS[0]) in MicrophoneEqualizerPreset


def test_smart_volume_special_labels():
    assert convert.SMART_VOLUME_LABELS == ["None", "Night", "Loud"]
    assert convert.smart_volume_special_from_label("None") is None
    assert convert.smart_volume_special_from_label("Night") is SmartVolumeSpecialHex.SMART_VOLUME_NIGHT
    assert convert.smart_volume_special_from_label("Loud") is SmartVolumeSpecialHex.SMART_VOLUME_LOUD
