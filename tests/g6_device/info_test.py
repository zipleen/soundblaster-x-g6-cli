"""Pure-logic tests for g6_device.info -- no real USB/HID is ever touched.

hid.enumerate()/usb.core.find() are replaced with fakes injected via
read_device_info's hid_enumerate/usb_finder parameters, the same "recording
double" approach tests/g6_gui/fake_api.py uses for G6Api.
"""

from __future__ import annotations

import pytest

from g6_device import DeviceInfo, G6_HID_INTERFACE, G6_PRODUCT_ID, G6_VENDOR_ID, format_bcd_version, read_device_info
from g6_device.info import _device_info_from_hid_entry, _pick_hid_entry


# ── format_bcd_version ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "value, expected",
    [
        (0x0200, "2.00"),
        (0x0100, "1.00"),
        (0x0134, "1.34"),
        (0x0000, "0.00"),
        (0x9999, "99.99"),
        (0x0001, "0.01"),
    ],
)
def test_format_bcd_version(value, expected):
    assert format_bcd_version(value) == expected


def test_format_bcd_version_masks_to_16_bits():
    # Defensive: a caller passing a too-wide int should not blow up or
    # silently produce a nonsensical multi-byte result.
    assert format_bcd_version(0x1FFFF) == format_bcd_version(0xFFFF)


# ── _pick_hid_entry ───────────────────────────────────────────────────────


def test_pick_hid_entry_prefers_the_control_interface():
    entries = [
        {"interface_number": 3, "product_string": "wrong interface"},
        {"interface_number": G6_HID_INTERFACE, "product_string": "Sound BlasterX G6"},
    ]
    picked = _pick_hid_entry(entries)
    assert picked["interface_number"] == G6_HID_INTERFACE


def test_pick_hid_entry_falls_back_to_first_when_no_match():
    entries = [{"interface_number": 3}, {"interface_number": 99}]
    assert _pick_hid_entry(entries) is entries[0]


def test_pick_hid_entry_of_empty_list_is_none():
    assert _pick_hid_entry([]) is None


# ── _device_info_from_hid_entry ─────────────────────────────────────────────


def test_device_info_from_hid_entry_decodes_release_number():
    entry = {
        "release_number": 0x0100,
        "manufacturer_string": "Creative Technology",
        "product_string": "Sound BlasterX G6",
        "serial_number": "E5004E4F57X",
        "interface_number": G6_HID_INTERFACE,
        "usage_page": 0xFFC0,
    }
    info = _device_info_from_hid_entry(entry)
    assert info.present is True
    assert info.usb_device_revision == "1.00"
    assert info.manufacturer == "Creative Technology"
    assert info.product == "Sound BlasterX G6"
    assert info.serial_number == "E5004E4F57X"
    assert info.interface_number == G6_HID_INTERFACE
    assert info.usage_page == 0xFFC0
    assert info.source == "hid"


def test_device_info_from_hid_entry_treats_empty_strings_as_absent():
    entry = {
        "release_number": 0x0100,
        "manufacturer_string": "",
        "product_string": "",
        "serial_number": "",
        "interface_number": G6_HID_INTERFACE,
        "usage_page": 0,
    }
    info = _device_info_from_hid_entry(entry)
    assert info.manufacturer is None
    assert info.product is None
    assert info.serial_number is None


def test_device_info_from_hid_entry_without_release_number():
    info = _device_info_from_hid_entry({"interface_number": G6_HID_INTERFACE})
    assert info.usb_device_revision is None


# ── read_device_info: the device-absent path (the one this machine can prove) ──


def test_read_device_info_when_no_device_is_enumerated():
    info = read_device_info(hid_enumerate=lambda vid, pid: [], usb_finder=lambda **kw: None)
    assert info == DeviceInfo(present=False)
    assert info.present is False
    assert info.error is None


def test_read_device_info_never_raises_when_hid_enumerate_blows_up():
    def broken_enumerate(vid, pid):
        raise OSError("hidapi backend unavailable")

    info = read_device_info(hid_enumerate=broken_enumerate)
    assert info.present is False
    assert "hidapi backend unavailable" in info.error


def test_read_device_info_never_raises_when_usb_finder_blows_up():
    entries = [
        {
            "release_number": 0x0100,
            "manufacturer_string": "Creative Technology",
            "product_string": "Sound BlasterX G6",
            "serial_number": "E5004E4F57X",
            "interface_number": G6_HID_INTERFACE,
            "usage_page": 0xFFC0,
        }
    ]

    def broken_finder(**kwargs):
        raise RuntimeError("no backend available")

    info = read_device_info(hid_enumerate=lambda vid, pid: entries, usb_finder=broken_finder)
    # HID data must still come through even though the pyusb augmentation failed.
    assert info.present is True
    assert info.usb_device_revision == "1.00"


def test_read_device_info_ignores_unrelated_hid_collections_only():
    """hid.enumerate is called with the G6's own VID/PID -- confirm the args."""
    seen = {}

    def fake_enumerate(vid, pid):
        seen["vid"] = vid
        seen["pid"] = pid
        return []

    read_device_info(hid_enumerate=fake_enumerate)
    assert seen == {"vid": G6_VENDOR_ID, "pid": G6_PRODUCT_ID}


# ── read_device_info: present, with the pyusb augmentation ─────────────────


class _FakeUsbDevice:
    def __init__(self, bcd_device, bcd_usb):
        self.bcdDevice = bcd_device
        self.bcdUSB = bcd_usb


def test_read_device_info_folds_in_usb_bcd_fields():
    entries = [
        {
            "release_number": 0x0100,
            "manufacturer_string": "Creative Technology",
            "product_string": "Sound BlasterX G6",
            "serial_number": "E5004E4F57X",
            "interface_number": G6_HID_INTERFACE,
            "usage_page": 0xFFC0,
        }
    ]
    fake_device = _FakeUsbDevice(bcd_device=0x0100, bcd_usb=0x0200)

    info = read_device_info(
        hid_enumerate=lambda vid, pid: entries,
        usb_finder=lambda **kw: fake_device,
    )

    assert info.present is True
    assert info.usb_device_revision == "1.00"
    assert info.usb_spec_version == "2.00"
    assert info.source == "hid+usb"
    # HID string descriptors are still preserved alongside the pyusb fields.
    assert info.manufacturer == "Creative Technology"
    assert info.serial_number == "E5004E4F57X"


def test_read_device_info_when_usb_finder_returns_none():
    entries = [{"release_number": 0x0100, "interface_number": G6_HID_INTERFACE}]
    info = read_device_info(hid_enumerate=lambda vid, pid: entries, usb_finder=lambda **kw: None)
    assert info.present is True
    assert info.usb_spec_version is None
    assert info.source == "hid"
