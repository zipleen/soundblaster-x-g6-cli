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


def test_set_enabled_descends_through_a_scroll_container():
    """page() wraps rows in a ScrollContainer whose .children is always empty."""
    inner = widgets.section("Mixer")
    row = widgets.slider_row("Line In", min=0, max=100, value=0, on_change=lambda w: None)
    inner.add(row)
    content = widgets.page(inner)

    widgets.set_enabled(content, False)
    assert row.slider.enabled is False

    widgets.set_enabled(content, True)
    assert row.slider.enabled is True


# ── (i) help blocks ─────────────────────────────────────────────────────────


def test_row_without_help_has_no_info_button():
    row = widgets.switch_row("Direct Mode", value=False, on_change=lambda w: None)
    assert not hasattr(row, "info_button")
    assert row.switch.text == "Direct Mode"


def test_help_block_wraps_long_text_into_labels():
    block = widgets.help_block("word " * 80)
    assert len(block.lines) > 1
    assert all(len(line) <= widgets.HELP_WRAP_COLUMNS for line in block.lines)


def test_help_block_preserves_blank_lines_between_paragraphs():
    block = widgets.help_block("first\n\nsecond")
    assert block.lines == ["first", "", "second"]


def test_info_button_toggles_help_in_and_out_of_the_tree():
    row = widgets.switch_row(
        "Direct Mode", value=False, on_change=lambda w: None, help="Explanation."
    )
    # Collapsed: the help block takes no space in the tree at all.
    assert row.help not in row.children
    assert row.info_button.text == widgets.INFO_GLYPH

    row.info_button.on_press()
    assert row.help in row.children
    assert row.info_button.text == widgets.CLOSE_GLYPH

    row.info_button.on_press()
    assert row.help not in row.children
    assert row.info_button.text == widgets.INFO_GLYPH


def test_help_wrapper_still_exposes_the_live_widget():
    switch = widgets.switch_row("A", value=True, on_change=lambda w: None, help="h")
    assert switch.switch.value is True

    slider = widgets.slider_row(
        "B", min=0, max=100, value=40, step=10, on_change=lambda w: None, help="h"
    )
    assert slider.slider.value == 40
    assert slider.readout.text == "40"

    select = widgets.select_row(
        "C", items=["A", "B"], value="B", on_change=lambda w: None, help="h"
    )
    assert select.selection.value == "B"


def test_set_enabled_reaches_controls_behind_a_help_wrapper():
    row = widgets.slider_row(
        "B", min=0, max=100, value=40, on_change=lambda w: None, help="h"
    )
    widgets.set_enabled(row, False)
    assert row.slider.enabled is False
    widgets.set_enabled(row, True)
    assert row.slider.enabled is True


def test_dynamic_note_block_can_be_retexted_with_a_different_number_of_lines():
    block = widgets.dynamic_note_block("short")
    assert block.lines == ["short"]

    block.set_text("word " * 80)
    assert len(block.lines) > 1
    assert all(len(line) <= widgets.HELP_WRAP_COLUMNS for line in block.lines)

    block.set_text("back to short")
    assert block.lines == ["back to short"]


def test_dynamic_warning_block_uses_the_warning_style():
    block = widgets.dynamic_warning_block("careful")
    assert block.children[0].style.color == widgets._WARNING_STYLE.color
