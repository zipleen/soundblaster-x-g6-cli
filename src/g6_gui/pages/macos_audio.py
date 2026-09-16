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

    refresh_button_row = widgets.button_row(
        ("Refresh", lambda widget, *a, **k: render(clock.refresh()))
    )
    section.add(refresh_button_row)

    content.add(section)
    content.status = status
    content.clock_source = clock_source_row
    content.format = format_row
    content.refresh_button = refresh_button_row.buttons[0]
    content.clock_controller = clock  # exposed for tests and diagnostics

    render(clock.refresh())

    return content
