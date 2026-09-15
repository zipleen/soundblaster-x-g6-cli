"""Mixer [Audio] — monitoring and recording levels. Linux only."""

from __future__ import annotations

import toga

from g6_cli.g6_spec import BOTH_CHANNELS, Channel
from g6_gui import convert, widgets
from g6_gui.controller import G6Controller
from g6_gui.platform import AUDIO_INTERFACE_SUPPORTED

TITLE = "Mixer"

# One row per mixer group: (attribute name, api method prefix, display label).
_GROUPS = [
    ("monitoring_line_in", "mixer_monitoring_line_in", "Monitoring: Line In"),
    ("monitoring_external_mic", "mixer_monitoring_external_mic", "Monitoring: External Mic"),
    ("monitoring_spdif_in", "mixer_monitoring_spdif_in", "Monitoring: SPDIF In"),
    ("recording_line_in", "mixer_recording_line_in", "Recording: Line In"),
    ("recording_external_mic", "mixer_recording_external_mic", "Recording: External Mic"),
    ("recording_spdif_in", "mixer_recording_spdif_in", "Recording: SPDIF In"),
    ("recording_what_u_hear", "mixer_recording_what_u_hear", "Recording: What U Hear"),
]


def is_available() -> bool:
    return AUDIO_INTERFACE_SUPPORTED


def _build_group(controller: G6Controller, attr: str, prefix: str, label: str) -> toga.Box:
    """Build one mute/volume/channels group and wrap the three rows in a box."""
    mixer_model = controller.model.get_mixer()
    mute_getter = getattr(mixer_model, f"get_{attr}_mute")
    volume_getter = getattr(mixer_model, f"get_{attr}_volume")

    # Track the currently-selected channels so the volume slider's debounced
    # call always uses the latest selection, not a stale snapshot.
    selected_channels = {"channels": BOTH_CHANNELS}

    def on_mute_change(widget):
        controller.submit(
            f"{prefix}_mute",
            mute=widget.value,
            revert=lambda: setattr(mute_row.switch, "value", not widget.value),
        )

    def on_volume_change(widget):
        controller.debounced(
            f"mixer_{attr}",
            f"{prefix}_volume",
            volume_percent=int(widget.value),
            channels=selected_channels["channels"],
        )

    def on_channels_change(widget):
        selected_channels["channels"] = convert.channels_from_label(widget.value)

    mute_row = widgets.switch_row("Mute", value=mute_getter(), on_change=on_mute_change)
    volume_row = widgets.slider_row(
        "Volume",
        min=0,
        max=100,
        value=volume_getter(Channel.CHANNEL_1),
        step=10,
        on_change=on_volume_change,
    )
    channels_row = widgets.select_row(
        "Channels",
        items=convert.CHANNEL_LABELS,
        value=convert.CHANNEL_LABELS[0],
        on_change=on_channels_change,
    )

    group_box = widgets.section(label)
    group_box.add(mute_row)
    group_box.add(volume_row)
    group_box.add(channels_row)
    group_box.mute = mute_row
    group_box.volume = volume_row
    group_box.channels = channels_row
    return group_box


def build(controller: G6Controller) -> toga.Widget:
    mixer_model = controller.model.get_mixer()

    playback_mute_row = widgets.switch_row(
        "Playback Mute",
        value=mixer_model.get_playback_mute(),
        on_change=lambda widget: controller.submit(
            "mixer_playback_mute",
            mute=widget.value,
            revert=lambda: setattr(playback_mute_row.switch, "value", not widget.value),
        ),
    )

    children = [playback_mute_row]
    group_boxes = {}
    for attr, prefix, label in _GROUPS:
        group_box = _build_group(controller, attr, prefix, label)
        children.append(group_box)
        group_boxes[attr] = group_box

    content = widgets.page(*children)
    content.playback_mute = playback_mute_row
    for attr, group_box in group_boxes.items():
        setattr(content, attr, group_box)

    # widgets.page() wraps its children in a toga.ScrollContainer, whose
    # `.children` always reports [] (it holds a single `.content`, not a
    # child list) — so widgets.set_enabled(content, False) would not reach
    # any real widget. Disable each top-level child directly instead.
    for child in children:
        widgets.set_enabled(child, False)
    return content
