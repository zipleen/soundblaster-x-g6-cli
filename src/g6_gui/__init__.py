"""Cross-platform GUI for the SoundBlaster X G6."""

VERSION = "1.1.0"


def main():
    """Entry point for the ``soundblaster-x-g6-gui`` script."""
    from g6_gui.app import main as app_main

    return app_main().main_loop()
