"""Cross-platform GUI for the SoundBlaster X G6."""

#: The GUI's own version, deliberately independent of ``g6_cli.VERSION``.
#:
#: The two are different things. ``g6_cli.VERSION`` is upstream's CLI, which
#: this fork never modifies; it happened to read 1.1.0 when the GUI was started,
#: and the GUI simply inherited that number. It was never a statement about the
#: GUI's own maturity.
#:
#: This is pre-1.0 and says so. It moves when the GUI changes, not when upstream
#: releases. Note this is *not* the version of the released .app/.dmg, which
#: comes from ``version`` in pyproject.toml and also drives the release tag.
VERSION = "0.2.1"


def main():
    """Entry point for the ``soundblaster-x-g6-gui`` script."""
    from g6_gui.app import main as app_main

    return app_main().main_loop()
