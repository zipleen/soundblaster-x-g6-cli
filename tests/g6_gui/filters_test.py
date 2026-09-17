from __future__ import annotations

from g6_cli.g6_spec import PlaybackFilter
from g6_gui import filters


def test_nos_payload_is_the_documented_wire_value():
    # docs/g6-re/docs/fw_notes.md "DAC FILTERS -- full decode": SoundCore
    # code 5 (NonOverSampling) minus 2 == wire payload 0003.
    assert filters.NON_OVERSAMPLING.value == bytes.fromhex("0003")
    assert filters.NOS_PAYLOAD == bytes.fromhex("0003")


def test_nos_is_not_a_playback_filter_member():
    # It must not be, and cannot be -- PlaybackFilter lives in the frozen
    # src/g6_cli mirror (HANDOFF.md §2).
    assert not isinstance(filters.NON_OVERSAMPLING, PlaybackFilter)
    assert filters.NON_OVERSAMPLING not in list(PlaybackFilter)


def test_nos_is_a_stable_singleton():
    from g6_gui.filters import NON_OVERSAMPLING as again

    assert filters.NON_OVERSAMPLING is again
