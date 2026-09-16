"""One module per tab. Each exports TITLE, is_available() and build(controller)."""

from g6_gui.pages import lighting, macos_audio, mixer, playback, recording, sbx, system

ALL = [macos_audio, playback, mixer, recording, sbx, lighting, system]
