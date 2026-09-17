"""Shared USB identifiers for the Sound Blaster X G6.

Mirrors the constants in ``g6_cli.g6_core`` (frozen upstream code, never
imported from here on purpose — this package must not create a dependency on
it). Kept in a tiny module of its own so both ``info.py`` and
``experimental/probe-g6-hid.py`` share one source of truth instead of three copies
of the same magic numbers drifting apart.
"""

from __future__ import annotations

G6_VENDOR_ID = 0x041E
G6_PRODUCT_ID = 0x3256

# The G6 exposes five USB interfaces (1 Audio Control, 2 Audio Streams, 2
# HID). Interface 4 is the one Creative's own software uses for HID control
# messages -- interface 3 is present but the device ignores data sent to it.
# See src/g6_cli/g6_core.py's G6_HID_INTERFACE for the upstream equivalent.
G6_HID_INTERFACE = 4
