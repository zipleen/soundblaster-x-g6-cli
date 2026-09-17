"""Playback [HID] + [Audio] + Decoder [HID]."""

from __future__ import annotations

import toga

from g6_gui import convert, filters, help as help_text, widgets
from g6_gui.controller import G6Controller
from g6_gui.platform import (
    AUDIO_INTERFACE_SUPPORTED,
    DIRECT_MODE_SUPPORTED,
    IS_MACOS,
    open_audio_midi_setup,
)

TITLE = "Playback"

_OUTPUT_LABELS = ["Speakers", "Headphones"]

_DIRECT_MODE_UNSUPPORTED = (
    "Direct Mode is set by macOS, not by the device, so the switch above does "
    "nothing. Use Audio MIDI Setup \u2192 Clock Source: \u201cStereo Direct\u201d is "
    "Direct Mode, \u201cDSP Clock\u201d keeps SBX and the other effects.\n"
    "SPDIF-Out Direct is left enabled because macOS has no equivalent setting "
    "for it \u2014 whether it works here is untested."
)

_DECODER_NOTE = (
    "Only affects a Dolby Digital bitstream arriving at the optical input. "
    "It does nothing for PCM over USB."
)


def _on_open_audio_midi_setup(widget, **_kwargs) -> None:
    open_audio_midi_setup()


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
        help=help_text.OUTPUT,
    )
    hid_section.add(output_row)

    # Direct Mode and SPDIF-Out Direct are two positions of one three-way Output
    # Mode setting on the device (Audio Effects / Direct / SPDIF-Out Direct), so
    # enabling either one disables the other. This guard keeps the mirrored
    # switch from firing its own handler and sending a redundant packet.
    exclusive = {"suppress": False}

    def make_mode_handler(method: str, other_row_name: str):
        def on_change(widget):
            if exclusive["suppress"]:
                return
            if widget.value:
                other = getattr(content, other_row_name, None)
                if other is not None and other.switch.value:
                    exclusive["suppress"] = True
                    try:
                        other.switch.value = False
                    finally:
                        exclusive["suppress"] = False
            controller.submit(
                method,
                enable=widget.value,
                revert=lambda: setattr(widget, "value", not widget.value),
            )

        return on_change

    direct_mode_row = widgets.switch_row(
        "Direct Mode",
        value=playback_model.get_direct_mode_enabled(),
        on_change=make_mode_handler(
            "playback_enable_direct_mode", "spdif_direct_mode"
        ),
        help=help_text.direct_mode(),
    )
    hid_section.add(direct_mode_row)

    spdif_direct_mode_row = widgets.switch_row(
        "SPDIF-Out Direct Mode",
        value=playback_model.get_spdif_out_direct_mode_enabled(),
        on_change=make_mode_handler(
            "playback_enable_spdif_out_direct_mode", "direct_mode"
        ),
        help=help_text.spdif_out_direct(),
    )
    hid_section.add(spdif_direct_mode_row)

    if not DIRECT_MODE_SUPPORTED:
        # Only Direct Mode is known to be overridden by the OS. SPDIF-Out Direct
        # is a third state that macOS's Clock Source (DSP Clock / Stereo Direct)
        # has no equivalent for, so it may well still work -- it is left enabled
        # rather than disabled on an assumption nobody has tested.
        widgets.set_enabled(direct_mode_row.control_row, False)
        hid_section.add(widgets.warning_block(_DIRECT_MODE_UNSUPPORTED))
        if IS_MACOS:
            hid_section.add(
                widgets.button_row(
                    ("Open Audio MIDI Setup", _on_open_audio_midi_setup)
                )
            )

    initial_filter_label = convert.label_from_filter(playback_model.get_filter())
    nos_label = convert.label_from_filter(filters.NON_OVERSAMPLING)

    filter_warning = widgets.dynamic_warning_block(
        help_text.FILTER_NOS_WARNING if initial_filter_label == nos_label else ""
    )

    def _filter_warning_text(label: str) -> str:
        return help_text.FILTER_NOS_WARNING if label == nos_label else ""

    # `filter_state["label"]` tracks the last label the device actually
    # confirmed (i.e. the revert target). `filter_state["reverting"]` guards
    # against gotcha 12 (Toga's Cocoa backend fires on_change for a
    # *programmatic* value assignment): _revert() below sets
    # `widget.value = previous_label`, which would otherwise re-enter
    # _on_filter_change and resubmit the very filter being reverted to.
    filter_state = {"label": initial_filter_label, "reverting": False}

    def _on_filter_change(widget) -> None:
        if filter_state["reverting"]:
            return

        previous_label = filter_state["label"]
        selected = convert.filter_from_label(widget.value)

        def _revert() -> None:
            filter_state["reverting"] = True
            try:
                widget.value = previous_label
            finally:
                filter_state["reverting"] = False
            filter_warning.set_text(_filter_warning_text(previous_label))

        def _on_success() -> None:
            filter_state["label"] = widget.value

        # Only the NOS shim gets `tolerate`: G6Api.playback_filter() writes
        # the correct bytes to the wire *before* trying to record the value
        # in G6Model, and only the shim (see filters.py's docstring) makes
        # that second step raise ValueError. A ValueError from one of the
        # four real filters would be a genuine failure and must still revert
        # and surface an error, so this is scoped to `selected is
        # filters.NON_OVERSAMPLING` rather than to ValueError in general.
        tolerate = (ValueError,) if selected is filters.NON_OVERSAMPLING else ()
        controller.submit(
            "playback_filter",
            playback_filter_enum=selected,
            revert=_revert,
            on_success=_on_success,
            tolerate=tolerate,
        )
        filter_warning.set_text(_filter_warning_text(widget.value))

    filter_row = widgets.select_row(
        "Filter",
        items=convert.FILTER_LABELS,
        value=initial_filter_label,
        on_change=_on_filter_change,
        help=help_text.FILTER,
    )
    # Grouped in its own box (rather than added straight to hid_section) so
    # the FILTER_NOS help expands right below the warning it explains,
    # instead of at the bottom of the whole Playback section.
    filter_group = toga.Box(style=toga.style.pack.Pack(direction=toga.style.pack.COLUMN))
    filter_group.add(filter_row)
    filter_group.add(filter_warning)
    # FILTER's help text ends with "see its own help" -- this is that help,
    # attached to the warning it explains.
    widgets.help_for(filter_group, anchor=filter_warning, text=help_text.FILTER_NOS)
    hid_section.add(filter_group)

    decoder_row = widgets.select_row(
        "Decoder mode",
        items=convert.DECODER_LABELS,
        value=decoder_model.get_mode().name.capitalize(),
        on_change=lambda widget: controller.submit(
            "decoder_mode",
            decoder_mode_enum=convert.decoder_from_label(widget.value),
        ),
        help=help_text.DECODER,
    )
    hid_section.add(decoder_row)
    hid_section.add(widgets.note_block(_DECODER_NOTE))

    content.add(hid_section)
    content.output = output_row
    content.direct_mode = direct_mode_row
    content.spdif_direct_mode = spdif_direct_mode_row
    content.filter = filter_row
    content.filter_warning = filter_warning
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
        help=help_text.PLAYBACK_MUTE,
    )
    audio_section.add(mute_row)

    channels_row = widgets.select_row(
        "Volume channels",
        items=convert.CHANNEL_LABELS,
        value="Both",
        on_change=lambda widget: _on_volume_change(
            controller, volume_row.slider.value, widget.value
        ),
        help=help_text.CHANNELS,
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
        help=help_text.PLAYBACK_VOLUME,
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
    headphones_buttons = widgets.button_row(
        ("Stereo", lambda widget: controller.submit("playback_headphones_to_stereo")),
        ("5.1", lambda widget: controller.submit("playback_headphones_to_5_1")),
        ("7.1", lambda widget: controller.submit("playback_headphones_to_7_1")),
    )

    # These four rows share one (i), because they share one caveat: 5.1 and 7.1
    # send byte-identical packets to Stereo (upstream says so in its own
    # docstring in g6_spec/playback.py), so what they actually change is
    # unconfirmed. help_text.SURROUND_71 explains what virtual 7.1 really is
    # and where the channel count is decided. Grouped into their own box so the
    # explanation expands below all four rows rather than wedging between the
    # Speakers and Headphones halves -- the same reason help_for() exists.
    channel_group = toga.Box()
    channel_group.style.direction = "column"
    channel_group.add(widgets.note("Speakers"))
    channel_group.add(speakers_buttons)
    channel_group.add(widgets.note("Headphones"))
    channel_group.add(headphones_buttons)
    widgets.help_for(channel_group, anchor=speakers_buttons, text=help_text.SURROUND_71)
    audio_section.add(channel_group)

    audio_section.channel_modes = channel_group
    audio_section.speakers_modes = speakers_buttons
    audio_section.headphones_modes = headphones_buttons

    return audio_section


def _on_volume_change(controller: G6Controller, volume_value, channels_label) -> None:
    controller.debounced(
        "playback_volume",
        "playback_volume",
        volume_percent=int(volume_value),
        channels=convert.channels_from_label(channels_label),
    )
