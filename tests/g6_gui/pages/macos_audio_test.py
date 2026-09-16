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
