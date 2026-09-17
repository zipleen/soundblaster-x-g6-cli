"""Passive, read-only USB/HID device information for the Sound Blaster X G6.

Everything in this module reads descriptors the operating system already
cached when the device enumerated (``hid.enumerate()``) or, best-effort,
descriptor fields pyusb exposes on an open ``usb.core.Device`` handle
(``bcdDevice``/``bcdUSB``). **Neither path writes a single byte to the
device.** This is deliberately not the same thing as a firmware-version
readback: the G6's control protocol has no documented, wire-verified way to
ask the firmware for its version string (see ``experimental/probe-g6-hid.py`` for
the exploratory, undocumented attempt at that — a separate, opt-in tool, not
used here).

The most interesting field, ``bcdDevice`` (surfaced by hidapi as
``release_number`` and by pyusb as ``bcdDevice``), is a 16-bit BCD-encoded USB
"device release number" from the USB device descriptor. It **cannot** hold a
firmware version string like ``2.1.250903.1324`` — there simply are not
enough bits — so this module calls it what it is, a *USB device revision*,
and never labels it "firmware version".

Nothing here raises into the caller. Any failure (device absent, hidapi
error, no libusb backend, permission problem) degrades to
``DeviceInfo(present=False, ...)`` with an optional ``error`` string for
diagnostics.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from .constants import G6_HID_INTERFACE, G6_PRODUCT_ID, G6_VENDOR_ID

HidEnumerate = Callable[[int, int], Sequence[Mapping[str, Any]]]
UsbFinder = Callable[..., Any]

__all__ = ["DeviceInfo", "format_bcd_version", "read_device_info"]


@dataclass(frozen=True)
class DeviceInfo:
    """A snapshot of what could be learned about the G6 without writing to it.

    ``usb_device_revision``/``usb_spec_version`` are USB descriptor fields
    (``bcdDevice``/``bcdUSB``), formatted as dotted BCD (e.g. ``"1.00"``).
    They describe the USB interface silicon/descriptor set, not the audio
    firmware running behind it -- do not present either as a firmware
    version.
    """

    present: bool
    manufacturer: str | None = None
    product: str | None = None
    serial_number: str | None = None
    interface_number: int | None = None
    usage_page: int | None = None
    usb_device_revision: str | None = None
    usb_spec_version: str | None = None
    source: str = "none"
    error: str | None = None


def format_bcd_version(value: int) -> str:
    """Format a 16-bit BCD version field (``bcdDevice``/``bcdUSB``) as ``"J.MN"``.

    Standard USB convention (the same one ``lsusb`` uses): the high byte is
    two BCD digits of major version, the low byte's high nibble is the minor
    digit and its low nibble the sub-minor digit. ``0x0200`` -> ``"2.00"``,
    ``0x0134`` -> ``"1.34"``.
    """
    value &= 0xFFFF
    high_byte = (value >> 8) & 0xFF
    low_byte = value & 0xFF
    major = (high_byte >> 4) * 10 + (high_byte & 0xF)
    minor = (low_byte >> 4) & 0xF
    sub = low_byte & 0xF
    return f"{major}.{minor}{sub}"


def _clean_str(value: Any) -> str | None:
    """hidapi returns ``""`` for an absent descriptor string; normalise to None."""
    if isinstance(value, str) and value.strip():
        return value
    return None


def _pick_hid_entry(entries: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """Prefer the HID collection on the G6's control interface (4).

    ``hid.enumerate()`` can return one dict per top-level HID collection, and
    the G6 exposes more than one HID interface. Interface 4 is the one
    ``g6_cli.g6_core`` and Creative's own software use for control messages,
    so prefer it when present; otherwise fall back to whatever was found so
    the row still shows *something* rather than nothing.
    """
    if not entries:
        return None
    for entry in entries:
        if entry.get("interface_number") == G6_HID_INTERFACE:
            return entry
    return entries[0]


def _device_info_from_hid_entry(entry: Mapping[str, Any]) -> DeviceInfo:
    release_number = entry.get("release_number")
    revision = format_bcd_version(release_number) if isinstance(release_number, int) else None
    return DeviceInfo(
        present=True,
        manufacturer=_clean_str(entry.get("manufacturer_string")),
        product=_clean_str(entry.get("product_string")),
        serial_number=_clean_str(entry.get("serial_number")),
        interface_number=entry.get("interface_number"),
        usage_page=entry.get("usage_page"),
        usb_device_revision=revision,
        usb_spec_version=None,
        source="hid",
    )


def _default_hid_enumerate(vendor_id: int, product_id: int) -> Sequence[Mapping[str, Any]]:
    import hid

    return hid.enumerate(vendor_id, product_id)


def _default_usb_finder(**kwargs: Any) -> Any:
    import usb.core

    return usb.core.find(**kwargs)


def _read_usb_bcd_fields(usb_finder: UsbFinder | None) -> tuple[int | None, int | None]:
    """Best-effort ``bcdDevice``/``bcdUSB`` via pyusb. Never raises.

    pyusb needs a libusb backend to do anything at all; on a machine without
    one (or without the G6 attached) this can raise a range of exceptions
    (``usb.core.NoBackendError``, ``USBError``, permission errors). All of
    them are treated the same way here: no additional data, no crash.
    """
    find_fn = usb_finder or _default_usb_finder
    try:
        device = find_fn(idVendor=G6_VENDOR_ID, idProduct=G6_PRODUCT_ID)
    except Exception:
        return None, None
    if device is None:
        return None, None
    bcd_device = getattr(device, "bcdDevice", None)
    bcd_usb = getattr(device, "bcdUSB", None)
    bcd_device = bcd_device if isinstance(bcd_device, int) else None
    bcd_usb = bcd_usb if isinstance(bcd_usb, int) else None
    return bcd_device, bcd_usb


def read_device_info(
    hid_enumerate: HidEnumerate | None = None,
    usb_finder: UsbFinder | None = None,
) -> DeviceInfo:
    """Passively read what descriptors say about an attached G6.

    Zero writes to the device. Tries ``hid.enumerate()`` first (richest,
    string descriptors included); if pyusb can also see the device, its
    ``bcdDevice``/``bcdUSB`` are folded in too since they come straight from
    the USB device descriptor rather than a HID-layer copy of it. Absence of
    either source (no device, no backend, any error) degrades to
    ``present=False`` rather than raising.

    ``hid_enumerate``/``usb_finder`` are injection points for tests; real
    callers should not need to pass them.
    """
    enumerate_fn = hid_enumerate or _default_hid_enumerate
    try:
        entries = enumerate_fn(G6_VENDOR_ID, G6_PRODUCT_ID)
    except Exception as exc:
        return DeviceInfo(present=False, error=f"HID enumerate failed: {exc}")

    entry = _pick_hid_entry(entries)
    if entry is None:
        return DeviceInfo(present=False)

    info = _device_info_from_hid_entry(entry)

    usb_bcd_device, usb_bcd_usb = _read_usb_bcd_fields(usb_finder)
    updates: dict[str, Any] = {}
    if usb_bcd_device is not None:
        updates["usb_device_revision"] = format_bcd_version(usb_bcd_device)
        updates["source"] = "hid+usb"
    if usb_bcd_usb is not None:
        updates["usb_spec_version"] = format_bcd_version(usb_bcd_usb)

    return replace(info, **updates) if updates else info
