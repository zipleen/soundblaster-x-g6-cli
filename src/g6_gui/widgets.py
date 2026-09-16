"""Reusable widget rows shared by every page.

Every builder returns the row's container ``toga.Box``; the live interactive
widget is attached to it as a plain attribute (``.switch``, ``.slider``, ...)
so callers — and tests — can read and write ``.value`` directly.
"""

from __future__ import annotations

import textwrap

import toga
from toga.style.pack import CENTER, COLUMN, ROW, Pack

LABEL_WIDTH = 160

#: Toga labels do not wrap, so help text is pre-wrapped into one label per line.
HELP_WRAP_COLUMNS = 92

_NOTE_STYLE = Pack(color="#888888", font_size=11)
_WARNING_STYLE = Pack(color="#B25000", font_size=11)
# No explicit colour: inheriting the system label colour is the only thing that
# stays readable in both macOS light and dark appearance. A fixed grey that looks
# "muted" on white is nearly invisible on a dark background. Help text is
# distinguished by its smaller size and indentation instead.
_HELP_STYLE = Pack(font_size=11)
_INFO_BUTTON_STYLE = Pack(width=28, margin_left=4)


class _Page(toga.Box):
    """A page box whose ``add()`` targets its scrollable column.

    Without this, ``page()`` followed by ``content.add(row)`` would drop the row
    next to the ScrollContainer rather than inside it. Because the scroller is
    ``flex=1`` it expands and pushes those rows to the bottom of the window,
    leaving a large empty gap above them.
    """

    _column = None

    def add(self, *children: toga.Widget) -> None:
        if self._column is None:
            super().add(*children)
        else:
            self._column.add(*children)


def page(*children: toga.Widget) -> toga.Box:
    """A scrollable column page with margins."""
    column = toga.Box(style=Pack(direction=COLUMN, margin=10))
    scroller = toga.ScrollContainer(content=column, style=Pack(flex=1))
    outer = _Page(style=Pack(direction=COLUMN, flex=1))
    toga.Box.add(outer, scroller)
    outer._column = column
    for child in children:
        column.add(child)
    return outer


def section(title: str) -> toga.Box:
    """A titled column container. Add rows to it with ``.add(...)``."""
    box = toga.Box(style=Pack(direction=COLUMN, margin_bottom=10))
    heading = toga.Label(title, style=Pack(font_weight="bold", margin_bottom=5))
    box.add(heading)
    return box


def help_block(text: str) -> toga.Box:
    """A column of pre-wrapped labels rendering ``text``.

    Toga's Label does not wrap, so paragraphs are wrapped here and emitted one
    label per line. Blank lines in ``text`` become blank labels.
    """
    box = toga.Box(
        style=Pack(direction=COLUMN, margin_left=12, margin_bottom=8, margin_top=2)
    )
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        lines.extend(textwrap.wrap(paragraph, width=HELP_WRAP_COLUMNS) or [""])
    for line in lines:
        box.add(toga.Label(line, style=_HELP_STYLE))
    box.lines = lines
    return box


def help_for(container: toga.Box, *, anchor: toga.Box, text: str) -> toga.Button:
    """Add an (i) button to ``anchor`` that expands ``text`` at the end of ``container``.

    For multi-row controls (an SBX effect is a switch *and* a slider) the button
    belongs beside the label, but the help text belongs below the whole group —
    otherwise the explanation wedges itself between a switch and its slider.

    Returns the button; the help block is attached to ``container.help``.
    """
    block = help_block(text)
    state = {"shown": False}

    def toggle(widget, **_kwargs):
        if state["shown"]:
            container.remove(block)
            widget.text = INFO_GLYPH
        else:
            container.add(block)
            widget.text = CLOSE_GLYPH
        state["shown"] = not state["shown"]

    button = toga.Button(INFO_GLYPH, on_press=toggle, style=_INFO_BUTTON_STYLE)
    button.always_enabled = True
    anchor.add(button)
    container.info_button = button
    container.help = block
    container.help_shown = lambda: state["shown"]
    return button


def with_help(row: toga.Box, help_text: str | None) -> toga.Box:
    """Wrap ``row`` in a column carrying a toggleable (i) help block.

    Returns a column box whose first child is ``row``. Every attribute the row
    carried (``.switch``, ``.slider``, ...) is copied onto the returned box, so
    callers and tests keep using the same names either way.

    The help block is added and removed rather than merely hidden, so it takes
    no layout space while collapsed.
    """
    if not help_text:
        return row

    container = toga.Box(style=Pack(direction=COLUMN))
    container.add(row)
    help_for(container, anchor=row, text=help_text)

    for attr in ("switch", "slider", "readout", "selection", "buttons"):
        if hasattr(row, attr):
            setattr(container, attr, getattr(row, attr))
    container.control_row = row
    return container


INFO_GLYPH = "ⓘ"    # ⓘ
CLOSE_GLYPH = "✕"   # ✕


def switch_row(label: str, *, value: bool, on_change, help: str | None = None) -> toga.Box:
    row = toga.Box(style=Pack(direction=ROW, margin_bottom=5, align_items=CENTER))
    switch = toga.Switch(label, value=value, on_change=on_change)
    row.add(switch)
    row.switch = switch
    return with_help(row, help)


def _snap(raw: float, lo: int, hi: int, step: int):
    stepped = round(raw / step) * step
    if stepped < lo:
        return lo
    if stepped > hi:
        return hi
    return stepped


def slider_row(
    label: str,
    *,
    min: int,
    max: int,
    value: int,
    step: int = 1,
    on_change,
    help: str | None = None,
) -> toga.Box:
    lo, hi = min, max
    row = toga.Box(style=Pack(direction=ROW, margin_bottom=5, align_items=CENTER, gap=8))
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

    slider = toga.Slider(
        min=lo, max=hi, value=value, on_change=handle_change, style=Pack(flex=1)
    )

    row.add(caption)
    row.add(slider)
    row.add(readout)
    row.slider = slider
    row.readout = readout
    return with_help(row, help)


def select_row(
    label: str, *, items: list[str], value: str | None, on_change, help: str | None = None
) -> toga.Box:
    row = toga.Box(style=Pack(direction=ROW, margin_bottom=5, align_items=CENTER, gap=8))
    caption = toga.Label(label, style=Pack(width=LABEL_WIDTH))
    selection = toga.Selection(items=items, value=value, on_change=on_change)
    row.add(caption)
    row.add(selection)
    row.selection = selection
    return with_help(row, help)


def button_row(*buttons: tuple[str, object], help: str | None = None) -> toga.Box:
    row = toga.Box(style=Pack(direction=ROW, margin_bottom=5, align_items=CENTER))
    created = []
    for text, handler in buttons:
        button = toga.Button(text, on_press=handler)
        row.add(button)
        created.append(button)
    row.buttons = created
    return with_help(row, help)


def note(text: str) -> toga.Label:
    """A single-line grey label. Its ``.text`` can be reassigned later."""
    return toga.Label(text, style=_NOTE_STYLE)


def warning(text: str) -> toga.Label:
    """A single-line orange label. Its ``.text`` can be reassigned later."""
    return toga.Label(text, style=_WARNING_STYLE)


def _wrapped(text: str, style: Pack) -> toga.Box:
    box = toga.Box(style=Pack(direction=COLUMN, margin_bottom=6))
    lines = []
    for paragraph in text.split("\n"):
        lines.extend(textwrap.wrap(paragraph, width=HELP_WRAP_COLUMNS) or [""])
    for line in lines:
        box.add(toga.Label(line, style=style))
    box.lines = lines
    return box


def note_block(text: str) -> toga.Box:
    """Multi-line grey note. Use when the text is too long for one line."""
    return _wrapped(text, _NOTE_STYLE)


class _DynamicTextBlock(toga.Box):
    """A note_block()/warning_block() whose text can change after creation.

    Plain note()/warning() Labels support reassigning .text directly, but a
    wrapped block cannot -- it is a column of separate Label lines, and the
    number of lines a new message needs will not generally match the old one.
    This clears and rebuilds those child labels on set_text() instead.
    """

    def __init__(self, text: str, style_pack: Pack):
        super().__init__(style=Pack(direction=COLUMN, margin_bottom=6))
        self._style_pack = style_pack
        self.set_text(text)

    def set_text(self, text: str) -> None:
        for child in list(self.children):
            self.remove(child)
        if not text.strip():
            # No residual blank-line gap when there is nothing to say --
            # matters here specifically because this block is used for
            # conditional notes (e.g. "disabled because ...") that must be
            # able to disappear entirely, not just show an empty line, when
            # the condition they describe is not currently true.
            self.lines = []
            return
        lines = []
        for paragraph in text.split("\n"):
            lines.extend(textwrap.wrap(paragraph, width=HELP_WRAP_COLUMNS) or [""])
        for line in lines:
            self.add(toga.Label(line, style=self._style_pack))
        self.lines = lines


def dynamic_note_block(text: str = "") -> _DynamicTextBlock:
    """A note_block() that can be updated later via ``.set_text(...)``."""
    return _DynamicTextBlock(text, _NOTE_STYLE)


def dynamic_warning_block(text: str = "") -> _DynamicTextBlock:
    """A warning_block() that can be updated later via ``.set_text(...)``."""
    return _DynamicTextBlock(text, _WARNING_STYLE)


def warning_block(text: str) -> toga.Box:
    """Multi-line orange warning. Use when the text is too long for one line."""
    return _wrapped(text, _WARNING_STYLE)


def set_enabled(box: toga.Widget, enabled: bool) -> None:
    """Recursively enable/disable every interactive widget in a container.

    Descends through both ``children`` and ``content``. The ``content`` branch
    matters: ``page()`` wraps its rows in a ``ScrollContainer``, whose
    ``children`` is always empty because it holds a single ``content`` widget
    instead. Without that branch, disabling a whole page silently does nothing.

    Widgets carrying ``always_enabled`` are skipped. That is how the (i) help
    buttons survive their row being disabled, which is precisely when their
    explanation is most wanted.
    """
    for child in getattr(box, "children", None) or []:
        if hasattr(child, "enabled") and not getattr(child, "always_enabled", False):
            child.enabled = enabled
        set_enabled(child, enabled)

    content = getattr(box, "content", None)
    if isinstance(content, toga.Widget):
        if hasattr(content, "enabled") and not getattr(content, "always_enabled", False):
            content.enabled = enabled
        set_enabled(content, enabled)
