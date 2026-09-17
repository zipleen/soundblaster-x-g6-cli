"""A scriptable fake of g6_gui.coreaudio.Hal, for testing ClockController and
the macOS Audio page without any real Core Audio device -- mirrors the
fake_api.py FakeG6Api pattern already used for the rest of this test suite.
"""

from __future__ import annotations

from g6_gui.coreaudio import ClockSource, Format, Hal


class FakeHal(Hal):
    """A single scripted device, with settable clock source and format.

    ``devices`` maps device_id -> {"name": str, "clock_sources": list[ClockSource]}.
    Only one device (id 1) is present by default, shaped like a real G6.
    """

    _UNSET = object()

    def __init__(
        self,
        *,
        clock_sources=_UNSET,
        current_clock_source_code: int = 0,
        formats_by_clock_source: dict[int, list[Format]] | None = None,
        current_format: Format | None = None,
        device_name: str = "Fake G6",
        present: bool = True,
        output_volume: float | None = 0.8,
        output_volume_db: float | None = None,
    ):
        self.device_id = 1
        self.stream_id = 10
        self.device_name_value = device_name
        self.present = present
        self.clock_sources_value = (
            [ClockSource(code=0, name="DSP Clock"), ClockSource(code=1, name="Stereo Direct")]
            if clock_sources is self._UNSET
            else clock_sources  # None here means "property absent", a real, distinct case
        )
        self.current_code = current_clock_source_code
        # Per-clock-source format menus, keyed by code -- mirrors the real
        # device's behaviour of offering different formats depending on which
        # clock source is active (that is exactly why the switch-back gotcha
        # this module works around exists at all).
        self.formats_by_code = formats_by_clock_source or {
            0: [Format(44100.0, 24, 2), Format(48000.0, 24, 2), Format(48000.0, 32, 2)],
            1: [
                Format(44100.0, 24, 2), Format(48000.0, 24, 2), Format(96000.0, 24, 2),
                Format(192000.0, 32, 2), Format(384000.0, 32, 2),
            ],
        }
        self.current_format_value = current_format or self.formats_by_code[current_clock_source_code][1]

        # None means "no host-settable volume at all" -- a distinct, real
        # case tests can opt into explicitly; the 0.8 default keeps every
        # existing test (written before volume reading existed) exercising
        # a plain, non-full-scale reading rather than an untested None.
        self.output_volume_value = output_volume

        # dB reading, mirroring output_volume above. Defaults to None --
        # "vold unreachable" -- rather than some default that would exercise
        # the dB path automatically in every existing test, which was
        # written before this field existed. Tests that want the dB path
        # (the whole point of task 3 here) pass this explicitly.
        self.output_volume_db_value = output_volume_db

        self.calls: list[tuple[str, dict]] = []
        self.reject_clock_source_set = False  # simulate a set() that silently does not take
        self.reject_format_set = False

        # Simulates a real, confirmed-live behaviour: current_clock_source_code
        # flips essentially instantly on a real G6, but the stream's
        # available-format list lags behind by a handful of reads before
        # catching up to the new clock source's own list. 0 (the default)
        # means no lag -- the list is correct immediately, as it always is
        # against the fake devices used elsewhere in this test file.
        self.format_settle_delay_reads = 0
        self._stale_formats: list[Format] | None = None
        self._stale_reads_remaining = 0

    def _record(self, name: str, **kwargs) -> None:
        self.calls.append((name, kwargs))

    def find_devices(self) -> list[int]:
        self._record("find_devices")
        return [self.device_id] if self.present else []

    def device_name(self, device_id: int) -> str:
        self._record("device_name", device_id=device_id)
        return self.device_name_value

    def clock_sources(self, device_id: int) -> list[ClockSource] | None:
        self._record("clock_sources", device_id=device_id)
        return self.clock_sources_value

    def current_clock_source_code(self, device_id: int) -> int:
        self._record("current_clock_source_code", device_id=device_id)
        return self.current_code

    def set_clock_source_code(self, device_id: int, code: int) -> None:
        self._record("set_clock_source_code", device_id=device_id, code=code)
        if self.reject_clock_source_set:
            return  # simulates Core Audio silently not applying the change
        old_code = self.current_code
        self.current_code = code
        # A real device offers a different format menu per clock source, and
        # resets to something of its own choosing on switch -- pick the first
        # entry, deterministically, same as observed on BlackHole.
        self.current_format_value = self.formats_by_code[code][0]
        if self.format_settle_delay_reads > 0:
            self._stale_formats = self.formats_by_code[old_code]
            self._stale_reads_remaining = self.format_settle_delay_reads

    def output_streams(self, device_id: int) -> list[int]:
        self._record("output_streams", device_id=device_id)
        return [self.stream_id]

    def current_format(self, stream_id: int) -> Format:
        self._record("current_format", stream_id=stream_id)
        return self.current_format_value

    def available_formats(self, stream_id: int) -> list[Format]:
        self._record("available_formats", stream_id=stream_id)
        if self._stale_reads_remaining > 0:
            self._stale_reads_remaining -= 1
            return self._stale_formats
        return self.formats_by_code[self.current_code]

    def set_format(self, stream_id: int, fmt: Format) -> None:
        self._record("set_format", stream_id=stream_id, fmt=fmt)
        if self.reject_format_set:
            return
        self.current_format_value = fmt

    def output_volume(self, device_id: int) -> float | None:
        self._record("output_volume", device_id=device_id)
        return self.output_volume_value

    def output_volume_db(self, device_id: int) -> float | None:
        self._record("output_volume_db", device_id=device_id)
        return self.output_volume_db_value
