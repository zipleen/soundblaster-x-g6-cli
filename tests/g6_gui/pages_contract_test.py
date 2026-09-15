from __future__ import annotations

import toga
import pytest

from g6_gui import pages
from g6_gui.controller import G6Controller
from tests.g6_gui.fake_api import FakeG6Api


def test_all_pages_are_registered_in_display_order():
    titles = [module.TITLE for module in pages.ALL]
    assert titles == ["Playback", "Mixer", "Recording", "SBX", "Lighting", "System"]


@pytest.mark.parametrize("module", pages.ALL, ids=lambda m: m.TITLE)
def test_every_page_satisfies_the_contract(module):
    assert isinstance(module.TITLE, str)
    assert isinstance(module.is_available(), bool)
    controller = G6Controller(FakeG6Api())
    content = module.build(controller)
    assert isinstance(content, toga.Widget)
    controller.shutdown()


def test_mixer_is_hidden_when_the_audio_interface_is_unsupported(monkeypatch):
    from g6_gui.pages import mixer

    monkeypatch.setattr("g6_gui.pages.mixer.AUDIO_INTERFACE_SUPPORTED", False)
    assert mixer.is_available() is False
