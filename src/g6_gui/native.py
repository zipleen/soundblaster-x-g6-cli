"""Locate native libraries when running from a packaged .app bundle.

``hidapi``'s wheel statically embeds libhidapi, so it needs nothing here. But
``pyusb`` loads ``libusb-1.0.dylib`` at runtime through
``ctypes.util.find_library``, which searches the system's library paths — on a
machine without Homebrew there is nothing to find, and the app would start fine
and then fail to see the device.

The packaging script copies the dylib into ``Contents/Resources/lib``. This
module points pyusb at that copy before any device lookup happens.
"""

from __future__ import annotations

import sys
from pathlib import Path

LIB_SUBDIR = "lib"
LIBUSB_NAME = "libusb-1.0.dylib"


def bundle_lib_dir() -> Path | None:
    """The bundled library directory, or None when not running from a .app."""
    for start in (Path(sys.executable), Path(__file__)):
        for parent in start.resolve().parents:
            if parent.suffix == ".app":
                candidate = parent / "Contents" / "Resources" / LIB_SUBDIR
                if candidate.is_dir():
                    return candidate
    return None


def bundled_libusb() -> Path | None:
    """Path to the bundled libusb, or None when it is not present."""
    lib_dir = bundle_lib_dir()
    if lib_dir is None:
        return None
    candidate = lib_dir / LIBUSB_NAME
    return candidate if candidate.exists() else None


def ensure_libusb() -> str | None:
    """Prime pyusb's backend with the bundled libusb, if there is one.

    Returns the path used, or None when running outside a bundle (in which case
    pyusb's normal system lookup applies and nothing needs doing).
    """
    candidate = bundled_libusb()
    if candidate is None:
        return None

    import usb.backend.libusb1 as libusb1

    # get_backend() caches the loaded library module-globally, so priming it
    # once here settles every later usb.core.find() call.
    libusb1.get_backend(find_library=lambda _name: str(candidate))
    return str(candidate)
