from __future__ import annotations

import pytest

from travertino.colors import rgb

from g6_gui.controller import G6Controller
from g6_gui.pages import lighting
from tests.g6_gui.fake_api import FakeG6Api


@pytest.fixture
def built():
    api = FakeG6Api()
    controller = G6Controller(api)
    content = lighting.build(controller)
    yield api, controller, content
    controller.shutdown()


async def test_turning_lighting_off_disables_it(built):
    api, controller, content = built
    content.lighting_enabled.switch.value = True
    await controller.flush()
    api.calls.clear()
    content.lighting_enabled.switch.value = False
    await controller.flush()
    assert api.calls == [("lighting_disable", {})]


async def test_turning_lighting_on_sends_current_rgb(built):
    api, controller, content = built
    content.lighting_enabled.switch.value = True
    await controller.flush()
    assert api.calls[-1][0] == "lighting_enable_set_rgb"
    assert set(api.calls[-1][1]) == {"red", "green", "blue"}


def test_rgb_sliders_are_disabled_while_lighting_is_off(built):
    _, _, content = built
    assert content.red.slider.enabled is False
    content.lighting_enabled.switch.value = True
    assert content.red.slider.enabled is True


async def test_rgb_changes_coalesce_into_a_single_write(built):
    api, controller, content = built
    content.lighting_enabled.switch.value = True
    await controller.flush()
    api.calls.clear()
    content.red.slider.value = 255
    content.green.slider.value = 128
    content.blue.slider.value = 64
    await controller.flush()
    assert api.calls == [
        ("lighting_enable_set_rgb", {"red": 255, "green": 128, "blue": 64})
    ]


def test_swatch_tracks_the_selected_colour(built):
    _, _, content = built
    content.lighting_enabled.switch.value = True
    content.red.slider.value = 255
    content.green.slider.value = 0
    content.blue.slider.value = 0
    assert content.swatch.style.background_color == rgb(255, 0, 0)
