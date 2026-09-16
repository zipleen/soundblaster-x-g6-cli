"""Unit tests for g6_gui.coreaudio, entirely against FakeHal -- no real Core
Audio device involved. See docs/settings-reference.md and the coreaudio.py
module docstring for what was separately validated live against real Core
Audio devices on the machine this was developed on (a different kind of
validation than these tests, which check decision logic, not the ctypes
plumbing)."""

from __future__ import annotations

import pytest

from g6_gui import coreaudio as ca
from tests.g6_gui.fake_coreaudio import FakeHal


# ── Pure logic ────────────────────────────────────────────────────────────


def test_classify_recognises_exactly_the_two_g6_modes():
    sources = [ca.ClockSource(0, "DSP Clock"), ca.ClockSource(1, "Stereo Direct")]
    assert ca.classify_clock_sources(sources) == {"DSP Clock": 0, "Stereo Direct": 1}


@pytest.mark.parametrize(
    "sources",
    [
        [],
        [ca.ClockSource(0, "DSP Clock")],  # only one of the two
        [ca.ClockSource(0, "DSP Clock"), ca.ClockSource(1, "Stereo Direct"), ca.ClockSource(2, "Optical")],
        [ca.ClockSource(0, "Internal"), ca.ClockSource(1, "External")],  # a different device entirely
    ],
    ids=["empty", "one-only", "extra-source", "unrelated-device"],
)
def test_classify_refuses_anything_that_is_not_exactly_the_two_known_modes(sources):
    """Deliberately conservative: an unfamiliar shape must grey out, not guess."""
    assert ca.classify_clock_sources(sources) is None


def test_filter_stereo_pcm_formats_drops_non_stereo():
    formats = [ca.Format(48000.0, 24, 2), ca.Format(48000.0, 24, 6), ca.Format(48000.0, 24, 1)]
    assert ca.filter_stereo_pcm_formats(formats) == [ca.Format(48000.0, 24, 2)]


def test_needs_safe_handoff_only_above_48khz():
    assert ca.needs_safe_handoff(ca.Format(96000.0, 24, 2)) is True
    assert ca.needs_safe_handoff(ca.Format(384000.0, 32, 2)) is True
    assert ca.needs_safe_handoff(ca.Format(48000.0, 24, 2)) is False
    assert ca.needs_safe_handoff(ca.Format(44100.0, 24, 2)) is False
    assert ca.needs_safe_handoff(None) is False


def test_format_label_is_human_readable():
    assert ca.Format(48000.0, 24, 2).label() == "24-bit / 48 kHz"
    assert ca.Format(384000.0, 32, 2).label() == "32-bit / 384 kHz"


def test_sort_formats_orders_by_rate_then_bits():
    formats = [ca.Format(48000.0, 32, 2), ca.Format(44100.0, 24, 2), ca.Format(48000.0, 24, 2)]
    assert ca.sort_formats(formats) == [
        ca.Format(44100.0, 24, 2), ca.Format(48000.0, 24, 2), ca.Format(48000.0, 32, 2),
    ]


# ── find_g6: identify by capability fingerprint, not by name ────────────────


def test_find_g6_matches_by_clock_source_shape_regardless_of_device_name():
    hal = FakeHal(device_name="Some USB Audio Device")  # deliberately not "G6" anything
    found = ca.find_g6(hal)
    assert found is not None
    device_id, classified = found
    assert device_id == hal.device_id
    assert classified == {"DSP Clock": 0, "Stereo Direct": 1}


def test_find_g6_returns_none_when_no_device_present():
    assert ca.find_g6(FakeHal(present=False)) is None


def test_find_g6_returns_none_when_no_device_has_the_right_clock_sources():
    hal = FakeHal(clock_sources=[ca.ClockSource(0, "Internal"), ca.ClockSource(1, "External")])
    assert ca.find_g6(hal) is None


def test_find_g6_returns_none_when_clock_sources_property_is_absent():
    """The overwhelming majority of audio devices -- including this
    project's own built-in speakers/mic, verified live -- simply do not
    implement this property at all."""
    hal = FakeHal(clock_sources=None)
    assert ca.find_g6(hal) is None


# ── ClockController: refresh() ───────────────────────────────────────────


def test_refresh_reports_not_found_when_absent():
    cc = ca.ClockController(hal=FakeHal(present=False))
    state = cc.refresh()
    assert state.found is False


def test_refresh_reports_not_found_when_clock_sources_do_not_match_the_known_shape():
    """Indistinguishable, by design, from the device being entirely absent --
    see the ClockState docstring for why that is deliberate, not a gap."""
    hal = FakeHal(clock_sources=[ca.ClockSource(0, "Internal"), ca.ClockSource(1, "External")])
    state = ca.ClockController(hal=hal).refresh()
    assert state.found is False


def test_refresh_reports_the_current_clock_source_and_format():
    hal = FakeHal(current_clock_source_code=1, current_format=ca.Format(384000.0, 32, 2))
    state = ca.ClockController(hal=hal).refresh()
    assert state.found is True
    assert state.current_clock_source == "Stereo Direct"
    assert state.current_format == ca.Format(384000.0, 32, 2)


def test_refresh_available_formats_are_filtered_and_sorted():
    hal = FakeHal(
        current_clock_source_code=0,
        formats_by_clock_source={0: [ca.Format(48000.0, 32, 6), ca.Format(44100.0, 24, 2), ca.Format(48000.0, 24, 2)]},
    )
    state = ca.ClockController(hal=hal).refresh()
    assert state.available_formats == (ca.Format(44100.0, 24, 2), ca.Format(48000.0, 24, 2))


# ── ClockController: set_clock_source() ──────────────────────────────────


def test_set_clock_source_switches_and_refreshes():
    hal = FakeHal(current_clock_source_code=0)
    cc = ca.ClockController(hal=hal)
    cc.refresh()
    cc.set_clock_source(ca.STEREO_DIRECT)
    assert cc.state.current_clock_source == "Stereo Direct"


def test_set_clock_source_rejects_an_unknown_name():
    cc = ca.ClockController(hal=FakeHal())
    cc.refresh()
    with pytest.raises(ValueError):
        cc.set_clock_source("Some Other Mode")


def test_set_clock_source_before_refresh_raises_rather_than_guessing():
    with pytest.raises(RuntimeError):
        ca.ClockController(hal=FakeHal()).set_clock_source(ca.DSP_CLOCK)


def test_set_clock_source_raises_when_core_audio_silently_does_not_apply_it(monkeypatch):
    """The exact bug this module must not have: trusting that a call
    succeeded just because it did not raise. Reproduced and fixed against
    real Core Audio (BlackHole) before this test was written -- see
    HANDOFF.md."""
    monkeypatch.setattr(ca, "SETTLE_POLL_ATTEMPTS", 2)  # this test wants the
    # failure path, not the generous real-hardware settle budget -- keeps the
    # suite fast without changing what is being verified.
    hal = FakeHal()
    hal.reject_clock_source_set = True
    cc = ca.ClockController(hal=hal)
    cc.refresh()
    with pytest.raises(TimeoutError):
        cc.set_clock_source(ca.STEREO_DIRECT)


# ── ClockController: the safe-handoff sequence ───────────────────────────
#
# Reproduces, as an automated test, the exact gotcha Luis found by hand:
# switching Stereo Direct (384kHz) -> DSP Clock breaks audio unless the
# format is dropped to something DSP Clock supports first.


def test_switching_to_dsp_clock_from_a_high_rate_drops_the_format_first():
    hal = FakeHal(current_clock_source_code=1, current_format=ca.Format(384000.0, 32, 2))
    cc = ca.ClockController(hal=hal)
    cc.refresh()
    hal.calls.clear()

    cc.set_clock_source(ca.DSP_CLOCK)

    set_format_calls = [c for c in hal.calls if c[0] == "set_format"]
    set_clock_calls = [c for c in hal.calls if c[0] == "set_clock_source_code"]
    assert len(set_format_calls) == 1, "must drop the format before switching clock source"
    assert set_format_calls[0][1]["fmt"].sample_rate <= 48000.0
    # order matters: the format handoff must happen before the clock switch,
    # or the wedge this exists to avoid is not actually avoided
    assert hal.calls.index(set_format_calls[0]) < hal.calls.index(set_clock_calls[0])


def test_switching_to_dsp_clock_from_a_safe_rate_skips_the_handoff():
    hal = FakeHal(current_clock_source_code=1, current_format=ca.Format(44100.0, 24, 2))
    cc = ca.ClockController(hal=hal)
    cc.refresh()
    hal.calls.clear()

    cc.set_clock_source(ca.DSP_CLOCK)

    assert not [c for c in hal.calls if c[0] == "set_format"]


def test_handoff_prefers_48khz_at_whatever_bit_depth_is_actually_offered():
    """Regression: an earlier version hard-required 24-bit specifically and
    fell back to the *lowest available rate* (8kHz on BlackHole, live-tested)
    when 24-bit at 48kHz was not offered. Must prefer any 48kHz format over a
    lower rate."""
    hal = FakeHal(
        current_clock_source_code=1,
        current_format=ca.Format(384000.0, 32, 2),
        formats_by_clock_source={
            0: [ca.Format(44100.0, 24, 2), ca.Format(48000.0, 24, 2)],
            1: [ca.Format(8000.0, 32, 2), ca.Format(48000.0, 32, 2), ca.Format(384000.0, 32, 2)],
        },
    )
    cc = ca.ClockController(hal=hal)
    cc.refresh()
    cc.set_clock_source(ca.DSP_CLOCK)
    # The clock switch itself resets format via FakeHal's own simulation; what
    # matters is the handoff step explicitly chose 48kHz, not 8kHz.
    handoff_calls = [c for c in hal.calls if c[0] == "set_format"]
    assert handoff_calls[0][1]["fmt"].sample_rate == 48000.0


def test_handoff_falls_back_to_lowest_rate_only_when_48khz_is_not_offered_at_all():
    hal = FakeHal(
        current_clock_source_code=1,
        current_format=ca.Format(384000.0, 32, 2),
        formats_by_clock_source={
            0: [ca.Format(44100.0, 24, 2)],
            1: [ca.Format(8000.0, 32, 2), ca.Format(384000.0, 32, 2)],
        },
    )
    cc = ca.ClockController(hal=hal)
    cc.refresh()
    cc.set_clock_source(ca.DSP_CLOCK)
    handoff_calls = [c for c in hal.calls if c[0] == "set_format"]
    assert handoff_calls[0][1]["fmt"].sample_rate == 8000.0


# ── ClockController: set_format() ────────────────────────────────────────


def test_set_format_switches_and_refreshes():
    hal = FakeHal(current_clock_source_code=0)
    cc = ca.ClockController(hal=hal)
    cc.refresh()
    target = ca.Format(48000.0, 32, 2)
    cc.set_format(target)
    assert cc.state.current_format == target


def test_set_format_rejects_a_format_not_currently_offered():
    hal = FakeHal(current_clock_source_code=0)  # 384kHz is only offered under Stereo Direct
    cc = ca.ClockController(hal=hal)
    cc.refresh()
    with pytest.raises(ValueError):
        cc.set_format(ca.Format(384000.0, 32, 2))


def test_set_format_raises_when_core_audio_silently_does_not_apply_it(monkeypatch):
    monkeypatch.setattr(ca, "SETTLE_POLL_ATTEMPTS", 2)
    hal = FakeHal(current_clock_source_code=0)
    hal.reject_format_set = True
    cc = ca.ClockController(hal=hal)
    cc.refresh()
    with pytest.raises(TimeoutError):
        cc.set_format(ca.Format(48000.0, 32, 2))


# ── Defensive against Core Audio simply not being present ───────────────────
#
# There is no Linux equivalent of this tab (is_available() gates it to
# IS_MACOS), but pages_contract_test.py builds every page unconditionally
# regardless of platform, and ClockController() must not crash outright when
# constructed on a machine without Core Audio at all.


def test_constructing_a_clock_controller_never_touches_core_audio_eagerly(monkeypatch):
    """Real Hal construction is deferred to refresh() -- merely creating a
    ClockController() must not attempt to load CoreAudio.framework."""
    def boom():
        raise AssertionError("_CoreAudioHal constructed eagerly, should be lazy")

    monkeypatch.setattr(ca, "_CoreAudioHal", boom)
    ca.ClockController()  # must not raise


def test_refresh_degrades_to_not_found_when_core_audio_is_unavailable(monkeypatch):
    """Simulates running on a platform without Core Audio at all (or any
    other reason the real Hal fails to construct) -- refresh() must report
    not-found, never raise."""
    def boom():
        raise OSError("dlopen(CoreAudio) failed")

    monkeypatch.setattr(ca, "_CoreAudioHal", boom)
    cc = ca.ClockController()
    state = cc.refresh()
    assert state.found is False


def test_refresh_survives_a_hal_call_raising_mid_read():
    class FlakyHal(FakeHal):
        def output_streams(self, device_id):
            raise OSError("device vanished mid-read")

    cc = ca.ClockController(hal=FlakyHal())
    state = cc.refresh()
    assert state.found is False


# ── Regression: exclusive-mode ("Non-Mixable") formats must not collapse ────
#
# Confirmed live against a real G6: its available-formats list contains two
# full sets of every (rate, bits, channels) combination, differing only in
# kAudioFormatFlagIsNonMixable -- an ordinary shareable variant and an
# exclusive-mode one that bypasses Core Audio's mixer. Format previously
# ignored this entirely, so the two compared equal, the dropdown showed
# visually identical duplicate entries, and selecting the second of a pair
# always resolved back to the first (via `next(...)` lookup by label) --
# meaning it silently did nothing.


def test_mixable_and_non_mixable_formats_are_distinct():
    a = ca.Format(48000.0, 24, 2, non_mixable=False)
    b = ca.Format(48000.0, 24, 2, non_mixable=True)
    assert a != b
    assert a.label() != b.label()
    assert "Exclusive" in b.label()
    assert "Exclusive" not in a.label()


def test_filter_and_sort_keep_both_variants_with_the_shareable_one_first():
    formats = [
        ca.Format(48000.0, 24, 2, non_mixable=True),
        ca.Format(48000.0, 24, 2, non_mixable=False),
    ]
    result = ca.sort_formats(ca.filter_stereo_pcm_formats(formats))
    assert len(result) == 2
    assert result[0].non_mixable is False
    assert result[1].non_mixable is True


def test_hal_reads_the_non_mixable_flag_from_a_real_style_asbd():
    """Exercises the actual bit test against the exact flag value observed
    live on the G6 (0x4c = signed int + packed + non-mixable)."""
    hal = ca._CoreAudioHal.__new__(ca._CoreAudioHal)  # skip framework loading

    class FakeASBD:
        mSampleRate = 48000.0
        mBitsPerChannel = 24
        mChannelsPerFrame = 2
        mFormatFlags = 0x4C

    fmt = hal._asbd_to_format(FakeASBD())
    assert fmt.non_mixable is True

    FakeASBD.mFormatFlags = 0x0C
    fmt2 = hal._asbd_to_format(FakeASBD())
    assert fmt2.non_mixable is False


# ── Regression: available_formats lags behind a clock source switch ─────────
#
# Confirmed live against a real G6: current_clock_source_code flips in
# ~20ms, but the stream's available-format list kept reporting the
# *previous* clock source's list (32 entries) for roughly 100-200ms before
# settling to the real new one (8 entries, correctly capped at 48kHz for DSP
# Clock). set_clock_source() must not return with a stale format list.


def test_set_clock_source_waits_for_the_format_list_to_actually_change():
    hal = FakeHal(current_clock_source_code=1)  # Stereo Direct, 5 formats
    hal.format_settle_delay_reads = 3  # a few stale reads before it catches up
    cc = ca.ClockController(hal=hal)
    cc.refresh()

    cc.set_clock_source(ca.DSP_CLOCK)

    # Must reflect DSP Clock's own list (3 entries in the default fixture),
    # not Stereo Direct's stale one (5 entries) that a naive single refresh
    # right after the clock-source predicate settles would have returned.
    assert cc.state.available_formats == tuple(ca.sort_formats(hal.formats_by_code[0]))
