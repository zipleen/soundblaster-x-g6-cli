"""System — general options, claim/release and reload. Partly Linux only."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable

import toga
from toga.style.pack import CENTER, ROW, Pack

import g6_cli
import g6_gui
from g6_cli.g6_api import DEFAULT_MODEL_PATH
from g6_device import DeviceInfo, read_device_info
from g6_gui import help as help_text, widgets
from g6_gui.controller import G6Controller
from g6_gui.platform import AUDIO_INTERFACE_SUPPORTED

TITLE = "System"

CLAIM_WARNING = (
    "Claiming detaches the kernel audio driver — your system will have no "
    "audio output until you release it again."
)

DEVICE_INFO_NOTE = (
    "Read from descriptors the operating system already has -- nothing is "
    "sent to the device. This is not the firmware version, which cannot "
    "currently be read back from a G6 at all. See the (i) for why."
)

DEVICE_INFO_ABSENT = (
    "No Sound Blaster X G6 was found over HID. Plug it in and press Refresh."
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

    device_section = _build_device_info_section()
    content.add(device_section)
    content.device_row = device_section.device_row
    content.device_revision = device_section.device_revision
    content.device_details = device_section.device_details
    content.device_refresh = device_section.device_refresh

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


def _safe_read_device_info() -> DeviceInfo:
    """Read-only, degrades to ``present=False`` on any failure. Never blocks or raises.

    ``g6_device.read_device_info`` already guarantees this on its own (it only
    reads OS-cached descriptors -- no device I/O happens here), but the extra
    guard costs nothing and keeps this page's promise self-contained.
    """
    try:
        return read_device_info()
    except Exception as exc:  # pragma: no cover - defence in depth, see docstring
        return DeviceInfo(present=False, error=str(exc))


def _format_device_revision(info: DeviceInfo) -> str:
    if not info.present:
        return "Not detected"
    return info.usb_device_revision or "unknown"


def _format_device_details(info: DeviceInfo) -> str:
    if not info.present:
        return DEVICE_INFO_ABSENT + (f" ({info.error})" if info.error else "")
    bits = []
    name = " ".join(part for part in (info.manufacturer, info.product) if part)
    if name:
        bits.append(name)
    if info.serial_number:
        bits.append(f"serial {info.serial_number}")
    if info.usb_spec_version:
        bits.append(f"USB {info.usb_spec_version}")
    return ", ".join(bits) if bits else "Detected, but no descriptor strings were available."


def _make_device_info_refresh_handler(revision_label: toga.Label, details_block):
    def on_press(widget, *args, **kwargs) -> None:
        info = _safe_read_device_info()
        revision_label.text = _format_device_revision(info)
        details_block.set_text(_format_device_details(info))

    return on_press


def _build_device_info_section() -> toga.Box:
    section = widgets.section("Device information")

    info = _safe_read_device_info()

    row = toga.Box(style=Pack(direction=ROW, margin_bottom=5, align_items=CENTER, gap=8))
    caption = toga.Label("USB device revision", style=Pack(width=widgets.LABEL_WIDTH))
    revision_label = toga.Label(_format_device_revision(info), style=Pack(flex=1))
    row.add(caption)
    row.add(revision_label)
    wrapped_row = widgets.with_help(row, help_text.SYSTEM_DEVICE_INFO)
    section.add(wrapped_row)

    details_block = widgets.dynamic_note_block(_format_device_details(info))
    section.add(details_block)

    honesty_note = widgets.note_block(DEVICE_INFO_NOTE)
    section.add(honesty_note)

    refresh_button = toga.Button(
        "Refresh",
        on_press=_make_device_info_refresh_handler(revision_label, details_block),
    )
    section.add(refresh_button)

    section.device_row = wrapped_row
    section.device_revision = revision_label
    section.device_details = details_block
    section.device_refresh = refresh_button
    return section
