"""SBX [HID] — profile editing, effects and Smart Volume.

The G6 holds exactly one live SBX state. ``sbx_toggle``/``sbx_slider`` always
write that single state to the device regardless of the ``profile_name`` they
are given — that argument only selects which profile's entry is updated in the
persisted JSON model. ``sbx_profile_switch`` is the only call that replays a
profile's stored values back to the device and marks it active.

So this page tracks two independent things: the *editing* profile (which
profile edits are recorded against) and the *active* profile (what the device
is actually playing). Editing a non-active profile is audible immediately, but
is saved under the editing profile and will be overwritten the next time any
profile is switched. The banner exists to make that visible.
"""

from __future__ import annotations

import asyncio

import toga

from g6_cli.g6_model.sbx import Profile
from g6_cli.g6_spec import AudioFeature, SmartVolumeSpecialHex
from g6_gui import convert, widgets
from g6_gui.controller import G6Controller

TITLE = "SBX"

# attr, label, toggle feature, slider feature, toggle getter, slider getter
_EFFECTS = [
    (
        "surround",
        "Surround",
        AudioFeature.SURROUND_TOGGLE,
        AudioFeature.SURROUND_SLIDER,
        "get_surround_toggle",
        "get_surround_slider",
    ),
    (
        "crystalizer",
        "Crystalizer",
        AudioFeature.CRYSTALIZER_TOGGLE,
        AudioFeature.CRYSTALIZER_SLIDER,
        "get_crystalizer_toggle",
        "get_crystalizer_slider",
    ),
    (
        "bass",
        "Bass",
        AudioFeature.BASS_TOGGLE,
        AudioFeature.BASS_SLIDER,
        "get_bass_toggle",
        "get_bass_slider",
    ),
    (
        "smart_volume",
        "Smart Volume",
        AudioFeature.SMART_VOLUME_TOGGLE,
        AudioFeature.SMART_VOLUME_SLIDER,
        "get_smart_volume_toggle",
        "get_smart_volume_slider",
    ),
    (
        "dialog_plus",
        "Dialog Plus",
        AudioFeature.DIALOG_PLUS_TOGGLE,
        AudioFeature.DIALOG_PLUS_SLIDER,
        "get_dialog_plus_toggle",
        "get_dialog_plus_slider",
    ),
]


def is_available() -> bool:
    return True


def _banner_text(editing: Profile.Name, active: Profile.Name) -> str:
    if editing == active:
        return f"Active profile: {active.value}"
    return (
        f"Editing {editing.value} but {active.value} is active — changes are "
        f"audible now, but are saved under {editing.value} and will be replaced "
        "next time you switch profiles."
    )


def _special_label(value: SmartVolumeSpecialHex | None) -> str:
    if value is None:
        return "None"
    if value is SmartVolumeSpecialHex.SMART_VOLUME_NIGHT:
        return "Night"
    return "Loud"


def build(controller: G6Controller) -> toga.Widget:
    model = controller.model
    active_profile = model.get_sbx_profile_selection()

    # A mutable holder so every closure below reads the *current* editing
    # profile at send time rather than capturing it at build time.
    state = {"editing": active_profile}

    def editing_profile() -> Profile.Name:
        return state["editing"]

    content = widgets.page()

    banner = widgets.note(_banner_text(state["editing"], active_profile))

    def refresh_banner() -> None:
        current_active = model.get_sbx_profile_selection()
        banner.text = _banner_text(state["editing"], current_active)
        banner.style.color = (
            "#888888" if state["editing"] == current_active else "#B25000"
        )

    effect_rows: dict[str, toga.Box] = {}

    def make_effect_row(attr, label, toggle_feature, slider_feature, toggle_getter, slider_getter):
        sbx = model.get_sbx(profile_name=state["editing"])

        def on_toggle(widget):
            controller.submit(
                "sbx_toggle",
                profile_name=editing_profile(),
                audio_feature=toggle_feature,
                activate=widget.value,
                revert=lambda: setattr(widget, "value", not widget.value),
            )

        def on_slider(widget):
            controller.debounced(
                f"sbx_{attr}",
                "sbx_slider",
                profile_name=editing_profile(),
                audio_feature=slider_feature,
                value=int(widget.value),
            )

        toggle = widgets.switch_row(label, value=getattr(sbx, toggle_getter)(), on_change=on_toggle)
        # The switch already carries the effect's name; repeating it on the
        # slider row just prints "Bass" twice under itself.
        slider = widgets.slider_row(
            "",
            min=0,
            max=100,
            value=getattr(sbx, slider_getter)(),
            step=1,
            on_change=on_slider,
        )

        row = toga.Box(style=toga.style.pack.Pack(direction=toga.style.pack.COLUMN, margin_bottom=8))
        row.add(toggle)
        row.add(slider)
        row.toggle = toggle
        row.slider = slider
        return row

    def on_editing_change(widget) -> None:
        new_profile = convert.profile_from_label(widget.value)
        state["editing"] = new_profile
        sbx = model.get_sbx(profile_name=new_profile)

        for attr, _label, _toggle_feature, _slider_feature, toggle_getter, slider_getter in _EFFECTS:
            row = effect_rows[attr]
            row.toggle.switch.value = getattr(sbx, toggle_getter)()
            row.slider.slider.value = getattr(sbx, slider_getter)()

        special = sbx.get_smart_volume_special()
        smart_volume_special.selection.value = _special_label(special)
        widgets.set_enabled(effect_rows["smart_volume"].slider, special is None)

        refresh_banner()

    editing = widgets.select_row(
        "Editing profile",
        items=convert.PROFILE_LABELS,
        value=state["editing"].value,
        on_change=on_editing_change,
    )

    def on_switch_press(widget, *_args, **_kwargs) -> None:
        target = editing_profile()
        controller.submit("sbx_profile_switch", profile_name=target)

        async def refresh_after_switch():
            await controller.flush()
            refresh_banner()

        asyncio.ensure_future(refresh_after_switch())

    switch_button = toga.Button("Switch to this profile", on_press=on_switch_press)
    switch_button_row = toga.Box(
        style=toga.style.pack.Pack(direction=toga.style.pack.ROW, margin_bottom=12)
    )
    switch_button_row.add(switch_button)

    content.add(editing)
    content.add(banner)
    content.add(switch_button_row)

    for attr, label, toggle_feature, slider_feature, toggle_getter, slider_getter in _EFFECTS:
        row = make_effect_row(attr, label, toggle_feature, slider_feature, toggle_getter, slider_getter)
        effect_rows[attr] = row
        content.add(row)
        setattr(content, attr, row)

    def on_smart_volume_special_change(widget) -> None:
        special = convert.smart_volume_special_from_label(widget.value)
        smart_volume_slider = effect_rows["smart_volume"].slider
        if special is None:
            widgets.set_enabled(smart_volume_slider, True)
            return
        widgets.set_enabled(smart_volume_slider, False)
        controller.submit(
            "sbx_smart_volume_special",
            profile_name=editing_profile(),
            smart_volume_special_hex=special,
        )

    initial_sbx = model.get_sbx(profile_name=state["editing"])
    initial_special = initial_sbx.get_smart_volume_special()
    smart_volume_special = widgets.select_row(
        "Smart Volume special",
        items=convert.SMART_VOLUME_LABELS,
        value=_special_label(initial_special),
        on_change=on_smart_volume_special_change,
    )
    widgets.set_enabled(effect_rows["smart_volume"].slider, initial_special is None)
    content.add(smart_volume_special)

    content.editing = editing
    content.banner = banner
    content.switch_button = switch_button
    content.smart_volume_special = smart_volume_special

    return content
