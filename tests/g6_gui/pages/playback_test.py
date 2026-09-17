from __future__ import annotations

import pytest

from g6_cli.g6_spec import PlaybackFilter
from g6_cli.g6_spec.decoder import DecoderMode
from g6_gui import help as help_text
from g6_gui.controller import G6Controller
from g6_gui.filters import NON_OVERSAMPLING
from g6_gui.pages import playback
from tests.g6_gui.fake_api import FakeG6Api


@pytest.fixture
def built():
    api = FakeG6Api()
    controller = G6Controller(api)
    content = playback.build(controller)
    yield api, controller, content
    controller.shutdown()


async def test_selecting_headphones_toggles_output(built):
    api, controller, content = built
    content.output.selection.value = "Headphones"
    await controller.flush()
    assert api.method_names() == ["playback_toggle_to_headphones"]


async def test_selecting_speakers_toggles_output(built):
    api, controller, content = built
    content.output.selection.value = "Headphones"
    content.output.selection.value = "Speakers"
    await controller.flush()
    assert api.method_names()[-1] == "playback_toggle_to_speakers"


async def test_direct_mode_switch(built):
    api, controller, content = built
    content.direct_mode.switch.value = True
    await controller.flush()
    assert api.calls == [("playback_enable_direct_mode", {"enable": True})]


async def test_spdif_direct_mode_switch(built):
    api, controller, content = built
    content.spdif_direct_mode.switch.value = True
    await controller.flush()
    assert api.calls == [("playback_enable_spdif_out_direct_mode", {"enable": True})]


async def test_filter_selection_sends_the_enum(built):
    api, controller, content = built
    content.filter.selection.value = "Slow Roll Off - Linear Phase"
    await controller.flush()
    assert api.calls == [
        ("playback_filter", {"playback_filter_enum": PlaybackFilter.SLOW_ROLL_OFF_LINEAR_PHASE})
    ]


@pytest.mark.parametrize(
    "label,expected_enum",
    [
        ("Fast Roll Off - Minimum Phase", PlaybackFilter.FAST_ROLL_OFF_MINIMUM_PHASE),
        ("Slow Roll Off - Minimum Phase", PlaybackFilter.SLOW_ROLL_OFF_MINIMUM_PHASE),
        ("Fast Roll Off - Linear Phase", PlaybackFilter.FAST_ROLL_OFF_LINEAR_PHASE),
        ("Slow Roll Off - Linear Phase", PlaybackFilter.SLOW_ROLL_OFF_LINEAR_PHASE),
    ],
)
async def test_the_four_original_filters_are_unchanged(built, label, expected_enum):
    api, controller, content = built
    content.filter.selection.value = label
    await controller.flush()
    assert api.calls == [("playback_filter", {"playback_filter_enum": expected_enum})]
    # None of the four Creative-supported filters should ever show the NOS
    # warning.
    assert content.filter_warning.lines == []


async def test_selecting_nos_sends_the_documented_wire_payload(built):
    api, controller, content = built
    content.filter.selection.value = "Non-Over-Sampling (NOS)"
    await controller.flush()
    assert api.calls == [
        ("playback_filter", {"playback_filter_enum": NON_OVERSAMPLING})
    ]
    sent = api.calls[0][1]["playback_filter_enum"]
    # The actual bytes fw_notes.md's "DAC FILTERS -- full decode" documents
    # for NOS (SoundCore code 5, wire payload = code - 2 = 0003).
    assert sent.value == bytes.fromhex("0003")


def test_filter_warning_is_hidden_for_the_default_filter(built):
    _, _, content = built
    assert content.filter_warning.lines == []


async def test_selecting_nos_shows_the_warning_and_switching_away_hides_it(built):
    # Regression test for the warning wiring itself (HANDOFF.md gotcha 13:
    # a test that passes whether or not the feature works is worthless). If
    # the ``filter_warning.set_text(...)`` call were deleted from
    # ``_on_filter_change``, ``content.filter_warning.lines`` would stay
    # ``[]`` after selecting NOS and this would fail on the first assert. If
    # the warning were shown unconditionally instead of only for NOS, it
    # would still be present after switching back to a normal filter and
    # this would fail on the second assert.
    api, controller, content = built
    content.filter.selection.value = "Non-Over-Sampling (NOS)"
    await controller.flush()
    assert content.filter_warning.lines != []
    assert "Non-Over-Sampling is selected" in " ".join(content.filter_warning.lines)

    content.filter.selection.value = "Fast Roll Off - Minimum Phase"
    await controller.flush()
    assert content.filter_warning.lines == []


async def test_selecting_nos_does_not_revert_even_though_the_model_rejects_it(built):
    # Drives the tolerate path through something that actually raises --
    # standing in for G6Model.set_filter()'s isinstance check rejecting the
    # NOS shim with a ValueError, which G6Api.playback_filter() only reaches
    # *after* writing the correct bytes to the wire (see filters.py's
    # docstring for the full chain). A double that silently accepted the
    # shim would pass this test whether or not `tolerate` were wired up
    # (HANDOFF.md gotcha 13); forcing a real raise means it only passes if
    # `tolerate=(ValueError,)` is actually threaded through to submit().
    api, controller, content = built
    api.fail_next(ValueError("playback_filter_enum must be PlaybackFilter"))
    content.filter.selection.value = "Non-Over-Sampling (NOS)"
    await controller.flush()
    assert content.filter.selection.value == "Non-Over-Sampling (NOS)"
    assert content.filter_warning.lines != []


async def test_selecting_a_normal_filter_still_reverts_on_a_genuine_failure(built):
    api, controller, content = built
    starting_label = content.filter.selection.value
    api.fail_next(ValueError("genuinely rejected"))
    content.filter.selection.value = "Slow Roll Off - Linear Phase"
    await controller.flush()
    assert content.filter.selection.value == starting_label
    assert content.filter_warning.lines == []


async def test_decoder_selection_sends_the_enum(built):
    api, controller, content = built
    content.decoder.selection.value = "Night"
    await controller.flush()
    assert api.calls == [("decoder_mode", {"decoder_mode_enum": DecoderMode.NIGHT})]


def test_audio_controls_are_absent_on_macos(monkeypatch):
    monkeypatch.setattr("g6_gui.pages.playback.AUDIO_INTERFACE_SUPPORTED", False)
    controller = G6Controller(FakeG6Api())
    content = playback.build(controller)
    assert not hasattr(content, "volume")
    assert not hasattr(content, "mute")
    controller.shutdown()


def test_audio_controls_exist_but_start_disabled_on_linux(monkeypatch):
    monkeypatch.setattr("g6_gui.pages.playback.AUDIO_INTERFACE_SUPPORTED", True)
    controller = G6Controller(FakeG6Api())
    content = playback.build(controller)
    assert content.volume.slider.enabled is False
    controller.shutdown()


async def test_volume_is_debounced_into_one_write(monkeypatch):
    monkeypatch.setattr("g6_gui.pages.playback.AUDIO_INTERFACE_SUPPORTED", True)
    api = FakeG6Api()
    controller = G6Controller(api)
    content = playback.build(controller)
    for value in (10, 20, 30):
        content.volume.slider.value = value
    await controller.flush()
    assert len(api.calls) == 1
    assert api.calls[0][0] == "playback_volume"
    assert api.calls[0][1]["volume_percent"] == 30
    controller.shutdown()
