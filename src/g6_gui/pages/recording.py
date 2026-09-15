"""Recording [HID] + [Audio]."""

from __future__ import annotations

import toga

from g6_gui import widgets
from g6_gui.controller import G6Controller
from g6_gui.platform import AUDIO_INTERFACE_SUPPORTED

TITLE = "Recording"


def is_available() -> bool:
    return True


def build(controller: G6Controller) -> toga.Widget:
    return widgets.page()
