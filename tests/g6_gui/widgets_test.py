from __future__ import annotations

from g6_gui import widgets


def test_switch_row_exposes_switch_and_initial_value():
    row = widgets.switch_row("Direct Mode", value=True, on_change=lambda w: None)
    assert row.switch.value is True
    assert row.switch.text == "Direct Mode"


def test_switch_row_invokes_handler_on_change():
    seen = []
    row = widgets.switch_row("Direct Mode", value=False, on_change=lambda w: seen.append(w.value))
    row.switch.value = True
    assert seen == [True]


def test_slider_row_snaps_to_step_and_updates_readout():
    seen = []
    row = widgets.slider_row(
        "Volume", min=0, max=100, value=0, step=10, on_change=lambda w: seen.append(w.value)
    )
    row.slider.value = 44
    assert row.slider.value == 40
    assert row.readout.text == "40"
    assert seen[-1] == 40


def test_slider_row_without_step_keeps_exact_value():
    row = widgets.slider_row("Bass", min=0, max=100, value=50, on_change=lambda w: None)
    row.slider.value = 37
    assert row.slider.value == 37
    assert row.readout.text == "37"


def test_select_row_exposes_items_and_value():
    row = widgets.select_row(
        "Filter", items=["A", "B"], value="B", on_change=lambda w: None
    )
    assert row.selection.value == "B"


def test_set_enabled_reaches_nested_widgets():
    container = widgets.section("Mixer")
    row = widgets.slider_row("Line In", min=0, max=100, value=0, on_change=lambda w: None)
    container.add(row)
    widgets.set_enabled(container, False)
    assert row.slider.enabled is False
    widgets.set_enabled(container, True)
    assert row.slider.enabled is True
