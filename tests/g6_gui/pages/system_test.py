from __future__ import annotations

import pytest

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
