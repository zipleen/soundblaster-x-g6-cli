"""macOS Audio — the *real* Direct Mode switch on macOS.

Everything on the Playback tab's Direct Mode / SPDIF-Out Direct switches is
sent over the G6's USB HID protocol, and on macOS that protocol is overridden
by Core Audio (see docs/settings-reference.md). This tab controls the thing
that actually wins: the G6's Clock Source and stream Format, read and written
directly through Core Audio -- the same mechanism Audio MIDI Setup itself
uses, not a workaround or a guess.

Only available on macOS. Deliberately narrow: this recognises exactly the
G6's two documented modes (DSP Clock, Stereo Direct) and nothing else -- any
other configuration greys the tab out with an explanation rather than
attempting to support it. See coreaudio.classify_clock_sources().
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine

import toga
from toga.style.pack import CENTER, ROW, Pack

from g6_gui import coreaudio, help as help_text, widgets
from g6_gui.controller import G6Controller
from g6_gui.platform import IS_MACOS

TITLE = "macOS Audio"

_INTRO = (
    "For macOS, Direct Mode is controlled via macOS in this panel. "
    "The Clock Source and Format below live in macOS's own Core Audio, not "
    "in this app's usual device protocol -- macOS always wins that argument, "
    "so this is the tab that actually controls it."
)

_NOT_FOUND = (
    "Could not identify the G6 in Core Audio. If it is connected, this also "
    "happens if its Clock Source options do not look exactly like \"DSP "
    "Clock\" and \"Stereo Direct\" -- an aggregate device, an unusual "
    "firmware state, or simply a different device entirely. Try opening "
    "Audio MIDI Setup directly, or press Refresh once the device is ready."
)

def is_available() -> bool:
    return IS_MACOS


def _status_summary(state: coreaudio.ClockState) -> str:
    source = state.current_clock_source or "unknown"
    fmt = state.current_format.label() if state.current_format else "unknown format"
    return f"Current: {source} \u2014 {fmt}"


def _volume_text(state: coreaudio.ClockState) -> str:
    """The read-only volume line. ``None`` is a real, distinct case -- the
    device exposes no host-settable volume at all -- not the same as 0%,
    and is worded to say so rather than silently showing "0%".

    Appends the dB reading in parentheses when it is available -- it is the
    figure the full-scale warning actually decides from when present (see
    coreaudio.is_full_scale_volume()), so showing it lets a mismatch between
    "looks fine as a percentage" and "still above -2 dBFS" be seen directly
    rather than only inferred from whether the warning appeared.
    """
    if state.output_volume is None:
        return "Output Volume: not reported by this device"
    text = f"Output Volume: {round(state.output_volume * 100)}%"
    if state.output_volume_db is not None:
        text += f" ({state.output_volume_db:.1f} dB)"
    return text


def _channels_text(state: coreaudio.ClockState) -> str:
    if state.output_channels is None:
        return "Output Channels: unknown"
    text = f"Output Channels: {state.output_channels}"
    if state.non_stereo_formats_available:
        text += " (a non-stereo format is also offered -- see help)"
    return text


def _make_clock_controller() -> coreaudio.ClockController:
    """The real, ctypes-backed controller. Tests monkeypatch this factory to
    inject one built on tests/g6_gui/fake_coreaudio.FakeHal instead."""
    return coreaudio.ClockController()


def _spawn(coro: Coroutine) -> None:
    """Schedule ``coro``, whether or not a Toga event loop is currently
    running.

    Same problem, same fix, as G6Controller._spawn (see controller.py and
    HANDOFF.md gotcha #9): a Toga event handler normally runs with the app's
    asyncio loop active, so plain ensure_future() is fine there -- but from a
    synchronous test, or a handler invoked directly, there is no running
    loop, ensure_future() raises, and Toga swallows the traceback, silently
    dropping the clock-source switch. Not duplicated from controller.py
    because this page has no G6Controller-related work to share it with --
    it talks to Core Audio, not the G6's own protocol -- so a second small
    copy is clearer than reaching into that class's internals.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
        return
    asyncio.ensure_future(coro)


def build(
    controller: G6Controller,
    *,
    on_clock_source_changed: Callable[[str | None], None] | None = None,
) -> toga.Widget:
    del controller  # this page talks to Core Audio, not the G6's own protocol

    clock = _make_clock_controller()
    content = widgets.page()

    section = widgets.section("macOS Audio")
    section.add(widgets.note_block(_INTRO))

    status = widgets.dynamic_note_block("")
    section.add(status)

    # Read-only: a note line, never a slider -- this app deliberately never
    # moves the user's volume itself (see help_text.MACOS_VOLUME). The (i)
    # help is attached to the row's caption, not to `volume_note` itself,
    # because `_DynamicTextBlock.set_text()` clears *all* of its own
    # children on every update -- anchoring the button there would delete it
    # the first time the reading changes.
    volume_row = toga.Box(style=Pack(direction=ROW, align_items=CENTER, gap=8))
    volume_note = widgets.dynamic_note_block("")
    volume_row.add(volume_note)
    volume_group = widgets.with_help(volume_row, help_text.MACOS_VOLUME)
    section.add(volume_group)

    volume_warning = widgets.dynamic_warning_block("")
    section.add(volume_warning)

    channels_row = toga.Box(style=Pack(direction=ROW, align_items=CENTER, gap=8))
    channels_note = widgets.dynamic_note_block("")
    channels_row.add(channels_note)
    channels_group = widgets.with_help(channels_row, help_text.MACOS_CHANNELS)
    section.add(channels_group)

    # Guards clock_source_row/format_row's .value while it is set
    # programmatically during a render. Toga's Cocoa backend fires on_change
    # for a programmatic assignment too -- confirmed the hard way once
    # already in this codebase (the SBX profile-switch bug, see HANDOFF.md).
    # Without this, every render would re-submit whatever the dropdowns
    # already showed.
    rendering = {"active": False}

    def render(state: coreaudio.ClockState, status_message: str | None = None) -> None:
        """Sync the widgets to ``state``.

        ``status_message`` overrides the default "Current: ..." text -- used
        after a failed switch, so the error is what the user sees rather than
        this call's own default message stomping it a moment later. The
        widgets themselves always reflect ``state``, i.e. reality as just
        re-read from Core Audio, never the attempted-but-failed value.
        """
        rendering["active"] = True
        try:
            if not state.found:
                status.set_text(status_message or _NOT_FOUND)
                widgets.set_enabled(clock_source_row.control_row, False)
                widgets.set_enabled(format_row.control_row, False)
                format_row.selection.items = []
                # Nothing was actually read -- an empty reading, not a "0%"
                # or "0 channels" one, so these disappear entirely rather
                # than show a number that was never measured.
                volume_note.set_text("")
                volume_warning.set_text("")
                channels_note.set_text("")
            else:
                status.set_text(status_message or _status_summary(state))
                widgets.set_enabled(clock_source_row.control_row, True)
                if state.current_clock_source is not None:
                    clock_source_row.selection.value = state.current_clock_source

                available = list(state.available_formats)
                format_row.selection.items = [f.label() for f in available] or [""]
                widgets.set_enabled(format_row.control_row, bool(available))
                if state.current_format is not None and state.current_format in available:
                    format_row.selection.value = state.current_format.label()

                volume_note.set_text(_volume_text(state))
                volume_warning.set_text(
                    help_text.VOLUME_FULL_SCALE_WARNING
                    if coreaudio.is_full_scale_volume(state.output_volume, state.output_volume_db)
                    else ""
                )
                channels_note.set_text(_channels_text(state))
        finally:
            rendering["active"] = False

        if on_clock_source_changed:
            on_clock_source_changed(state.current_clock_source if state.found else None)

    def on_clock_source_change(widget) -> None:
        if rendering["active"]:
            return
        name = widget.value

        async def run():
            loop = asyncio.get_running_loop()
            try:
                await loop.run_in_executor(None, clock.set_clock_source, name)
            except (TimeoutError, RuntimeError, ValueError) as exc:
                clock.refresh()
                render(clock.state, status_message=f"Could not switch: {exc}")
                return
            render(clock.state)

        _spawn(run())

    def on_format_change(widget) -> None:
        if rendering["active"]:
            return
        label = widget.value
        match = next((f for f in clock.state.available_formats if f.label() == label), None)
        if match is None:
            return

        async def run():
            loop = asyncio.get_running_loop()
            try:
                await loop.run_in_executor(None, clock.set_format, match)
            except (TimeoutError, RuntimeError, ValueError) as exc:
                clock.refresh()
                render(clock.state, status_message=f"Could not switch: {exc}")
                return
            render(clock.state)

        _spawn(run())

    clock_source_row = widgets.select_row(
        "Clock Source",
        items=[coreaudio.DSP_CLOCK, coreaudio.STEREO_DIRECT],
        value=coreaudio.DSP_CLOCK,
        on_change=on_clock_source_change,
        help=help_text.MACOS_CLOCK_SOURCE,
    )
    section.add(clock_source_row)

    format_row = widgets.select_row(
        "Format",
        items=[""],
        value=None,
        on_change=on_format_change,
        help=help_text.MACOS_FORMAT,
    )
    section.add(format_row)

    # Volume and channel count are picked up by re-reading Core Audio here on
    # Refresh (and on every clock-source/format switch, via the existing
    # render(clock.refresh())/render(clock.state) calls above) rather than
    # via an AudioObjectAddPropertyListener. A real listener would let this
    # update the instant the menu bar slider moves, but Core Audio delivers
    # listener callbacks on its own internal dispatch queue, not this app's
    # asyncio loop -- getting a value back onto Toga's main thread safely
    # would need its own cross-thread handoff, and get it wrong exactly the
    # way gotcha 20/25 in HANDOFF.md warn about (trusting an async callback's
    # timing without polling to confirm it actually landed). Given no G6 is
    # attached to develop or test that hand-off against, polling on a
    # deliberate user action (Refresh, or already visiting the tab) is the
    # honest tradeoff here: a little less live than a listener, but nothing
    # that can silently race the UI thread.
    refresh_button_row = widgets.button_row(
        ("Refresh", lambda widget, *a, **k: render(clock.refresh()))
    )
    section.add(refresh_button_row)

    content.add(section)
    content.status = status
    content.clock_source = clock_source_row
    content.format = format_row
    content.volume = volume_group
    content.volume_note = volume_note
    content.volume_warning = volume_warning
    content.channels = channels_group
    content.channels_note = channels_note
    content.refresh_button = refresh_button_row.buttons[0]
    content.clock_controller = clock  # exposed for tests and diagnostics

    render(clock.refresh())

    return content
