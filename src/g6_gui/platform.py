"""Platform capability flags.

Every feature reached through the G6's USB AudioControl interface requires
detaching the kernel audio driver first (the CLI's ``--claim-and-release``).
That is only possible on Linux; macOS does not allow libusb to take the
interface away from its own USB audio class driver. Features behind this flag
are hidden rather than shown broken.
"""

import subprocess
import sys

AUDIO_INTERFACE_SUPPORTED: bool = sys.platform.startswith("linux")

IS_MACOS: bool = sys.platform == "darwin"

#: macOS asserts the USB Audio Class clock selector continuously and overwrites
#: whatever the device was told, so the Direct Mode / SPDIF-Out Direct packets
#: have no effect there. Creative documents this: on a Mac the mode is chosen in
#: Audio MIDI Setup (Clock Source: "DSP Clock" vs "Stereo Direct"), not on the
#: device. See docs/settings-reference.md.
DIRECT_MODE_SUPPORTED: bool = not IS_MACOS

AUDIO_MIDI_SETUP_BUNDLE_ID = "com.apple.audio.AudioMIDISetup"


def open_audio_midi_setup() -> bool:
    """Launch macOS Audio MIDI Setup. Returns whether the launch succeeded.

    This is where Direct Mode actually lives on macOS, so the Playback page
    offers it as a button rather than asking the user to go hunting.
    """
    if not IS_MACOS:
        return False
    try:
        subprocess.run(
            ["open", "-b", AUDIO_MIDI_SETUP_BUNDLE_ID],
            check=True,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return True
