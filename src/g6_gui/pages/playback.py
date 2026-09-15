"""Playback [HID] + [Audio] + Decoder [HID]."""

from __future__ import annotations

import toga

from g6_gui import convert, widgets
from g6_gui.controller import G6Controller
from g6_gui.platform import AUDIO_INTERFACE_SUPPORTED

TITLE = "Playback"

_OUTPUT_LABELS = ["Speakers", "Headphones"]


def is_available() -> bool:
    return True


def build(controller: G6Controller) -> toga.Widget:
    playback_model = controller.model.get_playback()
    decoder_model = controller.model.get_decoder()

    content = widgets.page()

    hid_section = widgets.section("Playback")

    output_row = widgets.select_row(
        "Output",
        items=_OUTPUT_LABELS,
        value="Speakers" if playback_model.get_is_speakers() else "Headphones",
        on_change=_make_output_handler(controller),
    )
    hid_section.add(output_row)

    direct_mode_row = widgets.switch_row(
        "Direct Mode",
        value=playback_model.get_direct_mode_enabled(),
        on_change=lambda widget: controller.submit(
            "playback_enable_direct_mode",
            enable=widget.value,
            revert=lambda: setattr(widget, "value", not widget.value),
        ),
    )
    hid_section.add(direct_mode_row)

    spdif_direct_mode_row = widgets.switch_row(
        "SPDIF-Out Direct Mode",
        value=playback_model.get_spdif_out_direct_mode_enabled(),
        on_change=lambda widget: controller.submit(
            "playback_enable_spdif_out_direct_mode",
            enable=widget.value,
            revert=lambda: setattr(widget, "value", not widget.value),
        ),
    )
    hid_section.add(spdif_direct_mode_row)

    filter_row = widgets.select_row(
        "Filter",
        items=convert.FILTER_LABELS,
        value=convert.label_from_filter(playback_model.get_filter()),
        on_change=lambda widget: controller.submit(
            "playback_filter",
            playback_filter_enum=convert.filter_from_label(widget.value),
        ),
    )
    hid_section.add(filter_row)

    decoder_row = widgets.select_row(
        "Decoder mode",
        items=convert.DECODER_LABELS,
        value=decoder_model.get_mode().name.capitalize(),
        on_change=lambda widget: controller.submit(
            "decoder_mode",
            decoder_mode_enum=convert.decoder_from_label(widget.value),
        ),
    )
    hid_section.add(decoder_row)

    content.add(hid_section)
    content.output = output_row
    content.direct_mode = direct_mode_row
    content.spdif_direct_mode = spdif_direct_mode_row
    content.filter = filter_row
    content.decoder = decoder_row

    if AUDIO_INTERFACE_SUPPORTED:
        audio_section = _build_audio_section(controller, playback_model)
        content.add(audio_section)
        content.audio_section = audio_section
        content.mute = audio_section.mute
        content.volume = audio_section.volume
        content.volume_channels = audio_section.volume_channels
        widgets.set_enabled(audio_section, False)

    return content


def _make_output_handler(controller: G6Controller):
    def on_change(widget):
        if widget.value == "Speakers":
            controller.submit("playback_toggle_to_speakers")
        else:
            controller.submit("playback_toggle_to_headphones")

    return on_change


def _build_audio_section(controller: G6Controller, playback_model) -> toga.Box:
    audio_section = widgets.section("Audio interface")

    mute_row = widgets.switch_row(
        "Mute",
        value=playback_model.get_mute(),
        on_change=lambda widget: controller.submit(
            "playback_mute",
            mute=widget.value,
            revert=lambda: setattr(widget, "value", not widget.value),
        ),
    )
    audio_section.add(mute_row)

    channels_row = widgets.select_row(
        "Volume channels",
        items=convert.CHANNEL_LABELS,
        value="Both",
        on_change=lambda widget: _on_volume_change(
            controller, volume_row.slider.value, widget.value
        ),
    )

    def _on_volume_slider_change(widget):
        _on_volume_change(controller, widget.value, channels_row.selection.value)

    volume_row = widgets.slider_row(
        "Volume",
        min=0,
        max=100,
        value=playback_model.get_volume(next(iter(convert.channels_from_label("Both")))),
        step=1,
        on_change=_on_volume_slider_change,
    )

    audio_section.add(volume_row)
    audio_section.add(channels_row)

    audio_section.mute = mute_row
    audio_section.volume = volume_row
    audio_section.volume_channels = channels_row

    speakers_buttons = widgets.button_row(
        ("Stereo", lambda widget: controller.submit("playback_speakers_to_stereo")),
        ("5.1", lambda widget: controller.submit("playback_speakers_to_5_1")),
        ("7.1", lambda widget: controller.submit("playback_speakers_to_7_1")),
    )
    audio_section.add(widgets.note("Speakers"))
    audio_section.add(speakers_buttons)

    headphones_buttons = widgets.button_row(
        ("Stereo", lambda widget: controller.submit("playback_headphones_to_stereo")),
        ("5.1", lambda widget: controller.submit("playback_headphones_to_5_1")),
        ("7.1", lambda widget: controller.submit("playback_headphones_to_7_1")),
    )
    audio_section.add(widgets.note("Headphones"))
    audio_section.add(headphones_buttons)

    return audio_section


def _on_volume_change(controller: G6Controller, volume_value, channels_label) -> None:
    controller.debounced(
        "playback_volume",
        "playback_volume",
        volume_percent=int(volume_value),
        channels=convert.channels_from_label(channels_label),
    )
