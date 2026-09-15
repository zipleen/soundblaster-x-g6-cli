"""Platform capability flags.

Every feature reached through the G6's USB AudioControl interface requires
detaching the kernel audio driver first (the CLI's ``--claim-and-release``).
That is only possible on Linux; macOS does not allow libusb to take the
interface away from its own USB audio class driver. Features behind this flag
are hidden rather than shown broken.
"""

import sys

AUDIO_INTERFACE_SUPPORTED: bool = sys.platform.startswith("linux")
