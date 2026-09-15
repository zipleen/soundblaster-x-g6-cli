"""One module per tab. Each exports TITLE, is_available() and build(controller)."""

from g6_gui.pages import lighting, mixer, playback, recording, sbx, system

ALL = [playback, mixer, recording, sbx, lighting, system]
