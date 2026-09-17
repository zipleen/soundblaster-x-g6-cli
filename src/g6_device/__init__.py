"""Raw USB/HID access for the Sound Blaster X G6, kept out of ``g6_gui``.

``g6_gui`` should never talk to USB/HID directly -- it imports from here
instead. This package is new and separate from ``src/g6_cli`` (upstream,
frozen, never modified) and from ``src/g6_gui`` (the Toga application).

Currently this package only offers a passive, read-only device-info snapshot
(:func:`read_device_info`). See ``experimental/probe-g6-hid.py`` for the separate,
opt-in, undocumented-protocol exploration tool -- deliberately not part of
this package's public API, since it sends exploratory writes and is not meant
to be imported by the GUI.
"""

from __future__ import annotations

from .constants import G6_HID_INTERFACE, G6_PRODUCT_ID, G6_VENDOR_ID
from .info import DeviceInfo, format_bcd_version, read_device_info

__all__ = [
    "DeviceInfo",
    "G6_HID_INTERFACE",
    "G6_PRODUCT_ID",
    "G6_VENDOR_ID",
    "format_bcd_version",
    "read_device_info",
]
