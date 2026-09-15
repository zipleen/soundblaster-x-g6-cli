"""Reusable widget rows shared by every page.

Every builder returns the row's container ``toga.Box``; the live interactive
widget is attached to it as a plain attribute (``.switch``, ``.slider``, ...)
so callers — and tests — can read and write ``.value`` directly.
"""

from __future__ import annotations

import toga
from toga.style.pack import COLUMN, ROW, Pack

LABEL_WIDTH = 160

_NOTE_STYLE = Pack(color="#888888", font_size=11)
_WARNING_STYLE = Pack(color="#B25000", font_size=11)


def page(*children: toga.Widget) -> toga.Box:
    """A scrollable column page with margins."""
    column = toga.Box(style=Pack(direction=COLUMN, margin=10))
    for child in children:
        column.add(child)
    scroller = toga.ScrollContainer(content=column, style=Pack(flex=1))
    outer = toga.Box(style=Pack(direction=COLUMN, flex=1))
    outer.add(scroller)
    return outer


def section(title: str) -> toga.Box:
    """A titled column container. Add rows to it with ``.add(...)``."""
    box = toga.Box(style=Pack(direction=COLUMN, margin_bottom=10))
    heading = toga.Label(title, style=Pack(font_weight="bold", margin_bottom=5))
    box.add(heading)
    return box


def switch_row(label: str, *, value: bool, on_change) -> toga.Box:
    row = toga.Box(style=Pack(direction=ROW, margin_bottom=5))
    switch = toga.Switch(label, value=value, on_change=on_change)
    row.add(switch)
    row.switch = switch
    return row


def _snap(raw: float, lo: int, hi: int, step: int):
    stepped = round(raw / step) * step
    if stepped < lo:
        return lo
    if stepped > hi:
        return hi
    return stepped


def slider_row(
    label: str, *, min: int, max: int, value: int, step: int = 1, on_change
) -> toga.Box:
    lo, hi = min, max
    row = toga.Box(style=Pack(direction=ROW, margin_bottom=5))
    caption = toga.Label(label, style=Pack(width=LABEL_WIDTH))
    readout = toga.Label(str(value), style=Pack(width=48, text_align="right"))

    snapping = False

    def handle_change(widget):
        nonlocal snapping
        if snapping:
            return
        current = widget.value
        snapped = _snap(current, lo, hi, step)
        if snapped != current:
            snapping = True
            try:
                widget.value = snapped
            finally:
                snapping = False
        readout.text = str(snapped)
        on_change(widget)

    slider = toga.Slider(min=lo, max=hi, value=value, on_change=handle_change)

    row.add(caption)
    row.add(slider)
    row.add(readout)
    row.slider = slider
    row.readout = readout
    return row


def select_row(label: str, *, items: list[str], value: str | None, on_change) -> toga.Box:
    row = toga.Box(style=Pack(direction=ROW, margin_bottom=5))
    caption = toga.Label(label, style=Pack(width=LABEL_WIDTH))
    selection = toga.Selection(items=items, value=value, on_change=on_change)
    row.add(caption)
    row.add(selection)
    row.selection = selection
    return row


def button_row(*buttons: tuple[str, object]) -> toga.Box:
    row = toga.Box(style=Pack(direction=ROW, margin_bottom=5))
    created = []
    for text, handler in buttons:
        button = toga.Button(text, on_press=handler)
        row.add(button)
        created.append(button)
    row.buttons = created
    return row


def note(text: str) -> toga.Label:
    return toga.Label(text, style=_NOTE_STYLE)


def warning(text: str) -> toga.Label:
    return toga.Label(text, style=_WARNING_STYLE)


def set_enabled(box: toga.Widget, enabled: bool) -> None:
    """Recursively enable/disable every interactive widget in a container.

    Descends through both ``children`` and ``content``. The ``content`` branch
    matters: ``page()`` wraps its rows in a ``ScrollContainer``, whose
    ``children`` is always empty because it holds a single ``content`` widget
    instead. Without that branch, disabling a whole page silently does nothing.
    """
    for child in getattr(box, "children", None) or []:
        if hasattr(child, "enabled"):
            child.enabled = enabled
        set_enabled(child, enabled)

    content = getattr(box, "content", None)
    if isinstance(content, toga.Widget):
        if hasattr(content, "enabled"):
            content.enabled = enabled
        set_enabled(content, enabled)
