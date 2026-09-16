"""Read and switch the G6's clock source and stream format via macOS Core Audio.

This is what "Audio MIDI Setup" itself is doing under the hood: Clock Source
and Format are ordinary Core Audio HAL properties (``kAudioDevicePropertyClockSource``
and ``kAudioStreamPropertyPhysicalFormat``), settable through the same public
API any audio application uses. See docs/settings-reference.md for why this
matters -- on macOS, Direct Mode is not controlled by the G6's own USB HID
protocol at all; it is controlled here.

Every FourCC selector and struct layout below was read directly out of this
machine's Xcode SDK headers, not from memory or an online mirror:

    .../MacOSX.sdk/System/Library/Frameworks/CoreAudio.framework/Versions/A/Headers/AudioHardware.h
    .../MacOSX.sdk/System/Library/Frameworks/CoreAudio.framework/Versions/A/Headers/AudioHardwareBase.h
    .../MacOSX.sdk/System/Library/Frameworks/CoreAudioTypes.framework/Versions/A/Headers/CoreAudioBaseTypes.h

The mechanism itself -- device enumeration, CFString name extraction, clock
source enumeration/translation/get/set, and stream physical-format get/set,
including the nested AudioStreamRangedDescription array that is the most
structurally fragile part of this -- was exercised end to end against real
Core Audio devices on this machine (BlackHole 2ch, which genuinely implements
multiple clock sources, plus the built-in speakers/mic) before this module was
written, including full write/readback round trips. See HANDOFF.md.

What was **not** validated, because no G6 was attached while this was written:
the specific clock source names/codes and format list the G6's own driver
reports. This module does not assume any of that -- it identifies the device
by the one thing we know for certain from Creative's own documentation: it is
the only audio device whose clock sources are named exactly "DSP Clock" and
"Stereo Direct". Anything that does not match that shape is treated as
unsupported and left alone rather than guessed at.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import time
from dataclasses import dataclass, field

DSP_CLOCK = "DSP Clock"
STEREO_DIRECT = "Stereo Direct"

# The known-safe format for the handoff back to DSP Clock. Reproduces, in code,
# the manual recovery Luis found by hand: DSP Clock cannot do the sample rates
# Stereo Direct allows, and switching clock source does not renegotiate the
# stream format for you, so the format must be dropped first or audio breaks
# until it is set manually. 24-bit/48kHz is both Creative's documented DSP
# Clock ceiling and the exact format that worked when this was diagnosed live.
SAFE_HANDOFF_SAMPLE_RATE = 48000.0
SAFE_HANDOFF_BITS = 24

# How long to poll after a set() before giving up on seeing it take effect.
#
# Confirmed live against a real G6, and genuinely inconsistent: most clock
# source switches settle in 20-270ms with the format list following within
# another ~100-200ms, but the exact same operation -- same direction, same
# process, no code change in between -- was twice observed to exceed a full
# second before settling, with no pattern found that predicted which trials
# would be slow (not the switch direction, not whether a prior switch had
# just completed; a deliberate attempt to reproduce it as a back-to-back
# timing issue came back fast both times). This is real hardware settle-time
# variance this app has to tolerate, not a bug being papered over -- and
# nothing here blocks the UI thread while it waits (see run_in_executor in
# pages/macos_audio.py), so a generous budget costs nothing but a slightly
# longer wait on the rare slow case. A genuine failure (device unplugged,
# wrong code) still surfaces as an honest error rather than hanging forever.
SETTLE_POLL_INTERVAL = 0.05
SETTLE_POLL_ATTEMPTS = 60


@dataclass(frozen=True)
class ClockSource:
    code: int
    name: str


@dataclass(frozen=True)
class Format:
    sample_rate: float
    bits_per_channel: int
    channels: int = 2
    # kAudioFormatFlagIsNonMixable: an exclusive-mode variant that bypasses
    # Core Audio's mixer entirely, offered by the G6 alongside an ordinary
    # shareable one at the same rate/bit depth -- confirmed live, real G6,
    # not a duplicate-listing bug. Without this field two otherwise-distinct
    # descriptors compared equal, which produced identical-looking dropdown
    # entries where only the first could ever actually be selected.
    non_mixable: bool = False

    def label(self) -> str:
        khz = self.sample_rate / 1000
        khz_text = f"{khz:g}"
        base = f"{self.bits_per_channel}-bit / {khz_text} kHz"
        return f"{base} (Exclusive)" if self.non_mixable else base


@dataclass(frozen=True)
class ClockState:
    """A snapshot of what refresh() found. Immutable so callers can compare
    two snapshots to notice a change rather than trusting a mutable object.

    ``found`` is the only presence flag. Because the device is identified
    purely by its clock-source fingerprint (see find_g6()), "found a G6-like
    device but its clock sources look wrong" is not a state this module can
    actually distinguish from "no such device exists" -- both look identical
    from here. Claiming otherwise would be a false precision this module does
    not have; the macOS Audio page's not-found message says so honestly.
    """

    found: bool = False
    device_id: int | None = None
    stream_id: int | None = None
    clock_source_codes: dict[str, int] = field(default_factory=dict)
    current_clock_source: str | None = None
    current_format: Format | None = None
    available_formats: tuple[Format, ...] = ()


# ── Pure logic — no ctypes, no I/O, fully unit-testable ─────────────────────


def classify_clock_sources(sources: list[ClockSource]) -> dict[str, int] | None:
    """Recognise only the G6's two documented modes.

    Returns ``None`` -- rather than a best-effort partial mapping -- for
    anything else: extra sources, a missing one, different names. That is a
    deliberate choice, not an oversight: this device may be a G6 in a firmware
    revision that renamed something, or it may not be a G6 at all, and the
    macOS Audio tab should grey out and say so rather than guess at an
    unfamiliar configuration. "We should not support the advanced features
    macOS supports with different adapters" was explicit in the request this
    module was built for.
    """
    by_name = {s.name.strip(): s.code for s in sources}
    if set(by_name) != {DSP_CLOCK, STEREO_DIRECT}:
        return None
    return by_name


def filter_stereo_pcm_formats(formats: list[Format]) -> list[Format]:
    """Keep only plain 2-channel formats.

    The G6 in this mode is always stereo; this exists to defensively drop
    anything exotic a future firmware or a misidentified device might report,
    rather than presenting options the G6 was never meant to offer here.
    """
    return [f for f in formats if f.channels == 2]


def needs_safe_handoff(current_format: Format | None) -> bool:
    """Whether the format must be dropped before switching to DSP Clock.

    True whenever the current rate exceeds DSP Clock's documented 48kHz
    ceiling. ``current_format is None`` (nothing read yet) is treated as
    needing no handoff -- there is nothing known to be unsafe.
    """
    return current_format is not None and current_format.sample_rate > SAFE_HANDOFF_SAMPLE_RATE


def sort_formats(formats: list[Format]) -> list[Format]:
    return sorted(formats, key=lambda f: (f.sample_rate, f.bits_per_channel, f.non_mixable))


# ── Hal: the thin ctypes adapter, swappable in tests ────────────────────────


class Hal:
    """What ClockController needs from Core Audio. A real, ctypes-backed
    implementation lives in _CoreAudioHal below; tests substitute a fake."""

    def find_devices(self) -> list[int]:
        raise NotImplementedError

    def device_name(self, device_id: int) -> str:
        raise NotImplementedError

    def clock_sources(self, device_id: int) -> list[ClockSource] | None:
        """None means the property is not implemented by this device at all
        (the ordinary case for almost every audio device that is not the G6)."""
        raise NotImplementedError

    def current_clock_source_code(self, device_id: int) -> int:
        raise NotImplementedError

    def set_clock_source_code(self, device_id: int, code: int) -> None:
        raise NotImplementedError

    def output_streams(self, device_id: int) -> list[int]:
        raise NotImplementedError

    def current_format(self, stream_id: int) -> Format:
        raise NotImplementedError

    def available_formats(self, stream_id: int) -> list[Format]:
        raise NotImplementedError

    def set_format(self, stream_id: int, fmt: Format) -> None:
        raise NotImplementedError


class _CoreAudioHal(Hal):
    """The real implementation. See the module docstring for what was
    verified about this and how, and HANDOFF.md for the manual probe scripts
    this was developed and validated against."""

    def __init__(self) -> None:
        self._audio = ctypes.CDLL(ctypes.util.find_library("CoreAudio"))
        self._cf = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))
        self._bind()

    # -- FourCC selectors, computed from the 4-character codes rather than
    # transcribed as hex, so any typo is in a readable string, not a magic
    # number. Values confirmed against the SDK headers listed in the module
    # docstring.
    @staticmethod
    def _fourcc(chars: str) -> int:
        assert len(chars) == 4
        v = 0
        for ch in chars:
            v = (v << 8) | ord(ch)
        return v

    def _bind(self) -> None:
        fourcc = self._fourcc

        class _Addr(ctypes.Structure):
            _fields_ = [
                ("mSelector", ctypes.c_uint32),
                ("mScope", ctypes.c_uint32),
                ("mElement", ctypes.c_uint32),
            ]

        class _ASBD(ctypes.Structure):
            _fields_ = [
                ("mSampleRate", ctypes.c_double),
                ("mFormatID", ctypes.c_uint32),
                ("mFormatFlags", ctypes.c_uint32),
                ("mBytesPerPacket", ctypes.c_uint32),
                ("mFramesPerPacket", ctypes.c_uint32),
                ("mBytesPerFrame", ctypes.c_uint32),
                ("mChannelsPerFrame", ctypes.c_uint32),
                ("mBitsPerChannel", ctypes.c_uint32),
                ("mReserved", ctypes.c_uint32),
            ]

        class _ValueRange(ctypes.Structure):
            _fields_ = [("mMinimum", ctypes.c_double), ("mMaximum", ctypes.c_double)]

        class _RangedDesc(ctypes.Structure):
            _fields_ = [("mFormat", _ASBD), ("mSampleRateRange", _ValueRange)]

        class _Translation(ctypes.Structure):
            _fields_ = [
                ("mInputData", ctypes.c_void_p),
                ("mInputDataSize", ctypes.c_uint32),
                ("mOutputData", ctypes.c_void_p),
                ("mOutputDataSize", ctypes.c_uint32),
            ]

        self._Addr = _Addr
        self._ASBD = _ASBD
        self._RangedDesc = _RangedDesc
        self._Translation = _Translation

        self.k_system_object = 1
        self.k_scope_global = fourcc("glob")
        self.k_scope_output = fourcc("outp")
        self.k_element_main = 0
        self.k_devices = fourcc("dev#")
        self.k_name = fourcc("lnam")
        self.k_streams = fourcc("stm#")
        self.k_clock_source = fourcc("csrc")
        self.k_clock_sources = fourcc("csc#")
        self.k_clock_source_name = fourcc("lcsn")
        self.k_physical_format = fourcc("pft ")
        self.k_available_physical_formats = fourcc("pfta")

        OSStatus = ctypes.c_int32
        AudioObjectID = ctypes.c_uint32
        self._audio.AudioObjectGetPropertyDataSize.restype = OSStatus
        self._audio.AudioObjectGetPropertyDataSize.argtypes = [
            AudioObjectID, ctypes.POINTER(_Addr), ctypes.c_uint32, ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint32),
        ]
        self._audio.AudioObjectGetPropertyData.restype = OSStatus
        self._audio.AudioObjectGetPropertyData.argtypes = [
            AudioObjectID, ctypes.POINTER(_Addr), ctypes.c_uint32, ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p,
        ]
        self._audio.AudioObjectSetPropertyData.restype = OSStatus
        self._audio.AudioObjectSetPropertyData.argtypes = [
            AudioObjectID, ctypes.POINTER(_Addr), ctypes.c_uint32, ctypes.c_void_p,
            ctypes.c_uint32, ctypes.c_void_p,
        ]
        self._audio.AudioObjectHasProperty.restype = ctypes.c_ubyte
        self._audio.AudioObjectHasProperty.argtypes = [AudioObjectID, ctypes.POINTER(_Addr)]

        self._cf.CFStringGetCStringPtr.restype = ctypes.c_char_p
        self._cf.CFStringGetCStringPtr.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self._cf.CFStringGetLength.restype = ctypes.c_long
        self._cf.CFStringGetLength.argtypes = [ctypes.c_void_p]
        self._cf.CFStringGetCString.restype = ctypes.c_ubyte
        self._cf.CFStringGetCString.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32,
        ]
        self._cf.CFRelease.argtypes = [ctypes.c_void_p]

    # -- low-level property access

    def _has(self, obj_id, selector, scope=None, element=None) -> bool:
        addr = self._Addr(selector, scope or self.k_scope_global, element or self.k_element_main)
        return bool(self._audio.AudioObjectHasProperty(obj_id, ctypes.byref(addr)))

    def _size(self, obj_id, selector, scope=None, element=None) -> int:
        addr = self._Addr(selector, scope or self.k_scope_global, element or self.k_element_main)
        size = ctypes.c_uint32(0)
        status = self._audio.AudioObjectGetPropertyDataSize(
            obj_id, ctypes.byref(addr), 0, None, ctypes.byref(size)
        )
        if status != 0:
            raise OSError(f"AudioObjectGetPropertyDataSize failed: {status} (selector={selector:#x})")
        return size.value

    def _get_raw(self, obj_id, selector, size, scope=None, element=None) -> bytes:
        addr = self._Addr(selector, scope or self.k_scope_global, element or self.k_element_main)
        buf = ctypes.create_string_buffer(size)
        out_size = ctypes.c_uint32(size)
        status = self._audio.AudioObjectGetPropertyData(
            obj_id, ctypes.byref(addr), 0, None, ctypes.byref(out_size), buf
        )
        if status != 0:
            raise OSError(f"AudioObjectGetPropertyData failed: {status} (selector={selector:#x})")
        return buf.raw[: out_size.value]

    def _set_raw(self, obj_id, selector, data: bytes, scope=None, element=None) -> None:
        addr = self._Addr(selector, scope or self.k_scope_global, element or self.k_element_main)
        buf = ctypes.create_string_buffer(data, len(data))
        status = self._audio.AudioObjectSetPropertyData(
            obj_id, ctypes.byref(addr), 0, None, len(data), buf
        )
        if status != 0:
            raise OSError(f"AudioObjectSetPropertyData failed: {status} (selector={selector:#x})")

    def _cfstring_to_str(self, ref: int) -> str:
        if not ref:
            return ""
        ptr = self._cf.CFStringGetCStringPtr(ref, 0x08000100)  # kCFStringEncodingUTF8
        if ptr:
            return ptr.decode("utf-8")
        length = self._cf.CFStringGetLength(ref)
        buf = ctypes.create_string_buffer((length + 1) * 4)
        self._cf.CFStringGetCString(ref, buf, len(buf), 0x08000100)
        return buf.value.decode("utf-8")

    # -- Hal interface

    def find_devices(self) -> list[int]:
        size = self._size(self.k_system_object, self.k_devices)
        n = size // 4
        if n == 0:
            return []
        raw = self._get_raw(self.k_system_object, self.k_devices, size)
        return list((ctypes.c_uint32 * n).from_buffer_copy(raw))

    def device_name(self, device_id: int) -> str:
        size = self._size(device_id, self.k_name)
        raw = self._get_raw(device_id, self.k_name, size)
        ref = int.from_bytes(raw, "little")
        name = self._cfstring_to_str(ref)
        self._cf.CFRelease(ref)
        return name

    def clock_sources(self, device_id: int) -> list[ClockSource] | None:
        if not self._has(device_id, self.k_clock_sources):
            return None
        size = self._size(device_id, self.k_clock_sources)
        n = size // 4
        if n == 0:
            return []
        raw = self._get_raw(device_id, self.k_clock_sources, size)
        codes = list((ctypes.c_uint32 * n).from_buffer_copy(raw))
        return [ClockSource(code=c, name=self._clock_source_name(device_id, c)) for c in codes]

    def _clock_source_name(self, device_id: int, code: int) -> str:
        in_code = ctypes.c_uint32(code)
        out_ref = ctypes.c_void_p(0)
        xlat = self._Translation(
            ctypes.cast(ctypes.byref(in_code), ctypes.c_void_p), 4,
            ctypes.cast(ctypes.byref(out_ref), ctypes.c_void_p), 8,
        )
        addr = self._Addr(self.k_clock_source_name, self.k_scope_global, self.k_element_main)
        size = ctypes.c_uint32(ctypes.sizeof(xlat))
        status = self._audio.AudioObjectGetPropertyData(
            device_id, ctypes.byref(addr), 0, None, ctypes.byref(size), ctypes.byref(xlat)
        )
        if status != 0:
            raise OSError(f"clock source name translation failed: {status}")
        name = self._cfstring_to_str(out_ref.value)
        self._cf.CFRelease(out_ref)
        return name

    def current_clock_source_code(self, device_id: int) -> int:
        raw = self._get_raw(device_id, self.k_clock_source, 4)
        return ctypes.c_uint32.from_buffer_copy(raw).value

    def set_clock_source_code(self, device_id: int, code: int) -> None:
        self._set_raw(device_id, self.k_clock_source, bytes(ctypes.c_uint32(code)))

    def output_streams(self, device_id: int) -> list[int]:
        if not self._has(device_id, self.k_streams, scope=self.k_scope_output):
            return []
        size = self._size(device_id, self.k_streams, scope=self.k_scope_output)
        n = size // 4
        if n == 0:
            return []
        raw = self._get_raw(device_id, self.k_streams, size, scope=self.k_scope_output)
        return list((ctypes.c_uint32 * n).from_buffer_copy(raw))

    K_FORMAT_FLAG_IS_NON_MIXABLE = 1 << 6  # kAudioFormatFlagIsNonMixable

    def _asbd_to_format(self, asbd) -> Format:
        return Format(
            sample_rate=asbd.mSampleRate,
            bits_per_channel=asbd.mBitsPerChannel,
            channels=asbd.mChannelsPerFrame,
            non_mixable=bool(asbd.mFormatFlags & self.K_FORMAT_FLAG_IS_NON_MIXABLE),
        )

    def current_format(self, stream_id: int) -> Format:
        size = self._size(stream_id, self.k_physical_format)
        raw = self._get_raw(stream_id, self.k_physical_format, size)
        return self._asbd_to_format(self._ASBD.from_buffer_copy(raw))

    def _available_asbds(self, stream_id: int) -> list:
        """The raw ctypes structs behind available_formats(), kept internal.

        set_format() needs these, not the simplified Format objects: sending
        back the exact bytes Core Audio itself offered avoids having to guess
        driver-specific packing fields (mFormatFlags, mBytesPerFrame, ...) that
        this module has no way to know without the real device present. This
        is the standard, safe pattern -- pick from what the HAL reports as
        valid, never synthesise a descriptor from scratch.
        """
        size = self._size(stream_id, self.k_available_physical_formats)
        n = size // ctypes.sizeof(self._RangedDesc)
        if n == 0:
            return []
        raw = self._get_raw(stream_id, self.k_available_physical_formats, size)
        return list((self._RangedDesc * n).from_buffer_copy(raw))

    def available_formats(self, stream_id: int) -> list[Format]:
        return [self._asbd_to_format(d.mFormat) for d in self._available_asbds(stream_id)]

    def set_format(self, stream_id: int, fmt: Format) -> None:
        for desc in self._available_asbds(stream_id):
            if self._asbd_to_format(desc.mFormat) == fmt:
                self._set_raw(stream_id, self.k_physical_format, bytes(desc.mFormat))
                return
        raise ValueError(
            f"{fmt} is not currently offered by this stream's "
            "available physical formats -- refusing to fabricate one"
        )


# ── Device identification ────────────────────────────────────────────────────


def find_g6(hal: Hal) -> tuple[int, dict[str, int]] | None:
    """Find the device whose clock sources are exactly the G6's two documented
    modes, and return its device id with the name->code mapping.

    Deliberately does *not* match by device name: nothing in this codebase has
    confirmed what Core Audio actually calls the G6 (see the module
    docstring), so instead this looks for the one fact known for certain from
    Creative's own documentation -- a device with clock sources named exactly
    "DSP Clock" and "Stereo Direct". If more than one device somehow matches,
    the first one found is used; that is not expected to happen in practice.
    """
    for device_id in hal.find_devices():
        try:
            sources = hal.clock_sources(device_id)
        except OSError:
            continue
        if not sources:
            continue
        classified = classify_clock_sources(sources)
        if classified is not None:
            return device_id, classified
    return None


# ── ClockController: the stateful orchestrator pages talk to ────────────────


class ClockController:
    """Reads and switches the G6's clock source and format.

    All the decision logic (which clock sources are recognised, when the
    switch-back handoff is needed, which formats are offered) is in the pure
    functions above; this class is a thin, testable sequencing shell around
    them and the injected ``hal``. Pass a fake ``hal`` in tests -- see
    tests/g6_gui/fake_coreaudio.py.
    """

    def __init__(self, hal: Hal | None = None):
        # Construction of the real _CoreAudioHal is deferred to first use in
        # refresh(), not done here -- see _ensure_hal(). Doing it eagerly
        # would make merely *constructing* a ClockController crash outright
        # on a platform without Core Audio (there is no Linux equivalent of
        # this tab, but pages_contract_test.py builds every page
        # unconditionally regardless of platform, and a future refactor could
        # plausibly do the same). ``hal`` passed explicitly (tests) is used
        # as-is and never goes through this fallback at all.
        self._hal = hal
        self._hal_unavailable = False
        self.state = ClockState()

    def _ensure_hal(self) -> Hal | None:
        if self._hal is not None:
            return self._hal
        if self._hal_unavailable:
            return None
        try:
            self._hal = _CoreAudioHal()
        except OSError:
            self._hal_unavailable = True
            return None
        return self._hal

    def refresh(self) -> ClockState:
        """Re-read everything from Core Audio. Cheap enough to call on every
        tab visit and after every change -- there is no push notification
        wired up, so this is the only way this app's idea of the state stays
        honest, in keeping with the rest of the project's "no readback, trust
        the device" stance (see docs/device-state.md).

        Never raises: any OSError encountered while talking to Core Audio --
        including Core Audio simply not being present at all -- is treated
        the same as the G6 not being found, per the module docstring's "every
        Core Audio call wrapped in try/except OSError" promise.
        """
        hal = self._ensure_hal()
        if hal is None:
            self.state = ClockState(found=False)
            return self.state

        try:
            found = find_g6(hal)
            if found is None:
                self.state = ClockState(found=False)
                return self.state

            device_id, classified = found
            current_code = hal.current_clock_source_code(device_id)
            current_name = next((n for n, c in classified.items() if c == current_code), None)

            streams = hal.output_streams(device_id)
            stream_id = streams[0] if streams else None
            current_format = hal.current_format(stream_id) if stream_id is not None else None
            available = (
                sort_formats(filter_stereo_pcm_formats(hal.available_formats(stream_id)))
                if stream_id is not None
                else []
            )
        except OSError:
            self.state = ClockState(found=False)
            return self.state

        self.state = ClockState(
            found=True,
            device_id=device_id,
            stream_id=stream_id,
            clock_source_codes=classified,
            current_clock_source=current_name,
            current_format=current_format,
            available_formats=tuple(available),
        )
        return self.state

    def set_clock_source(self, name: str) -> ClockState:
        if not self.state.found:
            raise RuntimeError("no supported G6 found; call refresh() first")
        if name not in self.state.clock_source_codes:
            raise ValueError(f"unknown clock source {name!r}, expected one of {list(self.state.clock_source_codes)}")

        if name == DSP_CLOCK and needs_safe_handoff(self.state.current_format):
            self._handoff_to_safe_format()

        formats_before = self.state.available_formats
        code = self.state.clock_source_codes[name]
        self._hal.set_clock_source_code(self.state.device_id, code)
        self._require(lambda: self.refresh().current_clock_source == name,
                       f"Core Audio did not switch to {name!r}")

        # current_clock_source flips essentially instantly, but the stream's
        # available-format list lags behind it -- confirmed live, real G6:
        # immediately after the clock source read back correctly, the format
        # list still reported the *previous* clock source's formats (32
        # entries, Stereo Direct's) for roughly 100-200ms before settling to
        # the real new list (8 entries, DSP Clock's). Poll a little longer
        # specifically for that, rather than returning with a stale list.
        self._wait_while(lambda: self.refresh().available_formats == formats_before)
        return self.state

    def set_format(self, fmt: Format) -> ClockState:
        if not self.state.found or self.state.stream_id is None:
            raise RuntimeError("no supported G6 found; call refresh() first")
        if fmt not in self.state.available_formats:
            raise ValueError(f"{fmt} is not in the currently available formats for this clock source")
        self._hal.set_format(self.state.stream_id, fmt)
        self._require(lambda: self.refresh().current_format == fmt,
                       f"Core Audio did not switch to {fmt}")
        return self.state

    def _handoff_to_safe_format(self) -> None:
        # Prefer 48kHz at whatever bit depth is actually offered -- do not
        # assume 24-bit specifically is available (some drivers only offer
        # one bit depth per rate; verified against BlackHole, which is
        # 32-bit-only, while testing this). Only fall back to the lowest
        # available rate, as a last resort, if 48kHz is not offered at all.
        at_48k = [f for f in self.state.available_formats if f.sample_rate == SAFE_HANDOFF_SAMPLE_RATE]
        if at_48k:
            preferred = [f for f in at_48k if f.bits_per_channel == SAFE_HANDOFF_BITS]
            chosen = preferred[0] if preferred else at_48k[0]
        else:
            chosen = min(self.state.available_formats, key=lambda f: f.sample_rate, default=None)
        if chosen is None:
            return  # nothing known to be safe; proceed and let the user recover manually
        self._hal.set_format(self.state.stream_id, chosen)
        self._require(lambda: self.refresh().current_format == chosen,
                       f"safe-handoff format switch to {chosen} did not take")

    def _require(self, predicate, message: str) -> None:
        """Poll for ``predicate`` and raise if it never becomes true.

        Never treat a set() as having succeeded just because the call itself
        did not raise -- Core Audio can accept a call and then silently not
        apply it. The whole point of refresh() existing is to trust what the
        device reports, not what was sent; a set() that does not honour that
        would be exactly the kind of bug docs/device-state.md warns about
        elsewhere in this project.
        """
        for _ in range(SETTLE_POLL_ATTEMPTS):
            if predicate():
                return
            time.sleep(SETTLE_POLL_INTERVAL)
        if not predicate():
            raise TimeoutError(message)

    def _wait_while(self, predicate) -> None:
        """Poll while ``predicate`` holds, refreshing self.state each time.

        Unlike _require(), never raises on timeout -- used where catching up
        is worth a short wait but not itself the definition of success (the
        clock source switch this follows already succeeded; the format list
        settling is a courtesy refresh, not something that should fail the
        whole operation if it happens to take longer than expected).
        """
        for _ in range(SETTLE_POLL_ATTEMPTS):
            if not predicate():
                return
            time.sleep(SETTLE_POLL_INTERVAL)
