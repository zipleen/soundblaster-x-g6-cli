"""Mixer [Audio] — monitoring and recording levels. Linux only."""

from __future__ import annotations

import toga

from g6_gui import widgets
from g6_gui.controller import G6Controller
from g6_gui.platform import AUDIO_INTERFACE_SUPPORTED

TITLE = "Mixer"


def is_available() -> bool:
    return AUDIO_INTERFACE_SUPPORTED


def build(controller: G6Controller) -> toga.Widget:
    return widgets.page()
