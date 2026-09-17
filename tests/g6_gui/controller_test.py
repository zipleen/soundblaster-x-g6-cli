from __future__ import annotations

import asyncio

import pytest

from g6_gui.controller import G6Controller
from tests.g6_gui.fake_api import FakeG6Api


@pytest.mark.asyncio
async def test_call_reaches_the_api_with_keywords():
    api = FakeG6Api()
    controller = G6Controller(api)
    await controller.call("playback_enable_direct_mode", enable=True)
    assert api.calls == [("playback_enable_direct_mode", {"enable": True})]
    controller.shutdown()


@pytest.mark.asyncio
async def test_submit_is_non_blocking_and_eventually_calls():
    api = FakeG6Api()
    controller = G6Controller(api)
    controller.submit("decoder_mode", decoder_mode_enum="NIGHT")
    await controller.flush()
    assert api.method_names() == ["decoder_mode"]
    controller.shutdown()


@pytest.mark.asyncio
async def test_debounce_coalesces_rapid_changes_into_the_last_value():
    api = FakeG6Api()
    controller = G6Controller(api)
    for value in (10, 20, 30, 40, 50):
        controller.debounced("vol", "playback_volume", delay=0.05, volume_percent=value)
    await controller.flush()
    assert api.calls == [("playback_volume", {"volume_percent": 50})]
    controller.shutdown()


@pytest.mark.asyncio
async def test_debounce_keys_are_independent():
    api = FakeG6Api()
    controller = G6Controller(api)
    controller.debounced("a", "playback_volume", delay=0.05, volume_percent=1)
    controller.debounced("b", "recording_mic_boost", delay=0.05, decibel=10)
    await controller.flush()
    assert sorted(api.method_names()) == ["playback_volume", "recording_mic_boost"]
    controller.shutdown()


@pytest.mark.asyncio
async def test_io_error_routes_to_device_lost_not_on_error():
    seen = {}
    api = FakeG6Api()
    api.fail_next(IOError("unplugged"))
    controller = G6Controller(
        api,
        on_error=lambda message: seen.setdefault("error", message),
        on_device_lost=lambda exc: seen.setdefault("lost", exc),
    )
    controller.submit("playback_enable_direct_mode", enable=True)
    await controller.flush()
    assert isinstance(seen.get("lost"), IOError)
    assert "error" not in seen
    controller.shutdown()


@pytest.mark.asyncio
async def test_other_errors_report_and_revert_the_widget():
    seen = {}
    reverted = []
    api = FakeG6Api()
    api.fail_next(RuntimeError("bad value"))
    controller = G6Controller(api, on_error=lambda message: seen.setdefault("error", message))
    controller.submit(
        "playback_enable_direct_mode", enable=True, revert=lambda: reverted.append(True)
    )
    await controller.flush()
    assert "bad value" in seen["error"]
    assert reverted == [True]
    controller.shutdown()


@pytest.mark.asyncio
async def test_model_is_exposed_for_initial_widget_values():
    api = FakeG6Api()
    controller = G6Controller(api)
    assert controller.model is api.get_model()
    controller.shutdown()


async def test_on_success_runs_only_after_a_successful_call():
    api = FakeG6Api()
    controller = G6Controller(api)
    seen = []
    controller.submit("claim_audio_interface", on_success=lambda: seen.append("ok"))
    await controller.flush()
    assert seen == ["ok"]
    controller.shutdown()


async def test_on_success_is_skipped_when_the_call_fails():
    api = FakeG6Api()
    api.fail_next(RuntimeError("nope"))
    controller = G6Controller(api, on_error=lambda m: None)
    seen = []
    controller.submit("claim_audio_interface", on_success=lambda: seen.append("ok"))
    await controller.flush()
    assert seen == []
    controller.shutdown()


# ── tolerate ──
#
# Motivating case: g6_gui.filters.NON_OVERSAMPLING. The real G6Api.playback_filter()
# writes the correct bytes to the wire *before* G6Model rejects the shim with
# a ValueError, so that ValueError must not be treated as a failure. These
# tests exercise the mechanism generically through FakeG6Api.fail_next(),
# which is enough to prove the controller's handling of "the call raised
# this exception type" -- whichever upstream step actually raised it.


async def test_tolerated_exception_does_not_revert_or_error_and_runs_on_success():
    seen = {}
    reverted = []
    api = FakeG6Api()
    api.fail_next(ValueError("playback_filter_enum must be PlaybackFilter"))
    controller = G6Controller(api, on_error=lambda message: seen.setdefault("error", message))
    controller.submit(
        "playback_filter",
        playback_filter_enum=object(),
        revert=lambda: reverted.append(True),
        on_success=lambda: seen.setdefault("success", True),
        tolerate=(ValueError,),
    )
    await controller.flush()
    assert "error" not in seen
    assert reverted == []
    assert seen.get("success") is True
    controller.shutdown()


async def test_an_exception_type_not_listed_in_tolerate_still_reverts_and_errors():
    # The negative case: tolerate=(ValueError,) must not swallow a different
    # exception type. A genuine failure from one of the four real filters
    # (or anything else) must still behave exactly as it did before
    # `tolerate` existed.
    seen = {}
    reverted = []
    api = FakeG6Api()
    api.fail_next(RuntimeError("genuinely broken"))
    controller = G6Controller(api, on_error=lambda message: seen.setdefault("error", message))
    controller.submit(
        "playback_filter",
        playback_filter_enum=object(),
        revert=lambda: reverted.append(True),
        on_success=lambda: seen.setdefault("success", True),
        tolerate=(ValueError,),
    )
    await controller.flush()
    assert "genuinely broken" in seen["error"]
    assert reverted == [True]
    assert "success" not in seen
    controller.shutdown()


async def test_tolerate_defaults_to_empty_and_changes_nothing_by_default():
    seen = {}
    reverted = []
    api = FakeG6Api()
    api.fail_next(ValueError("some genuine validation error"))
    controller = G6Controller(api, on_error=lambda message: seen.setdefault("error", message))
    controller.submit(
        "playback_filter",
        playback_filter_enum=object(),
        revert=lambda: reverted.append(True),
    )
    await controller.flush()
    assert "error" in seen
    assert reverted == [True]
    controller.shutdown()
