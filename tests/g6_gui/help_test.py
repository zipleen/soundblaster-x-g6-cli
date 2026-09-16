"""Help text coverage and the platform gating that depends on it."""

from __future__ import annotations

import pytest

from g6_gui import help as help_text, widgets
from g6_gui.controller import G6Controller
from g6_gui.pages import lighting, playback, recording, sbx
from tests.g6_gui.fake_api import FakeG6Api


@pytest.fixture
def controller():
    controller = G6Controller(FakeG6Api())
    yield controller
    controller.shutdown()


ROWS_THAT_MUST_EXPLAIN_THEMSELVES = [
    (playback, ["output", "direct_mode", "spdif_direct_mode", "filter", "decoder"]),
    (
        recording,
        ["mic_boost", "noise_reduction", "aec", "smart_volume", "mic_eq", "mic_eq_preset"],
    ),
    (
        sbx,
        [
            "editing",
            "surround",
            "crystalizer",
            "bass",
            "smart_volume",
            "dialog_plus",
            "smart_volume_special",
        ],
    ),
]


@pytest.mark.parametrize("module, attrs", ROWS_THAT_MUST_EXPLAIN_THEMSELVES)
def test_every_documented_control_has_an_info_button(controller, module, attrs):
    page = module.build(controller)
    for attr in attrs:
        row = getattr(page, attr)
        assert hasattr(row, "info_button"), f"{module.__name__}.{attr} has no (i) button"
        assert row.help.lines, f"{module.__name__}.{attr} has empty help"


def test_lighting_controls_explain_themselves(controller):
    page = lighting.build(controller)
    assert hasattr(page.lighting_enabled, "info_button")


def test_sbx_effect_help_expands_below_the_slider_not_between(controller):
    """The (i) sits by the label; the text must not wedge between switch and slider."""
    page = sbx.build(controller)
    effect = page.surround
    assert effect.info_button in effect.toggle.children
    assert effect.help not in effect.children

    effect.info_button.on_press()
    assert effect.children[-1] is effect.help


def test_help_text_has_no_markdown_artifacts():
    """Help renders as plain labels, so stray markup would show up literally."""
    texts = [
        value
        for name, value in vars(help_text).items()
        if name.isupper() and isinstance(value, str)
    ]
    assert texts
    for text in texts:
        assert "**" not in text
        assert not text.startswith("#")


def test_macos_help_names_audio_midi_setup_and_both_clock_sources():
    assert "Audio MIDI Setup" in help_text.DIRECT_MODE_MACOS
    assert "Stereo Direct" in help_text.DIRECT_MODE_MACOS
    assert "DSP Clock" in help_text.DIRECT_MODE_MACOS
    # The two things Direct Mode costs you, which is the whole point of asking.
    assert "microphone" in help_text.DIRECT_MODE_MACOS
    assert "SBX" in help_text.DIRECT_MODE_MACOS


def test_macos_direct_mode_help_leads_with_the_conclusion():
    """It must say it does not work before explaining anything else."""
    first = help_text.DIRECT_MODE_MACOS.split("\n")[0]
    assert "does not work on macOS" in first
    # Short enough to read at a glance rather than an essay.
    assert len(help_text.DIRECT_MODE_MACOS) < len(help_text.DIRECT_MODE)


def test_macos_spdif_help_says_untested_rather_than_broken():
    assert "unknown" in help_text.SPDIF_OUT_DIRECT_MACOS
    assert "does not work" not in help_text.SPDIF_OUT_DIRECT_MACOS


def test_direct_mode_is_disabled_where_the_os_overrides_it(controller, monkeypatch):
    monkeypatch.setattr(playback, "DIRECT_MODE_SUPPORTED", False)
    monkeypatch.setattr(playback, "IS_MACOS", True)
    page = playback.build(controller)

    assert page.direct_mode.switch.enabled is False
    # The (i) button must stay usable — that is where the explanation lives.
    assert page.direct_mode.info_button.enabled is True


def test_spdif_out_direct_stays_enabled_on_macos(controller, monkeypatch):
    """Untested is not the same as broken.

    macOS overrides Direct Mode, but its Clock Source has only DSP Clock and
    Stereo Direct — no equivalent of SPDIF-Out Direct. Disabling that switch
    would assert a limitation nobody has demonstrated, and would remove the only
    means of ever testing it.
    """
    monkeypatch.setattr(playback, "DIRECT_MODE_SUPPORTED", False)
    monkeypatch.setattr(playback, "IS_MACOS", True)
    page = playback.build(controller)

    assert page.spdif_direct_mode.switch.enabled is True


def test_direct_mode_switches_are_live_where_the_platform_honours_them(
    controller, monkeypatch
):
    monkeypatch.setattr(playback, "DIRECT_MODE_SUPPORTED", True)
    page = playback.build(controller)
    assert page.direct_mode.switch.enabled is True
    assert page.spdif_direct_mode.switch.enabled is True
