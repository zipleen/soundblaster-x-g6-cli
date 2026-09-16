"""The application shell: device gate, tab assembly and clean shutdown."""

from __future__ import annotations

import argparse
import sys

import toga
from toga.style.pack import COLUMN, ROW, Pack

from g6_cli.g6_api import G6Api

from g6_gui import VERSION, native, pages, widgets
from g6_gui.controller import G6Controller

WINDOW_SIZE = (860, 620)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="soundblaster-x-g6-gui", description="SoundBlaster X G6 GUI"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate device communication without sending anything to the G6.",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print device communication to the console."
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Do not read or write the saved G6 state file.",
    )
    parser.add_argument("--version", action="version", version=f"soundblaster-x-g6-gui {VERSION}")
    return parser.parse_args(argv if argv is not None else [])


def build_api(args: argparse.Namespace):
    """Construct the G6Api. Raises IOError when no device is attached."""
    # In a packaged .app there is no system libusb to find; point pyusb at the
    # copy inside the bundle before the first device lookup.
    native.ensure_libusb()
    return G6Api(dry_run=args.dry_run, debug=args.debug, persist_model=not args.no_persist)


def visible_pages() -> list:
    """The page modules that apply to this platform, in display order."""
    return [module for module in pages.ALL if module.is_available()]


def build_pages(controller: G6Controller):
    """Build every visible page.

    Returns ``(tabs, audio_gated)`` where ``tabs`` is a list of
    ``(title, content)`` and ``audio_gated`` holds the boxes that stay disabled
    until the USB AudioControl interface is claimed.

    On macOS, Recording and SBX are additionally disabled whenever the macOS
    Audio tab reports the Clock Source is Stereo Direct -- those controls are
    sent over the G6's HID protocol, which Direct Mode bypasses entirely (see
    docs/settings-reference.md), so they would do nothing right now. That gate
    is applied once at the end, after every page has been built, so it does
    not depend on macOS Audio happening to build before Recording/SBX do.
    """
    audio_gated: list = []
    clock_source_gated: list = []
    clock_source_state = {"name": None}

    def on_claim_changed(claimed: bool) -> None:
        for box in audio_gated:
            widgets.set_enabled(box, claimed)

    def on_clock_source_changed(name: str | None) -> None:
        clock_source_state["name"] = name
        _apply_clock_source_gate(clock_source_gated, name)

    tabs = []
    for module in visible_pages():
        if module is pages.system:
            content = module.build(controller, on_claim_changed=on_claim_changed)
        elif module is pages.macos_audio:
            content = module.build(controller, on_clock_source_changed=on_clock_source_changed)
        else:
            content = module.build(controller)

        if module is pages.mixer:
            audio_gated.append(content)
        elif hasattr(content, "audio_section"):
            audio_gated.append(content.audio_section)

        if module in (pages.recording, pages.sbx):
            clock_source_gated.append(content)

        tabs.append((module.TITLE, content))

    # macOS Audio may have built before Recording/SBX (or after, or not at
    # all on Linux); re-apply now that clock_source_gated is fully populated.
    _apply_clock_source_gate(clock_source_gated, clock_source_state["name"])

    return tabs, audio_gated


def _apply_clock_source_gate(boxes: list, clock_source_name: str | None) -> None:
    """Disable Recording/SBX only once positively confirmed to be pointless.

    ``clock_source_name`` is ``None`` both on Linux (no macOS Audio tab exists
    at all) and when macOS Audio could not positively identify the G6's clock
    source -- in neither case do we actually know Stereo Direct is active, so
    the conservative choice is to leave these tabs enabled rather than
    speculatively disable them.
    """
    is_direct = clock_source_name == pages.macos_audio.coreaudio.STEREO_DIRECT
    for box in boxes:
        widgets.set_enabled(box, not is_direct)


class G6App(toga.App):
    """Shows a connect-your-device gate until a G6 is found, then the tabs."""

    def __init__(self, args: argparse.Namespace | None = None, **kwargs):
        self._args = args if args is not None else parse_args([])
        self._controller: G6Controller | None = None
        self._claimed = False
        super().__init__("Sound Blaster X G6", "dev.g6cli.gui", **kwargs)

    # ── lifecycle ──

    def startup(self) -> None:
        self.main_window = toga.MainWindow(title="Sound Blaster X G6", size=WINDOW_SIZE)
        self._status = toga.Label("", style=Pack(margin=6, color="#B25000"))
        self.main_window.content = self._gate_view()
        self.main_window.show()
        self.try_connect()

    def on_exit(self) -> bool:
        """Always release the audio interface before quitting."""
        if self._controller is not None:
            if self._claimed:
                try:
                    self._controller.api.release_audio_interface()
                except Exception:  # noqa: BLE001 - quitting must not be blocked
                    pass
            self._controller.shutdown()
        return True

    # ── device gate ──

    def _gate_view(self, message: str = "") -> toga.Widget:
        box = toga.Box(style=Pack(direction=COLUMN, margin=40, gap=10))
        box.add(toga.Label("Connect your Sound Blaster X G6", style=Pack(font_size=18)))
        box.add(
            widgets.note(
                "The device must be plugged in before it can be controlled. "
                "Connect it, then choose Retry."
            )
        )
        if message:
            box.add(widgets.warning(message))
        row = toga.Box(style=Pack(direction=ROW, gap=8))
        row.add(toga.Button("Retry", on_press=self._on_retry))
        box.add(row)
        return box

    def _on_retry(self, widget) -> None:
        self.try_connect()

    def try_connect(self) -> bool:
        """Attempt to reach the device. Show the tabs on success, the gate on failure."""
        try:
            api = build_api(self._args)
        except IOError as exc:
            self._controller = None
            self.main_window.content = self._gate_view(str(exc))
            return False
        except Exception as exc:  # noqa: BLE001 - never crash into a blank window
            self._controller = None
            self.main_window.content = self._gate_view(f"Unexpected error: {exc}")
            return False

        self._controller = G6Controller(
            api, on_error=self._show_error, on_device_lost=self._on_device_lost
        )
        self.main_window.content = self._tabs_view(self._controller)
        return True

    def _on_device_lost(self, exc: Exception) -> None:
        self._claimed = False
        if self._controller is not None:
            self._controller.shutdown()
            self._controller = None
        self.main_window.content = self._gate_view(f"Lost connection to the G6: {exc}")

    def _show_error(self, message: str) -> None:
        self._status.text = message

    # ── tabs ──

    def _tabs_view(self, controller: G6Controller) -> toga.Widget:
        tabs, _ = build_pages(controller)
        container = toga.OptionContainer(content=list(tabs), style=Pack(flex=1))
        root = toga.Box(style=Pack(direction=COLUMN, flex=1))
        root.add(container)
        self._status.text = ""
        root.add(self._status)
        return root


def main():
    return G6App(parse_args(sys.argv[1:]))
