"""Conversions between user-facing labels and g6_cli enum values.

Centralised so that every page shows the same wording for the same value.
"""

from __future__ import annotations

from g6_cli.g6_model.sbx import Profile
from g6_cli.g6_spec import BOTH_CHANNELS, Channel, PlaybackFilter, SmartVolumeSpecialHex
from g6_cli.g6_spec.decoder import DecoderMode
from g6_cli.g6_spec.recording import MicrophoneEqualizerPreset

from g6_gui.filters import NON_OVERSAMPLING

# ── Channels ──

CHANNEL_LABELS: list[str] = ["Both", "Left", "Right"]

_CHANNELS_BY_LABEL: dict[str, set[Channel]] = {
    "Both": BOTH_CHANNELS,
    "Left": {Channel.CHANNEL_1},
    "Right": {Channel.CHANNEL_2},
}


def channels_from_label(label: str) -> set[Channel]:
    try:
        return _CHANNELS_BY_LABEL[label]
    except KeyError:
        raise ValueError(f"Unsupported channels value: {label}") from None


def label_from_channels(channels: set[Channel]) -> str:
    for label, value in _CHANNELS_BY_LABEL.items():
        if value == channels:
            return label
    raise ValueError(f"Unsupported channels set: {channels}")


# ── SBX profiles ──

PROFILE_LABELS: list[str] = [name.value for name in Profile.Name]


def profile_from_label(label: str) -> Profile.Name:
    return Profile.Name(label)


# ── Playback filter ──
#
# NON_OVERSAMPLING is not a PlaybackFilter member -- it can't be, since that
# enum lives in the frozen src/g6_cli mirror (HANDOFF.md §2). It is a
# separate object (see g6_gui.filters) that duck-types the one attribute
# upstream reads off it. It is listed LAST on purpose, after the four
# Creative-supported filters, so nobody selects the hidden filter by
# accident.

_FILTER_LABELS: dict[object, str] = {
    PlaybackFilter.FAST_ROLL_OFF_MINIMUM_PHASE: "Fast Roll Off - Minimum Phase",
    PlaybackFilter.SLOW_ROLL_OFF_MINIMUM_PHASE: "Slow Roll Off - Minimum Phase",
    PlaybackFilter.FAST_ROLL_OFF_LINEAR_PHASE: "Fast Roll Off - Linear Phase",
    PlaybackFilter.SLOW_ROLL_OFF_LINEAR_PHASE: "Slow Roll Off - Linear Phase",
    NON_OVERSAMPLING: "Non-Over-Sampling (NOS)",
}

FILTER_LABELS: list[str] = list(_FILTER_LABELS.values())


def filter_from_label(label: str) -> PlaybackFilter:
    for value, text in _FILTER_LABELS.items():
        if text == label:
            return value
    raise ValueError(f"Unsupported playback filter: {label}")


def label_from_filter(playback_filter) -> str:
    return _FILTER_LABELS[playback_filter]


# ── Decoder ──

DECODER_LABELS: list[str] = ["Normal", "Full", "Night"]


def decoder_from_label(label: str) -> DecoderMode:
    return DecoderMode[label.upper()]


# ── Microphone equalizer presets ──

EQ_PRESET_LABELS: list[str] = [
    preset.name.replace("PRESET_DM_", "Dynamic Mic ").replace("PRESET_", "Preset ")
    for preset in MicrophoneEqualizerPreset
]


def eq_preset_from_label(label: str) -> MicrophoneEqualizerPreset:
    for preset, text in zip(MicrophoneEqualizerPreset, EQ_PRESET_LABELS):
        if text == label:
            return preset
    raise ValueError(f"Unsupported microphone equalizer preset: {label}")


# ── Smart Volume special values ──

SMART_VOLUME_LABELS: list[str] = ["None", "Night", "Loud"]


def smart_volume_special_from_label(label: str) -> SmartVolumeSpecialHex | None:
    match label:
        case "None":
            return None
        case "Night":
            return SmartVolumeSpecialHex.SMART_VOLUME_NIGHT
        case "Loud":
            return SmartVolumeSpecialHex.SMART_VOLUME_LOUD
    raise ValueError(f"Unsupported Smart Volume value: {label}")
