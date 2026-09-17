"""The Non-Over-Sampling (NOS) playback filter -- offered by the device,
hidden by Creative's own app, and *not* a member of upstream's
``PlaybackFilter`` enum.

## Why a shim instead of an enum member

``PlaybackFilter`` lives in ``src/g6_cli/g6_spec/__init__.py``, which is a
frozen upstream mirror -- see ``HANDOFF.md`` §2, rule 1: "Never modify
``src/g6_cli/``." (Verified throughout this change with
``git diff f0faf3a HEAD -- src/g6_cli`` staying empty.) Adding a member to
that enum would mean editing that file, so the fifth filter cannot become a
real ``PlaybackFilter`` value without breaking that rule.

## Why a shim is possible at all

``docs/g6-re/docs/fw_notes.md`` ("DAC FILTERS -- full decode") establishes
that the G6's DAC (a Cirrus Logic CS43131) has a fifth, fully functional
filter -- Non-Over-Sampling, SoundCore code 5, wire payload ``0003`` -- that
Creative's own Windows app hard-skips *by name* when it builds its filter
list (``BaseFiltersPageViewModel.InitializeSetupDACFilter``). Nothing about
NOS is unsupported by the device or the firmware; it is only absent from the
vendor GUI.

Both call sites that matter were read to confirm they never check the type
of what they are given, only its ``.value``:

- ``g6_spec.playback.playback_filter()`` (``src/g6_cli/g6_spec/playback.py``)
  does exactly one thing with its argument: ``intermediate=playback_filter_enum.value``.
- ``G6Api.playback_filter()`` (``src/g6_cli/g6_api/__init__.py``) passes the
  argument straight into the function above.

So an object that merely duck-types a ``.value`` attribute equal to
``bytes.fromhex('0003')`` reaches the wire exactly like a real
``PlaybackFilter`` member would, with no upstream edit required.

## The caveat this shim does NOT paper over

``G6Model.get_playback().set_filter()`` (``src/g6_cli/g6_model/playback.py``)
*does* check the type of what it is given:

    if not isinstance(playback_filter_enum, PlaybackFilter):
        raise ValueError(...)

``G6Api.playback_filter()`` calls this -- **after** already writing the
correct bytes to the wire -- only when the api was constructed with
``persist_model=True``, which is the GUI's default
(``g6_gui/app.py``: ``persist_model=not args.no_persist``). So on real
hardware, with default settings, selecting NOS:

1. Correctly sets the filter on the device (the HID write already happened).
2. Then raises ``ValueError`` out of the model-persistence step.
3. ``g6_gui.controller.G6Controller._guarded()`` treats that as a generic
   failure: it reverts the dropdown and shows an error banner, even though
   the device already applied the change -- and ``g6.json`` is left holding
   the previous filter, not NOS.

This is a real, load-bearing limitation of the pass-through approach, not
something fixed here by touching ``src/g6_cli``. It was surfaced rather than
patched around; see HANDOFF.md-style notes in the PR/commit description.
Only ``--no-persist`` (or a future non-upstream persistence layer) avoids it.
"""

from __future__ import annotations

#: Wire payload for the NOS filter, per fw_notes.md's decode:
#: SoundCore code 5 (NonOverSampling) minus 2 == 0x0003.
NOS_PAYLOAD = bytes.fromhex("0003")


class _NonOverSamplingFilter:
    """Duck-types the one attribute upstream reads off a ``PlaybackFilter``.

    Deliberately *not* a ``PlaybackFilter`` member and not an ``Enum`` at
    all -- see the module docstring for why it can't be, and where that
    stops working (``G6Model.set_filter``'s ``isinstance`` check).
    """

    value = NOS_PAYLOAD

    def __repr__(self) -> str:  # pragma: no cover - cosmetic only
        return "NON_OVERSAMPLING"


#: Singleton -- pages and tests import and compare this one instance.
NON_OVERSAMPLING = _NonOverSamplingFilter()
