"""Recording [HID] + [Audio] — mic level, boost and Voice Clarity."""

from __future__ import annotations

import toga

from g6_cli.g6_spec.recording import MicrophoneEqualizerPreset
from g6_gui import convert, help as help_text, widgets
from g6_gui.platform import IS_MACOS
from g6_gui.controller import G6Controller
from g6_gui.platform import AUDIO_INTERFACE_SUPPORTED

TITLE = "Recording"


def is_available() -> bool:
    return True


def build(controller: G6Controller) -> toga.Widget:
    recording_model = controller.model.get_recording()

    content = widgets.page()

    hid_section = widgets.section("Recording")
    if IS_MACOS:
        hid_section.add(widgets.note_block(help_text.RECORDING_SBX_DISABLED_BY_CLOCK_SOURCE))

    mic_boost_row = widgets.slider_row(
        "Mic Boost",
        min=0,
        max=30,
        value=recording_model.get_mic_boost(),
        step=10,
        on_change=lambda widget: controller.submit(
            "recording_mic_boost", decibel=int(widget.value)
        ),
        help=help_text.REC_MIC_BOOST,
    )
    hid_section.add(mic_boost_row)

    content.add(hid_section)
    content.mic_boost = mic_boost_row

    voice_clarity_section = _build_voice_clarity_section(controller, recording_model)
    content.add(voice_clarity_section)
    content.noise_reduction = voice_clarity_section.noise_reduction
    content.noise_reduction_level = voice_clarity_section.noise_reduction_level
    content.aec = voice_clarity_section.aec
    content.smart_volume = voice_clarity_section.smart_volume
    content.mic_eq = voice_clarity_section.mic_eq
    content.mic_eq_preset = voice_clarity_section.mic_eq_preset

    if AUDIO_INTERFACE_SUPPORTED:
        audio_section = _build_audio_section(controller, recording_model)
        content.add(audio_section)
        content.audio_section = audio_section
        content.mute = audio_section.mute
        content.rec_volume = audio_section.rec_volume
        content.rec_channels = audio_section.rec_channels
        content.mon_mute = audio_section.mon_mute
        content.mon_volume = audio_section.mon_volume
        content.mon_channels = audio_section.mon_channels
        widgets.set_enabled(audio_section, False)

    return content


def _build_voice_clarity_section(controller: G6Controller, recording_model) -> toga.Box:
    section = widgets.section("Voice Clarity")

    noise_reduction_level_row = widgets.slider_row(
        "Noise Reduction Level",
        min=0,
        max=100,
        value=recording_model.get_voice_clarity_noise_reduction_level(),
        step=20,
        on_change=lambda widget: controller.debounced(
            "recording_voice_clarity_noise_reduction_level",
            "recording_voice_clarity_noise_reduction_level",
            level_percent=int(widget.value),
        ),
        help=help_text.REC_NOISE_REDUCTION_LEVEL,
    )

    noise_reduction_row = widgets.switch_row(
        "Noise Reduction",
        value=recording_model.get_voice_clarity_noise_reduction_enabled(),
        on_change=lambda widget: _on_noise_reduction_change(
            controller, widget, noise_reduction_level_row
        ),
        help=help_text.REC_NOISE_REDUCTION,
    )
    section.add(noise_reduction_row)
    section.add(noise_reduction_level_row)
    widgets.set_enabled(
        noise_reduction_level_row, recording_model.get_voice_clarity_noise_reduction_enabled()
    )

    aec_row = widgets.switch_row(
        "Acoustic Echo Cancellation",
        value=recording_model.get_voice_clarity_acoustic_echo_cancellation_enabled(),
        on_change=lambda widget: controller.submit(
            "recording_voice_clarity_acoustic_echo_cancellation_enabled",
            enable=widget.value,
            revert=lambda: setattr(widget, "value", not widget.value),
        ),
        help=help_text.REC_AEC,
    )
    section.add(aec_row)

    smart_volume_row = widgets.switch_row(
        "Smart Volume",
        value=recording_model.get_voice_clarity_smart_volume_enabled(),
        on_change=lambda widget: controller.submit(
            "recording_voice_clarity_smart_volume_enabled",
            enable=widget.value,
            revert=lambda: setattr(widget, "value", not widget.value),
        ),
        help=help_text.REC_SMART_VOLUME,
    )
    section.add(smart_volume_row)

    mic_eq_preset_row = widgets.select_row(
        "Mic EQ Preset",
        items=convert.EQ_PRESET_LABELS,
        value=_preset_label(recording_model.get_voice_clarity_mic_equalizer_preset()),
        on_change=lambda widget: controller.submit(
            "recording_voice_clarity_mic_equalizer_preset",
            preset=convert.eq_preset_from_label(widget.value),
        ),
        help=help_text.REC_MIC_EQ_PRESET,
    )

    mic_eq_row = widgets.switch_row(
        "Mic Equalizer",
        value=recording_model.get_voice_clarity_mic_equalizer_enabled(),
        on_change=lambda widget: _on_mic_eq_change(controller, widget, mic_eq_preset_row),
        help=help_text.REC_MIC_EQ,
    )
    section.add(mic_eq_row)
    section.add(mic_eq_preset_row)
    widgets.set_enabled(
        mic_eq_preset_row, recording_model.get_voice_clarity_mic_equalizer_enabled()
    )

    section.noise_reduction = noise_reduction_row
    section.noise_reduction_level = noise_reduction_level_row
    section.aec = aec_row
    section.smart_volume = smart_volume_row
    section.mic_eq = mic_eq_row
    section.mic_eq_preset = mic_eq_preset_row

    return section


def _preset_label(preset: MicrophoneEqualizerPreset) -> str:
    return convert.EQ_PRESET_LABELS[list(MicrophoneEqualizerPreset).index(preset)]


def _on_noise_reduction_change(controller: G6Controller, widget, level_row) -> None:
    widgets.set_enabled(level_row, widget.value)
    controller.submit(
        "recording_voice_clarity_noise_reduction_enabled",
        enable=widget.value,
        revert=lambda: setattr(widget, "value", not widget.value),
    )


def _on_mic_eq_change(controller: G6Controller, widget, preset_row) -> None:
    widgets.set_enabled(preset_row, widget.value)
    controller.submit(
        "recording_voice_clarity_mic_equalizer_enabled",
        enable=widget.value,
        revert=lambda: setattr(widget, "value", not widget.value),
    )


def _build_audio_section(controller: G6Controller, recording_model) -> toga.Box:
    audio_section = widgets.section("Audio interface")

    mute_row = widgets.switch_row(
        "Mute",
        value=recording_model.get_mute(),
        on_change=lambda widget: controller.submit(
            "recording_mute",
            mute=widget.value,
            revert=lambda: setattr(widget, "value", not widget.value),
        ),
        help=help_text.REC_MUTE,
    )
    audio_section.add(mute_row)

    rec_channels_row = widgets.select_row(
        "Recording volume channels",
        items=convert.CHANNEL_LABELS,
        value="Both",
        on_change=lambda widget: _on_rec_volume_change(
            controller, rec_volume_row.slider.value, widget.value
        ),
        help=help_text.CHANNELS,
    )

    def _on_rec_volume_slider_change(widget):
        _on_rec_volume_change(controller, widget.value, rec_channels_row.selection.value)

    rec_volume_row = widgets.slider_row(
        "Recording Volume",
        min=0,
        max=100,
        value=recording_model.get_mic_recording_volume(
            next(iter(convert.channels_from_label("Both")))
        ),
        step=10,
        on_change=_on_rec_volume_slider_change,
        help=help_text.REC_VOLUME,
    )

    audio_section.add(rec_volume_row)
    audio_section.add(rec_channels_row)

    mon_mute_row = widgets.switch_row(
        "Monitoring Mute",
        value=recording_model.get_mic_monitoring_mute(),
        on_change=lambda widget: controller.submit(
            "recording_mic_monitoring_mute",
            mute=widget.value,
            revert=lambda: setattr(widget, "value", not widget.value),
        ),
    )
    audio_section.add(mon_mute_row)

    mon_channels_row = widgets.select_row(
        "Monitoring volume channels",
        items=convert.CHANNEL_LABELS,
        value="Both",
        on_change=lambda widget: _on_mon_volume_change(
            controller, mon_volume_row.slider.value, widget.value
        ),
        help=help_text.CHANNELS,
    )

    def _on_mon_volume_slider_change(widget):
        _on_mon_volume_change(controller, widget.value, mon_channels_row.selection.value)

    mon_volume_row = widgets.slider_row(
        "Monitoring Volume",
        min=0,
        max=100,
        value=recording_model.get_mic_monitoring_volume(
            next(iter(convert.channels_from_label("Both")))
        ),
        step=10,
        on_change=_on_mon_volume_slider_change,
        help=help_text.REC_MONITORING,
    )

    audio_section.add(mon_volume_row)
    audio_section.add(mon_channels_row)

    audio_section.mute = mute_row
    audio_section.rec_volume = rec_volume_row
    audio_section.rec_channels = rec_channels_row
    audio_section.mon_mute = mon_mute_row
    audio_section.mon_volume = mon_volume_row
    audio_section.mon_channels = mon_channels_row

    return audio_section


def _on_rec_volume_change(controller: G6Controller, volume_value, channels_label) -> None:
    controller.debounced(
        "recording_mic_recording_volume",
        "recording_mic_recording_volume",
        volume_percent=int(volume_value),
        channels=convert.channels_from_label(channels_label),
    )


def _on_mon_volume_change(controller: G6Controller, volume_value, channels_label) -> None:
    controller.debounced(
        "recording_mic_monitoring_volume",
        "recording_mic_monitoring_volume",
        volume_percent=int(volume_value),
        channels=convert.channels_from_label(channels_label),
    )
