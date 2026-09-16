"""Lighting [HID] — RGB control."""

from __future__ import annotations

import toga
from toga.style.pack import Pack

from g6_gui import help as help_text, widgets
from g6_gui.controller import G6Controller

TITLE = "Lighting"

_DEBOUNCE_KEY = "lighting_rgb"


def is_available() -> bool:
    return True


def build(controller: G6Controller) -> toga.Widget:
    lighting = controller.model.get_lighting()
    initial_enabled = lighting.get_enabled()
    initial_red, initial_green, initial_blue = lighting.get_rgb()

    swatch = toga.Box(style=Pack(width=120, height=28, background_color=_hex_colour(
        initial_red, initial_green, initial_blue
    )))

    def current_rgb() -> tuple[int, int, int]:
        return (
            int(red_row.slider.value),
            int(green_row.slider.value),
            int(blue_row.slider.value),
        )

    def update_swatch():
        swatch.style.background_color = _hex_colour(*current_rgb())

    def send_rgb():
        red, green, blue = current_rgb()
        controller.debounced(
            _DEBOUNCE_KEY,
            "lighting_enable_set_rgb",
            red=red,
            green=green,
            blue=blue,
        )

    def on_enabled_change(widget):
        widgets.set_enabled(rgb_section, widget.value)
        if widget.value:
            send_rgb()
        else:
            controller.submit("lighting_disable")

    def on_rgb_change(widget):
        update_swatch()
        if enabled_row.switch.value:
            send_rgb()

    enabled_row = widgets.switch_row(
        "Enabled",
        value=initial_enabled,
        on_change=on_enabled_change,
        help=help_text.LIGHTING_ENABLED,
    )

    red_row = widgets.slider_row(
        "Red",
        min=0,
        max=255,
        value=initial_red,
        on_change=on_rgb_change,
        help=help_text.LIGHTING_COLOUR,
    )
    green_row = widgets.slider_row(
        "Green", min=0, max=255, value=initial_green, on_change=on_rgb_change
    )
    blue_row = widgets.slider_row(
        "Blue", min=0, max=255, value=initial_blue, on_change=on_rgb_change
    )

    rgb_section = widgets.section("Colour")
    rgb_section.add(red_row)
    rgb_section.add(green_row)
    rgb_section.add(blue_row)
    rgb_section.add(swatch)
    widgets.set_enabled(rgb_section, initial_enabled)

    content = widgets.page(enabled_row, rgb_section)
    content.lighting_enabled = enabled_row
    content.red = red_row
    content.green = green_row
    content.blue = blue_row
    content.swatch = swatch
    return content


def _hex_colour(red: int, green: int, blue: int) -> str:
    return f"#{red:02x}{green:02x}{blue:02x}"
