"""macOS Audio page, entirely against FakeHal -- no real Core Audio device."""

from __future__ import annotations

import pytest

from g6_gui import coreaudio as ca
from g6_gui.controller import G6Controller
from g6_gui.pages import macos_audio
from tests.g6_gui.fake_api import FakeG6Api
from tests.g6_gui.fake_coreaudio import FakeHal


@pytest.fixture
def controller():
    controller = G6Controller(FakeG6Api())
    yield controller
    controller.shutdown()


def _inject(monkeypatch, hal: FakeHal) -> ca.ClockController:
    cc = ca.ClockController(hal=hal)
    monkeypatch.setattr(macos_audio, "_make_clock_controller", lambda: cc)
    return cc


def test_is_available_follows_the_platform_flag(monkeypatch):
    monkeypatch.setattr(macos_audio, "IS_MACOS", True)
    assert macos_audio.is_available() is True
    monkeypatch.setattr(macos_audio, "IS_MACOS", False)
    assert macos_audio.is_available() is False


def test_build_works_when_called_plain_per_the_page_contract(controller, monkeypatch):
    """Every other page in this app can be built with just build(controller);
    this one must too, even though it also accepts an optional callback."""
    _inject(monkeypatch, FakeHal())
    content = macos_audio.build(controller)
    assert content is not None


def test_found_device_shows_current_clock_source_and_formats(controller, monkeypatch):
    hal = FakeHal(current_clock_source_code=0, current_format=ca.Format(48000.0, 24, 2))
    _inject(monkeypatch, hal)
    page = macos_audio.build(controller)

    assert page.clock_source.selection.value == "DSP Clock"
    assert page.clock_source.selection.enabled is True
    assert "48" in page.format.selection.value
    assert "Current: DSP Clock" in " ".join(page.status.lines)


def test_device_not_found_disables_everything_and_explains_why(controller, monkeypatch):
    _inject(monkeypatch, FakeHal(present=False))
    page = macos_audio.build(controller)

    assert page.clock_source.selection.enabled is False
    assert page.format.selection.enabled is False
    assert "Could not identify" in " ".join(page.status.lines)


def test_unrecognised_clock_sources_are_treated_the_same_as_not_found(controller, monkeypatch):
    """The page must not claim a diagnosis it cannot actually make -- see the
    ClockState docstring in coreaudio.py for why "found but unsupported" is
    not a real, distinguishable state under fingerprint identification."""
    hal = FakeHal(clock_sources=[ca.ClockSource(0, "Internal"), ca.ClockSource(1, "External")])
    _inject(monkeypatch, hal)
    page = macos_audio.build(controller)
    assert page.clock_source.selection.enabled is False


def test_selecting_a_clock_source_calls_the_callback(controller, monkeypatch):
    hal = FakeHal(current_clock_source_code=0)
    _inject(monkeypatch, hal)
    seen = []
    page = macos_audio.build(controller, on_clock_source_changed=seen.append)
    seen.clear()  # drop the initial call made during build()

    page.clock_source.selection.value = "Stereo Direct"

    assert seen == ["Stereo Direct"]
    assert hal.current_code == 1


def test_switching_to_dsp_clock_from_a_high_rate_triggers_the_safe_handoff(controller, monkeypatch):
    hal = FakeHal(
        current_clock_source_code=1,
        current_format=ca.Format(384000.0, 32, 2),
        formats_by_clock_source={
            0: [ca.Format(44100.0, 24, 2), ca.Format(48000.0, 24, 2)],
            1: [ca.Format(48000.0, 32, 2), ca.Format(384000.0, 32, 2)],
        },
    )
    _inject(monkeypatch, hal)
    page = macos_audio.build(controller)

    page.clock_source.selection.value = "DSP Clock"

    assert any(name == "set_format" for name, _ in hal.calls)
    assert hal.current_code == 0


def test_a_rejected_switch_shows_an_error_rather_than_pretending_it_worked(controller, monkeypatch):
    monkeypatch.setattr(ca, "SETTLE_POLL_ATTEMPTS", 2)  # keep the suite fast; see coreaudio_test.py
    hal = FakeHal(current_clock_source_code=0)
    hal.reject_clock_source_set = True
    _inject(monkeypatch, hal)
    page = macos_audio.build(controller)

    page.clock_source.selection.value = "Stereo Direct"

    assert "Could not switch" in " ".join(page.status.lines)
    # and it must reflect the *real* state, not the attempted one
    assert page.clock_source.selection.value == "DSP Clock"


def test_refresh_button_re_reads_state(controller, monkeypatch):
    hal = FakeHal(current_clock_source_code=0)
    _inject(monkeypatch, hal)
    page = macos_audio.build(controller)

    # Something external changes the device's state (e.g. the real Audio MIDI
    # Setup app, used directly, outside of this one).
    hal.current_code = 1

    page.refresh_button.on_press()

    assert page.clock_source.selection.value == "Stereo Direct"


def test_status_includes_the_current_format(controller, monkeypatch):
    hal = FakeHal(current_clock_source_code=0, current_format=ca.Format(48000.0, 24, 2))
    _inject(monkeypatch, hal)
    page = macos_audio.build(controller)

    text = " ".join(page.status.lines)
    assert "DSP Clock" in text
    assert "24-bit" in text and "48" in text


# ── Output volume ─────────────────────────────────────────────────────────


def test_volume_is_shown_when_present(controller, monkeypatch):
    hal = FakeHal(current_clock_source_code=0, output_volume=0.5)
    _inject(monkeypatch, hal)
    page = macos_audio.build(controller)

    text = " ".join(page.volume_note.lines)
    assert "50" in text
    assert " ".join(page.volume_warning.lines) == ""


def test_volume_absent_is_reported_distinctly_from_zero(controller, monkeypatch):
    hal = FakeHal(current_clock_source_code=0, output_volume=None)
    _inject(monkeypatch, hal)
    page = macos_audio.build(controller)

    text = " ".join(page.volume_note.lines)
    assert "0%" not in text
    assert "not reported" in text.lower()


def test_volume_at_full_scale_shows_the_distortion_warning(controller, monkeypatch):
    hal = FakeHal(current_clock_source_code=0, output_volume=1.0)
    _inject(monkeypatch, hal)
    page = macos_audio.build(controller)

    assert "100" in " ".join(page.volume_note.lines)
    assert "distort" in " ".join(page.volume_warning.lines).lower()


def test_volume_below_full_scale_hides_the_warning(controller, monkeypatch):
    hal = FakeHal(current_clock_source_code=0, output_volume=0.9)
    _inject(monkeypatch, hal)
    page = macos_audio.build(controller)

    assert " ".join(page.volume_warning.lines) == ""


def test_volume_and_channels_are_cleared_when_device_not_found(controller, monkeypatch):
    _inject(monkeypatch, FakeHal(present=False))
    page = macos_audio.build(controller)

    assert " ".join(page.volume_note.lines) == ""
    assert " ".join(page.volume_warning.lines) == ""
    assert " ".join(page.channels_note.lines) == ""


def test_refresh_button_re_reads_the_volume(controller, monkeypatch):
    hal = FakeHal(current_clock_source_code=0, output_volume=0.5)
    _inject(monkeypatch, hal)
    page = macos_audio.build(controller)

    # Something external changes the volume (e.g. the menu bar slider, used
    # directly, outside of this app).
    hal.output_volume_value = 1.0

    page.refresh_button.on_press()

    assert "100" in " ".join(page.volume_note.lines)
    assert "distort" in " ".join(page.volume_warning.lines).lower()


# ── Output volume: dB-preferred warning (task 1) ─────────────────────────


def test_volume_note_includes_db_when_available(controller, monkeypatch):
    hal = FakeHal(current_clock_source_code=0, output_volume=0.5625, output_volume_db=-1.5)
    _inject(monkeypatch, hal)
    page = macos_audio.build(controller)

    text = " ".join(page.volume_note.lines)
    assert "56" in text
    assert "-1.5" in text and "dB" in text


def test_volume_note_omits_db_when_unavailable(controller, monkeypatch):
    hal = FakeHal(current_clock_source_code=0, output_volume=0.5, output_volume_db=None)
    _inject(monkeypatch, hal)
    page = macos_audio.build(controller)

    text = " ".join(page.volume_note.lines)
    assert "dB" not in text


def test_warning_fires_from_db_even_when_the_scalar_alone_would_not_warn(controller, monkeypatch):
    """The whole point of task 1: a scalar reading well under the old 0.99
    bar can still be within ASR's -2 dBFS window on this non-linear control.
    Reproduces the measured 'Mac mini Speakers' mapping style (a mid-range
    scalar corresponding to a high dB) at a value close enough to the
    threshold to matter."""
    hal = FakeHal(current_clock_source_code=0, output_volume=0.6933, output_volume_db=-1.0)
    _inject(monkeypatch, hal)
    page = macos_audio.build(controller)

    assert "distort" in " ".join(page.volume_warning.lines).lower()


def test_warning_stays_silent_from_db_even_when_the_scalar_alone_would_warn(controller, monkeypatch):
    """The other direction of the same fix: a scalar at the old full-scale
    bar (>=0.99) must NOT warn once the dB reading shows real headroom --
    trusting the finer instrument over the coarse one both ways."""
    hal = FakeHal(current_clock_source_code=0, output_volume=1.0, output_volume_db=-10.0)
    _inject(monkeypatch, hal)
    page = macos_audio.build(controller)

    assert " ".join(page.volume_warning.lines) == ""


def test_warning_falls_back_to_the_scalar_when_db_is_unavailable(controller, monkeypatch):
    hal = FakeHal(current_clock_source_code=0, output_volume=1.0, output_volume_db=None)
    _inject(monkeypatch, hal)
    page = macos_audio.build(controller)

    assert "distort" in " ".join(page.volume_warning.lines).lower()


# ── Channel count / non-stereo reality check ─────────────────────────────


def test_channels_shows_the_expected_stereo_count(controller, monkeypatch):
    hal = FakeHal(current_clock_source_code=0, current_format=ca.Format(48000.0, 24, 2))
    _inject(monkeypatch, hal)
    page = macos_audio.build(controller)

    assert "2" in " ".join(page.channels_note.lines)


def test_channels_notes_when_a_non_stereo_format_is_also_offered(controller, monkeypatch):
    hal = FakeHal(
        current_clock_source_code=0,
        current_format=ca.Format(48000.0, 24, 2),
        formats_by_clock_source={
            0: [ca.Format(44100.0, 24, 2), ca.Format(48000.0, 24, 2), ca.Format(48000.0, 24, 6)],
        },
    )
    _inject(monkeypatch, hal)
    page = macos_audio.build(controller)

    text = " ".join(page.channels_note.lines)
    assert "2" in text
    assert "non-stereo" in text.lower()
    # The format dropdown itself must stay stereo-only regardless -- the
    # 6-channel entry above must not have made it into the offered formats.
    assert len(page.format.selection.items) == 2


def test_duplicate_looking_formats_are_both_genuinely_selectable(controller, monkeypatch):
    """Regression for the exclusive-mode duplicate bug: two entries with the
    same rate/bits but different mixability must both be present, distinct,
    and each individually selectable -- not just the first of the pair."""
    hal = FakeHal(
        current_clock_source_code=0,
        current_format=ca.Format(48000.0, 24, 2, non_mixable=False),
        formats_by_clock_source={
            0: [
                ca.Format(48000.0, 24, 2, non_mixable=False),
                ca.Format(48000.0, 24, 2, non_mixable=True),
            ],
        },
    )
    _inject(monkeypatch, hal)
    page = macos_audio.build(controller)

    labels = [row.value for row in page.format.selection.items]
    assert len(labels) == len(set(labels)) == 2  # no visually identical entries

    exclusive_label = next(lb for lb in labels if "Exclusive" in lb)
    page.format.selection.value = exclusive_label

    assert hal.current_format_value.non_mixable is True
