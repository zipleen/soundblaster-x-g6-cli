from __future__ import annotations

import pytest

from g6_device import DeviceInfo
from g6_gui.controller import G6Controller
from g6_gui.pages import system
from tests.g6_gui.fake_api import FakeG6Api


@pytest.fixture
def linux(monkeypatch):
    monkeypatch.setattr("g6_gui.pages.system.AUDIO_INTERFACE_SUPPORTED", True)
    api = FakeG6Api()
    controller = G6Controller(api)
    yield api, controller
    controller.shutdown()


async def test_claim_switch_claims_and_releases(linux):
    api, controller = linux
    content = system.build(controller)
    content.claim.switch.value = True
    await controller.flush()
    assert api.method_names()[-1] == "claim_audio_interface"
    content.claim.switch.value = False
    await controller.flush()
    assert api.method_names()[-1] == "release_audio_interface"


async def test_claim_notifies_the_app(linux):
    api, controller = linux
    seen = []
    content = system.build(controller, on_claim_changed=seen.append)
    content.claim.switch.value = True
    await controller.flush()
    assert seen == [True]


def test_claim_carries_an_explicit_warning(linux):
    _, controller = linux
    content = system.build(controller)
    assert "no audio output" in content.claim_warning.text


async def test_reload_button_reloads_audio(linux):
    api, controller = linux
    content = system.build(controller)
    content.reload_button.on_press(content.reload_button)
    await controller.flush()
    assert "reload_audio" in api.method_names()


def test_linux_only_controls_are_absent_on_macos(monkeypatch):
    monkeypatch.setattr("g6_gui.pages.system.AUDIO_INTERFACE_SUPPORTED", False)
    controller = G6Controller(FakeG6Api())
    content = system.build(controller)
    assert not hasattr(content, "claim")
    assert not hasattr(content, "reload_button")
    assert hasattr(content, "version")
    controller.shutdown()


# ── Device information (g6_device passive readback) ─────────────────────────


def test_device_info_absent_does_not_block_or_raise(monkeypatch):
    """No G6 is attached in this dev environment -- this is the one path that
    can actually be exercised for real, and it must render cleanly rather
    than hang or blow up the page."""
    monkeypatch.setattr("g6_gui.pages.system.read_device_info", lambda: DeviceInfo(present=False))
    controller = G6Controller(FakeG6Api())
    content = system.build(controller)
    assert content.device_revision.text == "Not detected"
    controller.shutdown()


def test_device_info_absent_shows_the_not_found_note(monkeypatch):
    monkeypatch.setattr("g6_gui.pages.system.read_device_info", lambda: DeviceInfo(present=False))
    controller = G6Controller(FakeG6Api())
    content = system.build(controller)
    assert any("No Sound Blaster X G6 was found" in line for line in content.device_details.lines)
    controller.shutdown()


def test_device_info_present_shows_usb_revision_not_firmware_version(monkeypatch):
    info = DeviceInfo(
        present=True,
        manufacturer="Creative Technology",
        product="Sound BlasterX G6",
        serial_number="E5004E4F57X",
        usb_device_revision="1.00",
        usb_spec_version="2.00",
        source="hid+usb",
    )
    monkeypatch.setattr("g6_gui.pages.system.read_device_info", lambda: info)
    controller = G6Controller(FakeG6Api())
    content = system.build(controller)

    assert content.device_revision.text == "1.00"
    details_text = " ".join(content.device_details.lines)
    assert "Creative Technology" in details_text
    assert "E5004E4F57X" in details_text
    assert "USB 2.00" in details_text
    controller.shutdown()


def test_device_info_row_carries_the_firmware_help_text(monkeypatch):
    """system.py must use help_text.SYSTEM_DEVICE_INFO as the help= for this row,
    per the task's instruction -- even though its wording currently assumes a
    real firmware-version readback (a follow-up wording fix, not something
    this page should silently work around by picking different help text)."""
    from g6_gui import help as help_text, widgets

    monkeypatch.setattr("g6_gui.pages.system.read_device_info", lambda: DeviceInfo(present=False))
    controller = G6Controller(FakeG6Api())
    content = system.build(controller)
    assert content.device_row.help.lines == widgets.help_block(help_text.SYSTEM_DEVICE_INFO).lines
    controller.shutdown()


def test_device_info_refresh_button_re_reads(monkeypatch):
    responses = iter(
        [
            DeviceInfo(present=False),
            DeviceInfo(present=True, usb_device_revision="1.00", source="hid"),
        ]
    )
    monkeypatch.setattr("g6_gui.pages.system.read_device_info", lambda: next(responses))
    controller = G6Controller(FakeG6Api())
    content = system.build(controller)
    assert content.device_revision.text == "Not detected"

    content.device_refresh.on_press(content.device_refresh)

    assert content.device_revision.text == "1.00"
    controller.shutdown()


def test_device_info_never_raises_even_if_read_device_info_does(monkeypatch):
    def broken():
        raise RuntimeError("boom")

    monkeypatch.setattr("g6_gui.pages.system.read_device_info", broken)
    controller = G6Controller(FakeG6Api())
    content = system.build(controller)  # must not raise
    assert content.device_revision.text == "Not detected"
    controller.shutdown()


def test_device_info_present_on_macos_too(monkeypatch):
    """Device info is HID-based, not USB-AudioControl-based, so unlike the
    claim/reload controls it must show up even when AUDIO_INTERFACE_SUPPORTED
    is False (macOS)."""
    monkeypatch.setattr("g6_gui.pages.system.AUDIO_INTERFACE_SUPPORTED", False)
    monkeypatch.setattr("g6_gui.pages.system.read_device_info", lambda: DeviceInfo(present=False))
    controller = G6Controller(FakeG6Api())
    content = system.build(controller)
    assert hasattr(content, "device_revision")
    assert hasattr(content, "device_refresh")
    controller.shutdown()
