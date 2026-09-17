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


# ── is_full_scale_volume ─────────────────────────────────────────────────


def test_is_full_scale_volume_true_at_and_above_the_threshold():
    assert ca.is_full_scale_volume(1.0) is True
    assert ca.is_full_scale_volume(ca.FULL_SCALE_VOLUME_THRESHOLD) is True
    assert ca.is_full_scale_volume(0.995) is True


def test_is_full_scale_volume_false_below_the_threshold():
    assert ca.is_full_scale_volume(0.98) is False
    assert ca.is_full_scale_volume(0.9) is False
    assert ca.is_full_scale_volume(0.0) is False


def test_is_full_scale_volume_false_when_no_host_settable_volume_exists():
    """None -- not a low number -- must never read as "full scale"."""
    assert ca.is_full_scale_volume(None) is False


# ── is_full_scale_volume: dB-preferred decision (task: a scalar-only
# threshold misses the top steps a dB reading can see -- see
# FULL_SCALE_VOLUME_DB_THRESHOLD's comment for the full reasoning) ──────────


def test_is_full_scale_volume_true_above_the_db_threshold():
    assert ca.is_full_scale_volume(0.5, -1.0) is True  # above -2.0 dBFS
    assert ca.is_full_scale_volume(0.5, 0.0) is True


def test_is_full_scale_volume_false_at_or_below_the_db_threshold():
    assert ca.is_full_scale_volume(0.99, ca.FULL_SCALE_VOLUME_DB_THRESHOLD) is False
    assert ca.is_full_scale_volume(0.99, -5.0) is False


def test_is_full_scale_volume_db_reading_overrides_a_disagreeing_scalar():
    """The exact case a scalar-only threshold cannot see: a low-looking
    scalar step that is nonetheless within 2 dB of full scale must still
    warn, and a scalar reading that clears the old >=0.99 bar must NOT warn
    once the dB reading shows it is well clear of -2 dBFS. If the dB branch
    in is_full_scale_volume() were ever deleted (falling through to the
    scalar unconditionally), both assertions below would flip and fail --
    that is deliberate; this is the regression test for the dB path
    existing at all, not just for its default-None fallback behaviour."""
    assert ca.is_full_scale_volume(0.5, -1.0) is True  # scalar alone: False
    assert ca.is_full_scale_volume(1.0, -10.0) is False  # scalar alone: True


def test_is_full_scale_volume_falls_back_to_scalar_when_db_is_unavailable():
    assert ca.is_full_scale_volume(1.0, None) is True
    assert ca.is_full_scale_volume(0.9, None) is False


def test_is_full_scale_volume_false_when_both_readings_are_unavailable():
    assert ca.is_full_scale_volume(None, None) is False


# ── has_non_stereo_formats ────────────────────────────────────────────────


def test_has_non_stereo_formats_true_when_present():
    formats = [ca.Format(48000.0, 24, 2), ca.Format(48000.0, 24, 6)]
    assert ca.has_non_stereo_formats(formats) is True


def test_has_non_stereo_formats_false_when_all_stereo():
    formats = [ca.Format(44100.0, 24, 2), ca.Format(48000.0, 24, 2)]
    assert ca.has_non_stereo_formats(formats) is False


def test_has_non_stereo_formats_false_for_an_empty_list():
    assert ca.has_non_stereo_formats([]) is False


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


# ── ClockController: output_volume ───────────────────────────────────────


def test_refresh_reports_the_output_volume_when_present():
    hal = FakeHal(current_clock_source_code=0, output_volume=0.62)
    state = ca.ClockController(hal=hal).refresh()
    assert state.output_volume == 0.62


def test_refresh_reports_none_when_no_host_settable_volume_exists():
    """A real, distinct case -- must not be reported as 0.0."""
    hal = FakeHal(current_clock_source_code=0, output_volume=None)
    state = ca.ClockController(hal=hal).refresh()
    assert state.output_volume is None


def test_refresh_reports_a_full_scale_volume_reading():
    hal = FakeHal(current_clock_source_code=0, output_volume=1.0)
    state = ca.ClockController(hal=hal).refresh()
    assert ca.is_full_scale_volume(state.output_volume) is True


def test_refresh_reports_a_below_full_scale_volume_reading():
    hal = FakeHal(current_clock_source_code=0, output_volume=0.9)
    state = ca.ClockController(hal=hal).refresh()
    assert ca.is_full_scale_volume(state.output_volume) is False


def test_refresh_does_not_populate_volume_when_device_not_found():
    hal = FakeHal(present=False, output_volume=1.0)
    state = ca.ClockController(hal=hal).refresh()
    assert state.found is False
    assert state.output_volume is None


# ── ClockController: output_volume_db ────────────────────────────────────


def test_refresh_reports_the_output_volume_db_when_present():
    hal = FakeHal(current_clock_source_code=0, output_volume_db=-1.5)
    state = ca.ClockController(hal=hal).refresh()
    assert state.output_volume_db == -1.5


def test_refresh_reports_none_db_when_vold_is_unreachable():
    """The unverified-per-channel case this pass could not settle (see
    coreaudio.py's module docstring) -- must read as a real absence, not 0 dB."""
    hal = FakeHal(current_clock_source_code=0, output_volume_db=None)
    state = ca.ClockController(hal=hal).refresh()
    assert state.output_volume_db is None


def test_refresh_does_not_populate_volume_db_when_device_not_found():
    hal = FakeHal(present=False, output_volume_db=-1.0)
    state = ca.ClockController(hal=hal).refresh()
    assert state.found is False
    assert state.output_volume_db is None


def test_refresh_prefers_db_for_the_full_scale_decision_when_both_are_present():
    """End-to-end version of the pure-function test above, through refresh():
    a scalar that alone would not warn, paired with a dB reading that is
    within 2 dB of full scale, must still warn once both are wired through
    ClockState -- this is what would actually regress in the app if the dB
    field were read but never threaded into the decision."""
    hal = FakeHal(current_clock_source_code=0, output_volume=0.5, output_volume_db=-1.0)
    state = ca.ClockController(hal=hal).refresh()
    assert ca.is_full_scale_volume(state.output_volume, state.output_volume_db) is True


# ── ClockController: channel count / non-stereo reality check ───────────────


def test_refresh_reports_the_current_output_channel_count():
    hal = FakeHal(current_clock_source_code=0, current_format=ca.Format(48000.0, 24, 2))
    state = ca.ClockController(hal=hal).refresh()
    assert state.output_channels == 2


def test_refresh_reports_no_non_stereo_formats_when_only_stereo_is_offered():
    hal = FakeHal(
        current_clock_source_code=0,
        formats_by_clock_source={0: [ca.Format(44100.0, 24, 2), ca.Format(48000.0, 24, 2)]},
    )
    state = ca.ClockController(hal=hal).refresh()
    assert state.non_stereo_formats_available is False


def test_refresh_reports_non_stereo_formats_when_present_without_changing_the_dropdown_list():
    """The reality-check fields must not change filter_stereo_pcm_formats()'s
    own behaviour -- the Format dropdown stays stereo-only regardless."""
    hal = FakeHal(
        current_clock_source_code=0,
        current_format=ca.Format(48000.0, 24, 2),
        formats_by_clock_source={
            0: [ca.Format(44100.0, 24, 2), ca.Format(48000.0, 24, 2), ca.Format(48000.0, 24, 6)],
        },
    )
    state = ca.ClockController(hal=hal).refresh()
    assert state.non_stereo_formats_available is True
    assert state.output_channels == 2
    assert all(f.channels == 2 for f in state.available_formats)


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


# ── _CoreAudioHal.output_volume()/output_volume_db(): the real G6's
# confirmed property shape ───────────────────────────────────────────────
#
# experimental/verify-coreaudio-volume.py against a real G6 (device 50, clock
# sources DSP Clock / Stereo Direct) found: no 'vmvc', no master-element
# 'volm' -- but 'volm' IS implemented on channels 1 and 2. These tests script
# _has()/_get_raw() directly (same "skip framework loading" trick as
# test_hal_reads_the_non_mixable_flag_from_a_real_style_asbd above) to prove
# output_volume()'s element-fallback chain actually produces a reading
# against exactly that shape, not just against FakeHal's simplified
# single-value model (FakeHal has no concept of "which Core Audio element" --
# that fallback logic lives entirely inside _CoreAudioHal).


def _scripted_hal(properties: dict) -> ca._CoreAudioHal:
    """A _CoreAudioHal with framework loading skipped and _has()/_get_raw()
    scripted from a ``{(selector, scope, element): float_value}`` map. Any
    (selector, scope, element) not in the map reads as "not implemented" --
    mirrors AudioObjectHasProperty returning false for a property Core Audio
    genuinely does not have.
    """
    import ctypes

    hal = ca._CoreAudioHal.__new__(ca._CoreAudioHal)
    hal.k_scope_global = ca._CoreAudioHal._fourcc("glob")
    hal.k_scope_output = ca._CoreAudioHal._fourcc("outp")
    hal.k_element_main = 0
    hal.k_virtual_main_volume = ca._CoreAudioHal._fourcc("vmvc")
    hal.k_volume_scalar = ca._CoreAudioHal._fourcc("volm")
    hal.k_volume_decibels = ca._CoreAudioHal._fourcc("vold")

    def _has(obj_id, selector, scope=None, element=None):
        return (selector, scope, element) in properties

    def _get_raw(obj_id, selector, size, scope=None, element=None):
        return bytes(ctypes.c_float(properties[(selector, scope, element)]))

    hal._has = _has
    hal._get_raw = _get_raw
    return hal


def test_output_volume_falls_through_vmvc_and_master_volm_to_the_per_channel_reading():
    """The real G6's confirmed shape: no 'vmvc', no master 'volm' -- reading
    must still succeed via channel 1."""
    hal = _scripted_hal({
        (ca._CoreAudioHal._fourcc("volm"), ca._CoreAudioHal._fourcc("outp"), 1): 0.5625,
    })
    assert hal.output_volume(device_id=50) == pytest.approx(0.5625)


def test_output_volume_returns_none_when_the_g6_shape_has_no_reading_anywhere():
    hal = _scripted_hal({})  # vmvc absent, volm absent on every element
    assert hal.output_volume(device_id=50) is None


def test_output_volume_db_mirrors_the_same_element_fallback():
    """Task 1's open question, exercised at the level this module can
    actually test without a device attached: IF the G6 implements 'vold' on
    channel 2 the same way it implements 'volm' there, output_volume_db()
    finds it there too. Whether the G6 actually does is exactly what
    experimental/verify-coreaudio-volume.py's extended probe (task 2) still needs
    to confirm -- see the module docstring's "Still NOT validated" note."""
    hal = _scripted_hal({
        (ca._CoreAudioHal._fourcc("vold"), ca._CoreAudioHal._fourcc("outp"), 2): -1.5,
    })
    assert hal.output_volume_db(device_id=50) == pytest.approx(-1.5)


def test_output_volume_db_returns_none_when_vold_is_absent_everywhere():
    """The other real possibility this pass could not rule out: 'vold' simply
    is not implemented at all, even where 'volm' is. Must read as absence,
    not 0 dB."""
    hal = _scripted_hal({
        (ca._CoreAudioHal._fourcc("volm"), ca._CoreAudioHal._fourcc("outp"), 1): 0.5625,
    })
    assert hal.output_volume_db(device_id=50) is None


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
