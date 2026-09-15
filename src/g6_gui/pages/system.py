"""System — general options, claim/release and reload. Partly Linux only."""

from __future__ import annotations

import os
from collections.abc import Callable

import toga

import g6_cli
import g6_gui
from g6_cli.g6_api import DEFAULT_MODEL_PATH
from g6_gui import widgets
from g6_gui.controller import G6Controller
from g6_gui.platform import AUDIO_INTERFACE_SUPPORTED

TITLE = "System"

CLAIM_WARNING = (
    "Claiming detaches the kernel audio driver — your system will have no "
    "audio output until you release it again."
)


def is_available() -> bool:
    return True


def build(
    controller: G6Controller,
    *,
    on_claim_changed: Callable[[bool], None] | None = None,
) -> toga.Widget:
    version_label = toga.Label(
        f"soundblaster-x-g6-gui {g6_gui.VERSION}  |  soundblaster-x-g6-cli "
        f"{g6_cli.VERSION}  |  model file: {os.path.expanduser(DEFAULT_MODEL_PATH)}"
    )

    children: list[toga.Widget] = [version_label]

    if AUDIO_INTERFACE_SUPPORTED:
        def on_claim_switch(widget):
            def revert():
                widget.value = not widget.value

            if widget.value:
                method = "claim_audio_interface"
            else:
                method = "release_audio_interface"

            def on_done():
                if on_claim_changed is not None:
                    on_claim_changed(widget.value)

            controller.submit(method, revert=revert, on_success=on_done)

        claim_row = widgets.switch_row(
            "Claim audio interface", value=False, on_change=on_claim_switch
        )
        claim_warning = widgets.warning(CLAIM_WARNING)

        def on_reload(widget):
            controller.submit("reload_audio")

        reload_button = toga.Button("Reload audio", on_press=on_reload)

        children.extend([claim_row, claim_warning, reload_button])

    startup_note = widgets.note(
        "Dry-run, debug logging and persistence are set by the --dry-run, "
        "--debug and --no-persist command-line flags when launching the GUI. "
        "Changing them requires restarting the app."
    )
    children.append(startup_note)

    content = widgets.page(*children)
    content.version = version_label
    if AUDIO_INTERFACE_SUPPORTED:
        content.claim = claim_row
        content.claim_warning = claim_warning
        content.reload_button = reload_button

    return content
