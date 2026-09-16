"""System — general options, claim/release and reload. Partly Linux only."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable

import toga

import g6_cli
import g6_gui
from g6_cli.g6_api import DEFAULT_MODEL_PATH
from g6_gui import help as help_text, widgets
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
    content = widgets.page()

    system_section = widgets.section("System")
    version_label = toga.Label(
        f"GUI version {g6_gui.VERSION}  |  CLI version {g6_cli.VERSION}  |  "
        f"model file: {os.path.expanduser(DEFAULT_MODEL_PATH)}"
    )
    system_section.add(version_label)
    content.add(system_section)
    content.version = version_label

    if AUDIO_INTERFACE_SUPPORTED:
        audio_section = widgets.section("Audio interface")

        claim_row = widgets.switch_row(
            "Claim audio interface",
            value=False,
            on_change=_make_claim_handler(controller, on_claim_changed),
            help=help_text.SYSTEM_CLAIM,
        )
        audio_section.add(claim_row)

        claim_warning = widgets.warning(CLAIM_WARNING)
        audio_section.add(claim_warning)

        reload_button = toga.Button(
            "Reload audio",
            on_press=lambda widget, *args, **kwargs: controller.submit("reload_audio"),
        )
        audio_section.add(reload_button)

        content.add(audio_section)
        content.claim = claim_row
        content.claim_warning = claim_warning
        content.reload_button = reload_button

    startup_note = widgets.note(
        "Dry-run, debug logging and model persistence are set by the "
        "--dry-run, --debug and --no-persist command-line flags when "
        "launching the GUI. Changing them requires restarting the app."
    )
    content.add(startup_note)

    return content


def _make_claim_handler(controller: G6Controller, on_claim_changed):
    def on_change(widget: toga.Switch) -> None:
        value = widget.value
        method = "claim_audio_interface" if value else "release_audio_interface"

        def revert() -> None:
            widget.value = not value

        controller.submit(
            method,
            revert=revert,
            on_success=(lambda: on_claim_changed(value)) if on_claim_changed else None,
        )

    return on_change
