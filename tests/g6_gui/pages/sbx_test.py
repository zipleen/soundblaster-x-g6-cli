from __future__ import annotations

import pytest

from g6_cli.g6_model import G6Model
from g6_cli.g6_model.sbx import Profile
from g6_cli.g6_spec import AudioFeature, SmartVolumeSpecialHex
from g6_gui.controller import G6Controller
from g6_gui.pages import sbx
from tests.g6_gui.fake_api import FakeG6Api

EFFECTS = [
    ("surround", AudioFeature.SURROUND_TOGGLE, AudioFeature.SURROUND_SLIDER),
    ("crystalizer", AudioFeature.CRYSTALIZER_TOGGLE, AudioFeature.CRYSTALIZER_SLIDER),
    ("bass", AudioFeature.BASS_TOGGLE, AudioFeature.BASS_SLIDER),
    ("smart_volume", AudioFeature.SMART_VOLUME_TOGGLE, AudioFeature.SMART_VOLUME_SLIDER),
    ("dialog_plus", AudioFeature.DIALOG_PLUS_TOGGLE, AudioFeature.DIALOG_PLUS_SLIDER),
]


@pytest.fixture
def built():
    api = FakeG6Api()
    controller = G6Controller(api)
    content = sbx.build(controller)
    yield api, controller, content
    controller.shutdown()


def test_editing_defaults_to_the_active_profile(built):
    _, controller, content = built
    assert content.editing.selection.value == controller.model.get_sbx_profile_selection().value


@pytest.mark.parametrize("attr,toggle,_slider", EFFECTS, ids=[e[0] for e in EFFECTS])
async def test_effect_toggle_sends_the_editing_profile(built, attr, toggle, _slider):
    api, controller, content = built
    content.editing.selection.value = "Music"
    getattr(content, attr).toggle.switch.value = True
    await controller.flush()
    assert api.calls[-1] == (
        "sbx_toggle",
        {"profile_name": Profile.Name.MUSIC, "audio_feature": toggle, "activate": True},
    )


@pytest.mark.parametrize("attr,_toggle,slider", EFFECTS, ids=[e[0] for e in EFFECTS])
async def test_effect_slider_sends_the_editing_profile_and_debounces(built, attr, _toggle, slider):
    api, controller, content = built
    content.editing.selection.value = "Cinema"
    effect = getattr(content, attr)
    effect.slider.slider.value = 20
    effect.slider.slider.value = 35
    await controller.flush()
    assert api.calls[-1] == (
        "sbx_slider",
        {"profile_name": Profile.Name.CINEMA, "audio_feature": slider, "value": 35},
    )


async def test_changing_editing_profile_sends_nothing_to_the_device(built):
    api, controller, content = built
    content.editing.selection.value = "Special"
    await controller.flush()
    assert api.method_names() == []


async def test_switch_button_switches_the_profile(built):
    api, controller, content = built
    content.editing.selection.value = "Cinema"
    content.switch_button.on_press()
    await controller.flush()
    assert ("sbx_profile_switch", {"profile_name": Profile.Name.CINEMA}) in api.calls


def test_banner_warns_when_editing_a_non_active_profile(built):
    _, _, content = built
    active = content.editing.selection.value
    other = "Music" if active != "Music" else "Cinema"
    content.editing.selection.value = other
    assert "will be replaced" in content.banner.text
    assert other in content.banner.text and active in content.banner.text


def test_banner_is_calm_when_editing_the_active_profile(built):
    _, controller, content = built
    active = controller.model.get_sbx_profile_selection().value
    assert content.banner.text == f"Active profile: {active}"


async def test_smart_volume_special_supersedes_the_slider(built):
    api, controller, content = built
    content.smart_volume_special.selection.value = "Night"
    await controller.flush()
    assert api.calls[-1][0] == "sbx_smart_volume_special"
    assert api.calls[-1][1]["smart_volume_special_hex"] is SmartVolumeSpecialHex.SMART_VOLUME_NIGHT
    assert content.smart_volume.slider.slider.enabled is False


async def test_choosing_none_re_enables_the_smart_volume_slider(built):
    _, controller, content = built
    content.smart_volume_special.selection.value = "Night"
    content.smart_volume_special.selection.value = "None"
    await controller.flush()
    assert content.smart_volume.slider.slider.enabled is True


# ── Regression: changing the editing profile must not write to the device ───
#
# Toga's Cocoa backend fires on_change for a *programmatic* ``widget.value = x``
# (toga_cocoa/widgets/switch.py calls ``self.interface.on_change()`` whenever the
# value actually changes). Repopulating the controls therefore used to submit
# every differing value, silently performing the profile switch that the
# "Switch to this profile" button is meant to do.
#
# These tests need profiles that genuinely differ: with the default model all
# four are identical, nothing changes, and no handler would fire either way.


def _model_with_distinct_cinema():
    model = G6Model()
    cinema = model.get_sbx(profile_name=Profile.Name.CINEMA)
    cinema.set_surround_toggle(True)
    cinema.set_surround_slider(80)
    cinema.set_bass_toggle(True)
    cinema.set_bass_slider(70)
    return model


@pytest.mark.asyncio
async def test_changing_editing_profile_sends_nothing():
    api = FakeG6Api(model=_model_with_distinct_cinema())
    controller = G6Controller(api)
    page = sbx.build(controller)
    api.calls.clear()

    page.editing.selection.value = "Cinema"
    await controller.flush()

    assert api.calls == []


@pytest.mark.asyncio
async def test_changing_editing_profile_still_repopulates_the_controls():
    api = FakeG6Api(model=_model_with_distinct_cinema())
    controller = G6Controller(api)
    page = sbx.build(controller)

    page.editing.selection.value = "Cinema"
    await controller.flush()

    assert page.surround.toggle.switch.value is True
    assert page.surround.slider.slider.value == 80
    assert page.bass.slider.slider.value == 70


@pytest.mark.asyncio
async def test_switching_profile_still_writes_after_browsing():
    """The button must keep working once the dropdown has been moved."""
    api = FakeG6Api(model=_model_with_distinct_cinema())
    controller = G6Controller(api)
    page = sbx.build(controller)

    page.editing.selection.value = "Cinema"
    await controller.flush()
    api.calls.clear()

    page.switch_button.on_press()
    await controller.flush()

    assert ("sbx_profile_switch", {"profile_name": Profile.Name.CINEMA}) in api.calls
