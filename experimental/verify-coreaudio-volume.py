#!/usr/bin/env python3
"""Standalone probe: what does Core Audio actually report for the G6's
output volume and channel layout?

Written because coreaudio.py's ``_CoreAudioHal.output_volume()`` and the
channel-count/"virtual 7.1" fields on ``ClockState`` were both implemented
and unit-tested against ``FakeHal`` with **no G6 attached to develop them
against** -- see HANDOFF.md and the coreaudio.py module docstring. Every
FourCC used below was verified against this machine's Xcode SDK headers
(AudioHardware.h, AudioHardwareBase.h, AudioHardwareService.h under
AudioToolbox.framework), the same way coreaudio.py's own constants were, but
"the header says this selector exists" is not the same claim as "the G6
implements it" -- only running this against real hardware settles that.

A first run against a real G6 (2026-09-17, device 50) already settled the
scalar side of this: no 'vmvc', no master-element 'volm', but 'volm' IS
implemented on channels 1/2, and the device is genuinely 2-channel with no
non-stereo formats offered at all. See coreaudio.py's module docstring for
the full readout. What that run did NOT settle, because it only ever probed
'vold' and 'mute' on output/main -- the one element that had already turned
out to have nothing on it -- is whether 'vold' (the dB view of the same
volume control coreaudio.output_volume_db() now reads) exists per-channel
the same way 'volm' does. This version closes that gap: it probes 'vold' and
'mute' on main AND channels 1/2, prints the scalar/dB pairs directly so the
non-linear mapping can be read off, and prints what the new dB-preferred
warning logic (coreaudio.is_full_scale_volume()) would actually decide.

Run with the G6 plugged in and selected (or just attached; this script scans
every device, same as coreaudio.find_g6()):

    ./venv/bin/python experimental/verify-coreaudio-volume.py

What it prints, per candidate device:
  - device id and name
  - whether its clock sources match the G6 fingerprint (DSP Clock / Stereo
    Direct) that coreaudio.find_g6() looks for
  - every volume-related property this script knows how to probe (scalar,
    dB, and mute, each on main/ch1/ch2), and either its value or "not
    implemented" -- the actual evidence for which properties and elements
    coreaudio.py's output_volume()/output_volume_db() should trust
  - the scalar-to-dB pairing for any element where both are implemented, so
    the non-linear mapping this module's threshold comments describe can be
    seen directly rather than taken on faith
  - what coreaudio.is_full_scale_volume() would decide right now, and which
    property (dB or the scalar fallback) it based that decision on
  - the current stream format and the FULL available-format list, including
    any non-stereo entries filter_stereo_pcm_formats() would normally drop --
    this is the evidence for the "virtual 7.1 reality check" in
    ClockState.non_stereo_formats_available

Read-only: this script never calls AudioObjectSetPropertyData. It only
reads properties already exposed by the public HAL, the same API Audio MIDI
Setup itself uses.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Run as a plain script (not installed as a package entry point), so make
# sure `src/` is importable the same way the test suite's conftest does.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from g6_gui import coreaudio as ca  # noqa: E402


def _probe(hal: ca._CoreAudioHal, device_id: int, label: str, selector: int, *, scope: int, element: int) -> str:
    """Return a human-readable line for one (selector, scope, element) probe.

    Never raises: a selector Core Audio doesn't implement for this device is
    the expected, common case (see coreaudio.py's own Hal.clock_sources()
    docstring for the same point about clock sources), not a script error.
    """
    try:
        has = hal._has(device_id, selector, scope=scope, element=element)
    except OSError as exc:
        return f"    {label:<40} ERROR checking AudioObjectHasProperty: {exc}"
    if not has:
        return f"    {label:<40} not implemented"
    try:
        size = hal._size(device_id, selector, scope=scope, element=element)
        raw = hal._get_raw(device_id, selector, size, scope=scope, element=element)
        if size == 4:
            import ctypes

            value = ctypes.c_float.from_buffer_copy(raw).value
            return f"    {label:<40} {value:.4f}  (raw bytes: {raw.hex()})"
        return f"    {label:<40} {size} bytes: {raw.hex()}"
    except OSError as exc:
        return f"    {label:<40} has property but read failed: {exc}"


def _scope_name(hal: ca._CoreAudioHal, scope: int) -> str:
    return {hal.k_scope_global: "global", hal.k_scope_output: "output"}.get(scope, hex(scope))


def _read_float(hal: ca._CoreAudioHal, device_id: int, selector: int, *, scope: int, element: int) -> float | None:
    """Value of a 4-byte float property if implemented, else None -- never
    raises. Used by the scalar/dB pairing and the decision printout below,
    which need the actual value rather than _probe()'s formatted line."""
    try:
        if not hal._has(device_id, selector, scope=scope, element=element):
            return None
        size = hal._size(device_id, selector, scope=scope, element=element)
        if size != 4:
            return None
        raw = hal._get_raw(device_id, selector, size, scope=scope, element=element)
    except OSError:
        return None
    import ctypes

    return ctypes.c_float.from_buffer_copy(raw).value


def describe_device(hal: ca._CoreAudioHal, device_id: int) -> None:
    try:
        name = hal.device_name(device_id)
    except OSError as exc:
        print(f"Device {device_id}: <could not read name: {exc}>")
        return

    print(f"\nDevice {device_id}: {name!r}")

    try:
        sources = hal.clock_sources(device_id)
    except OSError as exc:
        sources = None
        print(f"  clock_sources: ERROR: {exc}")

    if sources is None:
        print("  clock sources: property not implemented (most devices)")
    else:
        names = [s.name for s in sources]
        print(f"  clock sources: {names}")
        classified = ca.classify_clock_sources(sources)
        if classified is not None:
            print("  ^ MATCHES the G6 fingerprint (DSP Clock / Stereo Direct) -- this is find_g6()'s pick")
        else:
            print("  ^ does not match the G6 fingerprint")

    print("  volume-related properties:")
    probes = [
        ("kAudioHardwareServiceDeviceProperty_VirtualMainVolume ('vmvc')", hal.k_virtual_main_volume, hal.k_scope_global, hal.k_element_main),
        ("kAudioDevicePropertyVolumeScalar ('volm') output/main", hal.k_volume_scalar, hal.k_scope_output, hal.k_element_main),
        ("kAudioDevicePropertyVolumeScalar ('volm') output/ch1", hal.k_volume_scalar, hal.k_scope_output, 1),
        ("kAudioDevicePropertyVolumeScalar ('volm') output/ch2", hal.k_volume_scalar, hal.k_scope_output, 2),
        # 'vold' was only ever probed on output/main before -- the same
        # element where 'volm' also turned out to be absent. Now probed on
        # ch1/ch2 too, the elements where 'volm' actually lives, to settle
        # whether output_volume_db()'s per-channel assumption is correct.
        ("kAudioDevicePropertyVolumeDecibels ('vold') output/main", hal.k_volume_decibels, hal.k_scope_output, hal.k_element_main),
        ("kAudioDevicePropertyVolumeDecibels ('vold') output/ch1", hal.k_volume_decibels, hal.k_scope_output, 1),
        ("kAudioDevicePropertyVolumeDecibels ('vold') output/ch2", hal.k_volume_decibels, hal.k_scope_output, 2),
        ("kAudioDevicePropertyMute ('mute') output/main", hal._fourcc("mute"), hal.k_scope_output, hal.k_element_main),
        ("kAudioDevicePropertyMute ('mute') output/ch1", hal._fourcc("mute"), hal.k_scope_output, 1),
        ("kAudioDevicePropertyMute ('mute') output/ch2", hal._fourcc("mute"), hal.k_scope_output, 2),
    ]
    for label, selector, scope, element in probes:
        print(_probe(hal, device_id, label, selector, scope=scope, element=element))

    print("  scalar-to-dB pairs (only where BOTH are implemented on the same element):")
    any_pair = False
    for label, element in (("main", hal.k_element_main), ("ch1", 1), ("ch2", 2)):
        scalar = _read_float(hal, device_id, hal.k_volume_scalar, scope=hal.k_scope_output, element=element)
        db = _read_float(hal, device_id, hal.k_volume_decibels, scope=hal.k_scope_output, element=element)
        if scalar is not None and db is not None:
            print(f"    {label}: scalar {scalar:.4f}  =  {db:.2f} dB")
            any_pair = True
    if not any_pair:
        print("    (none -- scalar and dB are never both implemented on the same element here)")

    print("  what coreaudio.py's output_volume() would return:", end=" ")
    try:
        volume = hal.output_volume(device_id)
        print(volume)
    except OSError as exc:
        volume = None
        print(f"ERROR: {exc}")

    print("  what coreaudio.py's output_volume_db() would return:", end=" ")
    try:
        volume_db = hal.output_volume_db(device_id)
        print(volume_db)
    except OSError as exc:
        volume_db = None
        print(f"ERROR: {exc}")

    decision = ca.is_full_scale_volume(volume, volume_db)
    if volume_db is not None:
        basis = (
            f"'vold' reading {volume_db:.2f} dB vs threshold "
            f"{ca.FULL_SCALE_VOLUME_DB_THRESHOLD} dBFS (ASR's -2 dBFS finding)"
        )
    elif volume is not None:
        basis = (
            f"'vold' unavailable -- fell back to the scalar reading {volume:.4f} "
            f"vs threshold {ca.FULL_SCALE_VOLUME_THRESHOLD}"
        )
    else:
        basis = "no volume reading available at all -- never warns"
    print(f"  what the full-scale warning would decide right now: warn={decision}")
    print(f"    basis: {basis}")

    try:
        streams = hal.output_streams(device_id)
    except OSError as exc:
        print(f"  output_streams: ERROR: {exc}")
        return
    if not streams:
        print("  no output streams")
        return

    stream_id = streams[0]
    try:
        current = hal.current_format(stream_id)
        print(f"  current format: {current}")
    except OSError as exc:
        print(f"  current format: ERROR: {exc}")

    try:
        all_formats = hal.available_formats(stream_id)
    except OSError as exc:
        print(f"  available formats: ERROR: {exc}")
        return

    print(f"  available formats (unfiltered, {len(all_formats)} total):")
    for fmt in ca.sort_formats(all_formats):
        tag = "" if fmt.channels == 2 else "  <-- NON-STEREO"
        print(f"    {fmt}{tag}")

    stereo_only = ca.sort_formats(ca.filter_stereo_pcm_formats(all_formats))
    print(f"  after filter_stereo_pcm_formats(): {len(stereo_only)} entries (what the dropdown would show)")
    print(f"  has_non_stereo_formats(): {ca.has_non_stereo_formats(all_formats)}")


def main() -> int:
    hal = ca._CoreAudioHal()
    device_ids = hal.find_devices()
    if not device_ids:
        print("No audio devices found at all -- unexpected, check Core Audio is running.")
        return 1

    print(f"Found {len(device_ids)} audio device(s): {device_ids}")
    for device_id in device_ids:
        describe_device(hal, device_id)

    found = ca.find_g6(hal)
    print()
    if found is None:
        print("find_g6() did not identify any device as the G6 -- see per-device clock sources above.")
    else:
        device_id, classified = found
        print(f"find_g6() identified device {device_id} with clock sources {classified}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
