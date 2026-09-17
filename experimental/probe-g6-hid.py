#!/usr/bin/env python3
"""Probe of the Sound Blaster X G6's HID readback protocol (`5A 11 03 ...`).

STANDALONE TOOL. Not imported by the GUI (``g6_gui``) or by ``g6_device``, and
never run automatically by anything in this project. You run it by hand, on
purpose.

HISTORY -- READ THIS BEFORE CHANGING THE DEFAULTS AGAIN
--------------------------------------------------------
This script went through three iterations before this one. Each is preserved
here because the earlier evidence still matters:

1. **v1 (single guess).** Sent `5A E0 01 <n>` for sub-sub `n` in 1..9,
   modelled on the documented `5A <sub> <len> <payload>` framing from
   ``docs/g6-re/docs/fw_notes.md`` ("90/0xE0(224)/sub-1..9 = GET variants").
   Run against a real G6, all nine came back **byte-identical**:
   `5A 02 0A E0 81 00...00`. Nobody knew why.

2. **v2 (frame-shape analysis).** Reading `UsbHidDataFragment.__to_hex()` in
   ``src/g6_cli/g6_spec/__init__.py`` showed the real 64-byte layout is
   `prefix(1) | mode(2) | intermediate(2) | audio_feature(1) | value(4) |
   padding(54)` -- so v1's byte1/byte2 (`E0`/`01`) are actually the 2-byte
   `mode` field (command=0xE0, op=0x01), and its "sub-sub" byte landed in
   `intermediate`, not in a length field as v1 assumed. This produced a
   hypothesis that `mode`'s second byte is a generic command/op split
   (guessing op 0x01 = "commit"), and that the response's `02` might be a
   generic "read" op. **Both guesses turned out to be wrong** in different
   ways -- see below. They are recorded here because the wrong turns are as
   instructive as the right one, and because docs/hid-probe-findings.md
   documents exactly where each one broke down.

3. **v3 (this version) -- decoded from real, direction-tagged USB captures.**
   This repo ships ``payloads/raw/*.pcapng`` -- USBPcap captures of the
   Windows app (Sound Blaster Command) talking to a real G6, made for
   *other* reasons (documenting mixer/recording/lighting behaviour), long
   before anyone thought to mine them for this. USBPcap records which side
   of the wire each packet came from. Parsing them (no tshark/scapy needed;
   the format is simple enough for a ~60-line pcapng+USBPcap reader) gives
   *ground truth*, not inference:

   - `5A 12 07 <intermediate> <audio_feature> <value>` -- **HOST -> DEVICE,
     write.** This is `DataFragmentMode.DATA` in ``g6_spec``. Confirmed
     host-only across every capture in ``payloads/raw/`` (14 occurrences).
   - `5A 11 03 <intermediate> <audio_feature> <value=0>` -- **HOST ->
     DEVICE, read request.** This is `DataFragmentMode.COMMIT` in
     ``g6_spec`` -- **upstream's own name for it is wrong** (see
     docs/hid-probe-findings.md for why that's not a bug worth fixing:
     upstream is frozen, and sending a "read" as a "commit" after every
     write is harmless -- it works today, by ear, on real hardware).
     Confirmed host-only, 14 occurrences.
   - `5A 11 08 01 00 <family> <index> <value>` -- **DEVICE -> HOST, read
     response.** Confirmed device-only, 26 occurrences, captured on
     endpoint 0x85 (interrupt IN). This is the actual readback of the value
     just queried by a `5A 11 03` request. **This directly contradicts
     ``docs/device-state.md``'s "there is no readback" for this specific
     message family** -- the plumbing already exists; upstream's own
     `send_hid_data_to_device` already does `h.read(64)` after every send,
     it just discards the result (see ``src/g6_cli/g6_core.py``).
   - `5A 02 0A <echoed-command> <status>` -- **DEVICE -> HOST, generic
     ACK.** Confirmed device-only, 31 occurrences, for at least three
     different write commands (0x12, 0x3A, 0x3C). Status was `0x00` in
     *every* captured example -- meaning this project has **zero** captured
     examples of a non-zero status, and therefore zero direct evidence of
     what a non-zero status means. **v1's `5A 02 0A E0 81` reads as: an ACK
     for command 0xE0, with status 0x81 -- read as likely error/unsupported
     only by contrast with the always-0x00 successes. That is [inferred],
     not observed -- do not state it more confidently than that.** Command
     0xE0 never appears anywhere in ``payloads/raw/`` -- it was never
     exercised by the real app, consistent with ``fw_notes.md`` calling it
     firmware-implemented but app-unused.

   Full evidence, transcripts, and confidence markers for every claim above:
   docs/hid-probe-findings.md.

4. **v4 (this version) -- retuned for a one-device constraint.** The
   device's owner has exactly one G6 and no replacement: "you can't assume
   anything regarding the usb spec." v3's ``read-sweep`` walked a 32-value
   index range per family, which is coverage-oriented, not risk-oriented --
   nobody has observed most of those (family, index) pairs on the wire. A
   first pass at fixing that tallied only ``payloads/raw/*.pcapng`` and
   landed on a narrow 5-index proven-safe set (family 0x95 only) -- too
   narrow, and for the wrong reason: it missed that **this app's own
   source already sends `1103` read requests for far more than that**.
   `sbx.py`, `recording.py`, `decoder.py` and `playback.py` each build a
   DATA frame followed by a COMMIT frame (`DataFragmentMode.COMMIT` *is*
   `1103`), and the COMMIT carries the exact same `intermediate` and
   `audio_feature` as the DATA frame before it -- so every register this
   app ever writes, it already asks the device to read back, and upstream
   throws the answer away. `HANDOFF.md` section 8 records that Playback,
   Recording, Lighting and SBX were all exercised against this exact unit
   (serial E5004E4F57X) and restored -- so replaying these exact frames is
   not "coverage for its own sake", it's frames this device has already
   answered, repeatedly, safely. See TIERS below for the corrected,
   source-derived set.

TIERS -- read this before passing any ``--include-*`` flag
--------------------------------------------------------------
1. **Default (no flag needed): every (family, index) this app already
   writes.** Derived from ``src/g6_cli/g6_spec/`` by grep, not guessed --
   see ``TIER1_INDICES`` below for the exact set and which function
   contributes each index. Covers all three families (`0x95` recording,
   `0x96` playback/SBX, `0x97` decoder). This tier is defensible as
   "replaying frames this exact application already sends to this exact
   device, which HANDOFF.md records has already survived it."
2. **``--include-documented``: whatever `doc/usb-spec.md` documents that
   tier 1 does not already cover.** After widening tier 1 to the app's own
   source, this is down to one entry -- family `0x96` index `0x17`
   ("Physical Speakers Configuration", a feature this app doesn't
   implement). Documented elsewhere, not something this app's source
   sends, hence a separate, explicitly-labelled tier.
3. **``--include-speculative``: everything else.** The `e0-recheck`
   campaign (replaying v1's already-answered frames), a small sweep of
   undocumented family bytes (`0x90`-`0x9F`, minus `0x9B`), and -- only if
   you also pass ``--speculative-index-range`` -- a wider index walk within
   families `0x95`/`0x96`/`0x97` beyond what tiers 1 and 2 already cover.
   This tier prints a prominent warning before it sends anything: these are
   frames nobody has observed the vendor *or this app* sending, to a device
   with no replacement.

See "Why the default sweep is deliberately narrow" in
docs/hid-probe-findings.md for the full reasoning and per-index citations.

WHAT THIS VERSION DOES DIFFERENTLY
------------------------------------
- **The default is now tier 1** -- every read request this app's own source
  already issues (37 frames across three families), not a hand-picked
  sample. No index range is walked unless you explicitly ask for one, and
  even then only under ``--include-speculative``.
- **The main primitive is still `5A 11 03`** (read request) /
  ``5A 11 08`` (read response) -- reading confirmed live device state is a
  bigger win than a firmware-version string, and this primitive is
  confirmed to work by direct pcap evidence, not inference.
- **0xE0 is speculative now, not a default recheck.** It's already answered
  (status 0x81, read as likely-rejection -- see history above), so
  resending it teaches us little and it is not vendor-observed traffic;
  it now lives behind ``--include-speculative``.
- A best-effort ``decode_hint()`` recognises the two confirmed response
  shapes (generic ACK, and 0x11 read response) and prints what it can parse
  out of them (echoed command/status, or echoed family/index/value),
  labelled as a best-effort decode, not a certainty.

SAFETY (unchanged in spirit from every earlier version, tightened in v4)
---------------------------------------------------------------------------
- Dry-run by default. Pass ``--send`` to actually open the device and
  transmit anything, and you'll get a y/N confirmation unless ``--yes`` is
  also given.
- The default (tier 1) and ``--include-documented`` (tier 2) only ever send
  **read requests** (`5A 11 03 ...`, value field always zero) for
  (family, index) pairs this app's own source is confirmed to write
  (tier 1) or that ``doc/usb-spec.md`` documents beyond that (tier 2).
  **No write-family frame (`5A 12 07 ...` or any other) is ever built by
  either tier.**
- ``--include-speculative`` sends frames nobody has observed the vendor
  *or this app* sending to this device -- printed with a loud warning
  before anything is built, because the device's owner has exactly one G6
  and no replacement.
- ``--baseline`` is the one intentional, non-tiered exception: it sends a
  real, already-used, reversible WRITE (re-selecting a DAC playback
  filter), built with ``g6_cli.g6_spec.playback.playback_filter()`` -- the
  same upstream helper the GUI itself calls -- specifically so we have a
  known-good reference to compare error/rejection responses against. See
  ``build_baseline_cases()``.
- This script will never build a frame targeting command 0x9B (155,
  decimal) or containing the byte pair `AA 55` / `55 AA` anywhere --  that
  is the firmware's flash-update handshake
  (``docs/g6-re/REPORT.md``: "FW dispatcher case 90/155 (0x9B): `AA 55`/
  `55 AA` handshake ... 4KB erase blocks + write"). ``_assert_safe()``
  enforces this at frame-build time, not just by convention.
- Mirrors ``src/g6_cli/g6_core.py``'s HID framing exactly (interface 4, and
  a report-id 0x00 byte prepended before the 64-byte payload) but does not
  import ``g6_cli``'s device/HID classes for the sweep itself -- only the
  pure frame-building helpers (``g6_spec``) for ``--baseline``, plus the
  shared VID/PID/interface constants from ``g6_device.constants``.
- Do not run this with ``--send`` while playing or recording audio.

USAGE
-----
    # See what would be sent, without touching the device:
    ./venv/bin/python experimental/probe-g6-hid.py

    # The recommended real run: tier 1 (the default -- everything this app's
    # own source already writes) plus the known-good baseline for comparison:
    ./venv/bin/python experimental/probe-g6-hid.py --send --baseline

    # Also try the one documented-but-not-app-sent index (family 0x96, 0x17):
    ./venv/bin/python experimental/probe-g6-hid.py --send --baseline --include-documented

    # Everything, including frames nobody has observed the vendor OR this
    # app sending (reads the warning, thinks about it, then decides):
    ./venv/bin/python experimental/probe-g6-hid.py --send --include-documented --include-speculative

    # Widen the index search within families 0x95/0x96/0x97 -- speculative
    # only, requires --include-speculative:
    ./venv/bin/python experimental/probe-g6-hid.py --send --include-speculative --speculative-index-range 0-3f

Paste the printed grouped summary back for a human (or the next agent) to
read -- identical responses are collapsed to one line with a count, and any
response that differs from the common one for its campaign is printed in
full and flagged, since that is the signal actually worth chasing.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass

try:
    from g6_device.constants import G6_HID_INTERFACE, G6_PRODUCT_ID, G6_VENDOR_ID
except ImportError:  # pragma: no cover - fallback if run without `pip install -e .`
    G6_VENDOR_ID = 0x041E
    G6_PRODUCT_ID = 0x3256
    G6_HID_INTERFACE = 4

FRAME_LEN = 64
PREFIX = 0x5A

# Byte layout, confirmed two ways: (1) reverse-derived from
# UsbHidDataFragment.__to_hex() in src/g6_cli/g6_spec/__init__.py, and (2)
# matched byte-for-byte against real HOST->DEVICE frames captured in
# payloads/raw/*.pcapng (see module docstring, v3).
#   [0]      prefix         (always 0x5A)
#   [1]      command        (0x12 write, 0x11 read-request, 0xE0 GET-group
#                             (answered-negative -- see docstring))
#   [2]      op             (0x07 for a 0x12 write, 0x03 for a 0x11 read --
#                             meaning is NOT consistent across commands;
#                             see docs/hid-probe-findings.md's "what changed"
#                             section for why that generalisation failed)
#   [3:5]    intermediate   (2 bytes -- for reads/writes this is always
#                             `01 <family>`, where family is one of the
#                             DataFragmentStatic values: 0x95 recording,
#                             0x96 playback, 0x97 decoder)
#   [5]      audio_feature  (1 byte -- the index within that family)
#   [6:10]   value          (4 bytes -- the float/int payload; zero for a
#                             read request)
#   [10:64]  padding        (54 bytes, always zero in every captured frame)
OFF_COMMAND = 1
OFF_OP = 2
OFF_INTERMEDIATE = 3
OFF_AUDIO_FEATURE = 5
OFF_VALUE = 6

CMD_WRITE = 0x12          # confirmed HOST->DEVICE, op 0x07 ("DATA" in g6_spec)
CMD_READ = 0x11           # confirmed HOST->DEVICE (op 0x03) / DEVICE->HOST (op 0x08)
CMD_ACK = 0x02             # confirmed DEVICE->HOST generic ack, op/len 0x0A
CMD_GET_GROUP = 0xE0       # fw_notes.md's GET group -- answered-negative, see docstring

OP_WRITE = 0x07
OP_READ_REQUEST = 0x03     # confirmed real: DataFragmentMode.COMMIT's actual op
OP_READ_RESPONSE = 0x08    # confirmed real (also seen: 0x0E, a longer variant -- untested here)
OP_ACK = 0x0A

# The three documented DataFragmentStatic intermediate values (high byte is
# always 0x01; low byte is the "family"). Sourced from g6_cli.g6_spec so this
# script can't drift from upstream's own constants. Note: 0x97 (decoder) is
# NOT wired into any tier below -- it's documented in g6_spec and in
# doc/usb-spec.md, but the coordinator scoped tier 2 to family 0x96 only, so
# for now 0x97 is only reachable via --include-speculative's family bonus.
FAMILY_RECORDING = 0x95   # DataFragmentStatic.RECORDING_INTERMEDIATE = 0x0195
FAMILY_PLAYBACK = 0x96    # DataFragmentStatic.PLAYBACK_INTERMEDIATE = 0x0196
FAMILY_DECODER = 0x97     # DataFragmentStatic.DECODER_INTERMEDIATE = 0x0197

# The exact prefix v1 sent and got back a (now-understood-as-rejected)
# answer for, every time, for every sub-sub 1..9. Used by the e0-recheck
# campaign both to build its frames and to recognise whether the same
# answer reproduces.
KNOWN_E0_REJECTION_PREFIX = bytes.fromhex("5a020ae081")

# Never go near these -- the firmware's flash-update protocol.
FORBIDDEN_COMMANDS = {0x9B}  # sub 155, decimal -- docs/g6-re/REPORT.md
FORBIDDEN_BYTE_PAIRS = (bytes.fromhex("AA55"), bytes.fromhex("55AA"))

# TIER 1 (default): every (family, index) pair this application's OWN
# source (src/g6_cli/g6_spec/) already writes -- and therefore, per every
# write, already issues a `1103` read request for (COMMIT carries the same
# `intermediate`/`audio_feature` as the DATA frame before it; upstream just
# discards the reply). This is stronger than "the vendor's Windows app did
# this once in a capture": HANDOFF.md section 8 records that Playback,
# Recording, Lighting and SBX were all exercised against THIS exact unit
# (serial E5004E4F57X) and restored afterwards, so these exact frames have
# already been sent to this exact device, repeatedly, and it is fine.
#
# Derived by grep, not copied from memory -- see docs/hid-probe-findings.md
# ("Why the default sweep is deliberately narrow") for the full derivation
# and which g6_spec function contributes each index. The pcap-confirmed set
# from payloads/raw/ (family 0x95, indices {00,04,05,13,2c}) is a *subset*
# of this -- captured traffic happened not to exercise an EQ-preset change,
# but the function that sends those extra indices ships in this app and
# HANDOFF.md records "mic EQ + presets all confirmed working by ear".
TIER1_INDICES: dict[int, list[int]] = {
    # recording.py: AEC toggle (0x00), voice-clarity/noise-reduction toggle
    # (0x04) + level (0x05), mic-EQ toggle (0x13) + all 8 EQ-band values sent
    # together on every preset apply (0x14-0x1B), recording Smart Volume
    # toggle (0x2C).
    FAMILY_RECORDING: [0x00, 0x04, 0x05, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x2C],
    # sbx.py: the 11 AudioFeature ids (all wired into the GUI's SBX page --
    # Surround/Dialog+/SmartVolume/Crystalizer/Bass toggles+sliders, plus
    # SmartVolume Special). playback.py's toggle_to_speakers()/
    # toggle_to_headphones() (wired into the GUI's Playback page Output
    # radio) additionally send 0x06 and 0x09-0x14 under this same family.
    FAMILY_PLAYBACK: [
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B,
        0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12, 0x13, 0x14, 0x18, 0x19,
    ],
    # decoder.py: decoder_mode(), wired into the GUI's Playback page. Unlike
    # the two families above, HANDOFF.md's hardware-exercise list does not
    # name "Decoder" specifically (it names Playback/Recording/Lighting/SBX)
    # -- included here because it is unambiguously an app-issued frame from
    # source, but flagged as the one index in this tier without an explicit
    # by-name hardware citation.
    FAMILY_DECODER: [0x02],
}

# TIER 2 (--include-documented): (family, index) pairs doc/usb-spec.md
# records for the 1103/1207 pair that TIER1_INDICES does NOT already cover
# -- i.e. documented, but not something this app's own source sends. After
# widening tier 1 above, this is now down to a single entry: family 0x96
# index 0x17 ("Physical Speakers Configuration" / "Desktop Speakers" in
# doc/usb-spec.md -- a feature this app does not implement).
TIER2_INDICES: dict[int, list[int]] = {
    FAMILY_PLAYBACK: [0x17],
}

# TIER 3 (--include-speculative): undocumented family bytes, tried only at
# index 0, plus (opt-in via --speculative-index-range) a wider index walk.
# 0x9B is deliberately excluded even though it would only ever land in the
# `intermediate` field here (never the command byte the flash dispatcher
# actually switches on -- see _assert_safe) -- belt-and-suspenders, given
# there is exactly one G6 and no replacement.
DEFAULT_E0_RECHECK_SUBS = [1, 9]
DEFAULT_BONUS_FAMILIES = [f for f in range(0x90, 0xA0) if f not in FORBIDDEN_COMMANDS]

SPECULATIVE_WARNING = """
  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !! SPECULATIVE TIER SELECTED (--include-speculative)                    !!
  !!                                                                      !!
  !! Everything below sends frames that NOBODY has observed the vendor's !!
  !! own software sending to this device. There is exactly one G6 for    !!
  !! this project and no replacement -- "you can't assume anything       !!
  !! regarding the usb spec" (the device's owner). Proceed only if you   !!
  !! understand that these are genuinely untested inputs.                !!
  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
"""

BANNER = f"""
{"=" * 78}
 G6 HID readback probe -- v4, retuned to a proven-safe default
{"=" * 78}
 Ground truth (from payloads/raw/*.pcapng, direction confirmed by USBPcap):

   5A 12 07 <intermediate> <audio_feature> <value>   HOST  -> DEVICE  write
   5A 11 03 <intermediate> <audio_feature> 00000000  HOST  -> DEVICE  read request
   5A 11 08 01 00 <family> <index> <value>           DEVICE -> HOST  read response
   5A 02 0A <echoed-cmd> <status>                     DEVICE -> HOST  generic ACK

 There is exactly one G6 for this project and no replacement, so the default
 sends ONLY tier 1: 5A 11 03 read requests for every (family, index) pair
 this app's OWN source (src/g6_cli/g6_spec/) already writes -- families
 0x95/0x96/0x97, {sum(len(v) for v in TIER1_INDICES.values())} indices total, derived by grep, not guessed.
 HANDOFF.md records Playback/Recording/Lighting/SBX were all exercised
 against this exact unit and restored, so these exact frames have already
 been sent to this exact device, repeatedly. Nothing wider runs unless you
 explicitly ask for it: --include-documented adds the one (family, index)
 doc/usb-spec.md records that this app's source does not already send
 (0x96/0x17); --include-speculative adds everything else, including the
 already-answered 0xE0 recheck and any undocumented family or index range
 you opt into.

 --baseline is the one deliberate, non-tiered exception: a real, reversible,
 already-used WRITE (DAC filter re-selection via
 g6_cli.g6_spec.playback.playback_filter()), sent so you have a known-good
 ACK to compare rejections against.

 This script never builds a frame targeting command 0x9B (155) or containing
 byte pair AA 55 / 55 AA anywhere -- the firmware's flash-update handshake.

 Do not run this with --send while playing or recording audio.
{"=" * 78}
"""


@dataclass
class ProbeCase:
    campaign: str
    label: str
    request: bytes


@dataclass
class ProbeResult:
    case: ProbeCase
    sent: bool
    response: bytes | None
    error: str | None


def _assert_safe(frame: bytes) -> None:
    """Last-line safety net: refuse to build anything near the flash protocol."""
    command = frame[OFF_COMMAND]
    if command in FORBIDDEN_COMMANDS:
        raise AssertionError(
            f"refusing to build a frame targeting command 0x{command:02X} -- "
            "this is the firmware's flash-update protocol (docs/g6-re/REPORT.md, "
            "sub 155/0x9B, AA55/55AA handshake). This script must never touch it."
        )
    for forbidden in FORBIDDEN_BYTE_PAIRS:
        if forbidden in frame:
            raise AssertionError(
                f"refusing to send a frame containing {forbidden.hex()} anywhere -- "
                "that is the flash-protocol unlock handshake byte pair."
            )


def build_frame(
    command: int,
    op: int,
    *,
    intermediate: bytes = b"\x00\x00",
    audio_feature: int = 0x00,
    value: bytes = b"\x00\x00\x00\x00",
) -> bytes:
    """Build a 64-byte frame in the layout confirmed against real captures."""
    if len(intermediate) != 2:
        raise ValueError(f"intermediate must be 2 bytes, got {intermediate!r}")
    if len(value) != 4:
        raise ValueError(f"value must be 4 bytes, got {value!r}")
    frame = bytearray(FRAME_LEN)
    frame[0] = PREFIX
    frame[OFF_COMMAND] = command & 0xFF
    frame[OFF_OP] = op & 0xFF
    frame[OFF_INTERMEDIATE : OFF_INTERMEDIATE + 2] = intermediate
    frame[OFF_AUDIO_FEATURE] = audio_feature & 0xFF
    frame[OFF_VALUE : OFF_VALUE + 4] = value
    result = bytes(frame)
    _assert_safe(result)
    return result


def build_read_request(family: int, index: int) -> bytes:
    """`5A 11 03 01 <family> <index> 00000000 ...` -- the confirmed read primitive."""
    return build_frame(
        CMD_READ,
        OP_READ_REQUEST,
        intermediate=bytes([0x01, family & 0xFF]),
        audio_feature=index,
    )


def build_e0_recheck_frame(sub_sub: int) -> bytes:
    """The exact frame shape v1 sent: `5A E0 01 <sub_sub> 00...`.

    Kept byte-for-byte identical to the original probe on purpose -- the
    point of this campaign is to reconfirm the known answer, not to try
    something new against a command we have evidence is rejected.
    """
    frame = bytearray(FRAME_LEN)
    frame[0] = PREFIX
    frame[OFF_COMMAND] = CMD_GET_GROUP
    frame[OFF_OP] = 0x01
    frame[OFF_INTERMEDIATE] = sub_sub & 0xFF
    result = bytes(frame)
    _assert_safe(result)
    return result


def decode_hint(response: bytes) -> str | None:
    """Best-effort decode of the two response shapes confirmed against real
    captures (see module docstring). Returns None if the response doesn't
    match either shape -- callers should fall back to a plain hexdump.
    """
    if len(response) < 7:
        return None
    if response[0] != PREFIX:
        return None
    cmd, op = response[1], response[2]
    if cmd == CMD_ACK and op == OP_ACK and len(response) >= 5:
        echoed_cmd, status = response[3], response[4]
        status_word = "OK" if status == 0x00 else "non-zero -- likely error/unsupported [inferred]"
        return f"ACK: echoes cmd 0x{echoed_cmd:02X}, status 0x{status:02X} ({status_word})"
    if cmd == CMD_READ and op in (OP_READ_RESPONSE, 0x0E) and len(response) >= 11:
        # Confirmed shape for op 0x08: [3]=0x01 (echo of intermediate's fixed
        # high byte) [4]=0x00 (secondary/status?) [5]=family [6]=index
        # [7:11]=value. Op 0x0E was seen once, for a longer reply, and is
        # printed with the same field guesses -- unconfirmed for that length.
        marker, secondary, family, index = response[3], response[4], response[5], response[6]
        value_bytes = response[7:11]
        try:
            import struct

            as_float = struct.unpack("<f", value_bytes)[0]
        except Exception:
            as_float = None
        as_float_str = f", as float={as_float:g}" if as_float is not None else ""
        return (
            f"READ RESPONSE (op 0x{op:02X}{'​, unconfirmed length' if op != OP_READ_RESPONSE else ''}): "
            f"marker=0x{marker:02X} secondary=0x{secondary:02X} "
            f"family=0x{family:02X} index=0x{index:02X} value={value_bytes.hex()}{as_float_str}"
        )
    return None


def hexdump(data: bytes | None, *, indent: str = "  ") -> str:
    if data is None:
        return f"{indent}<no data>"
    lines = []
    for offset in range(0, len(data), 16):
        chunk = data[offset : offset + 16]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{indent}{offset:02x}: {hex_part:<47}  {ascii_part}")
    return "\n".join(lines)


def find_hid_device_path() -> bytes | None:
    """Locate the G6's control HID interface (4), the same one g6_cli uses.

    Read-only enumeration -- does not open or write to anything.
    """
    import hid

    for entry in hid.enumerate(G6_VENDOR_ID, G6_PRODUCT_ID):
        if entry.get("interface_number") == G6_HID_INTERFACE:
            return entry["path"]
    return None


def send_and_read(device_path: bytes, frame: bytes, *, timeout_s: float) -> bytes:
    """Send one frame and read back one 64-byte response, or raise TimeoutError.

    Mirrors g6_cli.g6_core.G6Device.HidInterface.send_hid_data_to_device: a
    0x00 report-id byte is prepended before the 64-byte payload, because
    hidapi otherwise treats the first real payload byte as the report id and
    drops it. Uses a Python-level poll loop for the timeout (not the `timeout`
    shell command, which does not exist on macOS).
    """
    import hid

    h = hid.device()
    try:
        h.open_path(device_path)
        h.set_nonblocking(1)
        report = bytes([0x00]) + frame
        h.write(list(report))

        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            response = h.read(FRAME_LEN)
            if response:
                return bytes(response)
            time.sleep(0.02)
        raise TimeoutError(f"no response within {timeout_s:.1f}s")
    finally:
        h.close()


def parse_int_list(spec: str, *, base: int = 10) -> list[int]:
    """Parse "1-9" or "1,3,5" or "1,4-6" into a sorted, deduplicated list.

    `base` controls how each token is interpreted -- 10 for the decimal
    sub-sub convention v1 used, 16 for family/index bytes (so "95" means
    0x95, matching how they're written throughout fw_notes.md and this
    script's own docstring).
    """
    values: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            values.update(range(int(lo, base), int(hi, base) + 1))
        else:
            values.add(int(part, base))
    return sorted(values)


def build_baseline_cases(filter_name: str) -> list[ProbeCase]:
    """Known-good, non-destructive baseline: re-select a DAC playback filter,
    built with the SAME upstream helper the app itself calls
    (g6_cli.g6_spec.playback.playback_filter), not a hand-rolled frame.

    Why this command: it's one of the four filters already exposed on the
    GUI's Playback tab and already sent during ordinary use, so this is
    provably a command this app already issues -- not new protocol surface.
    There is no readback of "what filter is currently active" (see
    docs/device-state.md), so this WILL select --baseline-filter regardless
    of what's currently set; that's audible but harmless and reversible --
    just re-select your preferred filter afterward via the GUI's Playback
    tab if this changed it.

    Given the now-confirmed generic ACK shape (5A 02 0A <echoed-cmd>
    <status>, see module docstring), the prediction is that both frames
    below get back 5A 02 0A 6C 00 -- but command 0x6C (the DAC filter
    command) never appears anywhere in payloads/raw/*.pcapng, so this is
    the first time this project will have real evidence either way.
    """
    from g6_cli.g6_spec import PlaybackFilter
    from g6_cli.g6_spec.playback import playback_filter

    playback_filter_enum = PlaybackFilter[filter_name]
    fragments = playback_filter(playback_filter_enum)
    labels = [
        f"playback_filter({filter_name}) data phase (stage the filter value)",
        f"playback_filter({filter_name}) commit phase (apply it)",
    ]
    return [
        ProbeCase("baseline", label, bytes.fromhex(str(frag)))
        for frag, label in zip(fragments, labels)
    ]


def build_read_cases(campaign: str, family: int, indices: list[int], *, note: str = "") -> list[ProbeCase]:
    suffix = f" ({note})" if note else ""
    return [
        ProbeCase(
            campaign,
            f"5A 11 03 family=0x{family:02X} index=0x{index:02X}{suffix}",
            build_read_request(family, index),
        )
        for index in indices
    ]


def build_tier1_cases() -> list[ProbeCase]:
    """The default: every (family, index) this app's own source already
    writes (and therefore already issues a matching read request for). See
    TIER1_INDICES's definition for the derivation and per-index citations.
    """
    cases = []
    for family, indices in TIER1_INDICES.items():
        cases += build_read_cases(
            "tier1-app-issued", family, indices, note="this app already sends this"
        )
    return cases


def build_tier2_cases() -> list[ProbeCase]:
    """--include-documented: (family, index) pairs doc/usb-spec.md records
    that TIER1_INDICES does not already cover -- documented, but not
    something this app's own source sends.
    """
    cases = []
    for family, indices in TIER2_INDICES.items():
        cases += build_read_cases(
            "tier2-documented", family, indices, note="documented, not sent by this app"
        )
    return cases


def build_e0_recheck_cases(sub_subs: list[int]) -> list[ProbeCase]:
    return [
        ProbeCase(
            "tier3-e0-recheck",
            f"5A E0 01 sub-sub={n} (speculative -- expect ACK matching "
            f"{KNOWN_E0_REJECTION_PREFIX.hex()}...)",
            build_e0_recheck_frame(n),
        )
        for n in sub_subs
    ]


def build_family_bonus_cases(bonus_families: list[int]) -> list[ProbeCase]:
    """Speculative: documented families are only 0x95/0x96. This tries
    nearby, undocumented family bytes at index 0, in case anything else
    responds differently.
    """
    return [
        ProbeCase(
            "tier3-family-bonus",
            f"5A 11 03 family=0x{family:02X} index=0x00 (undocumented, speculative)",
            build_read_request(family, 0x00),
        )
        for family in bonus_families
    ]


def build_tier3_cases(args: argparse.Namespace) -> list[ProbeCase]:
    """--include-speculative: e0-recheck + undocumented-family bonus, plus
    (only if --speculative-index-range was given) a wider index walk across
    families 0x95/0x96/0x97, beyond what tiers 1 and 2 already cover.
    """
    cases = build_e0_recheck_cases(args.e0_recheck_subs)
    cases += build_family_bonus_cases(args.speculative_families)
    if args.speculative_index_range:
        covered: dict[int, set[int]] = {}
        for family, indices in TIER1_INDICES.items():
            covered.setdefault(family, set()).update(indices)
        for family, indices in TIER2_INDICES.items():
            covered.setdefault(family, set()).update(indices)
        for family in (FAMILY_RECORDING, FAMILY_PLAYBACK, FAMILY_DECODER):
            extra = sorted(set(args.speculative_index_range) - covered.get(family, set()))
            cases += build_read_cases(
                "tier3-index-walk", family, extra, note="speculative index walk, beyond tiers 1+2"
            )
    return cases


def print_campaign_summary(campaign: str, results: list[ProbeResult]) -> None:
    sent_results = [r for r in results if r.response is not None]
    error_results = [r for r in results if r.error]
    print(
        f"\n--- {campaign}: {len(results)} case(s), {len(sent_results)} response(s), "
        f"{len(error_results)} error(s) ---"
    )
    if error_results:
        for r in error_results[:5]:
            print(f"  error: {r.case.label}: {r.error}")
        if len(error_results) > 5:
            print(f"  ... and {len(error_results) - 5} more errors")
    if not sent_results:
        return

    groups: dict[bytes, list[ProbeResult]] = {}
    for r in sent_results:
        groups.setdefault(r.response, []).append(r)
    ordered = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    majority_response = ordered[0][0]

    for response, group_results in ordered:
        marker = "" if response == majority_response else "   <-- DIFFERENT from the common response"
        print(f"  {len(group_results):>3}x  {response.hex()}{marker}")
        hint = decode_hint(response)
        if hint:
            print(f"        {hint}")
        if response != majority_response:
            labels = ", ".join(r.case.label for r in group_results[:8])
            more = "" if len(group_results) <= 8 else f" (+{len(group_results) - 8} more)"
            print(f"        produced by: {labels}{more}")
            print(hexdump(response, indent="        "))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--send", action="store_true", help="Actually open the device and transmit frames.")
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Also send the known-good baseline (DAC filter re-select via "
        "g6_spec.playback.playback_filter) before the sweep campaigns, so you "
        "have a confirmed-good ACK to compare rejections against.",
    )
    parser.add_argument(
        "--baseline-filter",
        default="FAST_ROLL_OFF_MINIMUM_PHASE",
        choices=[
            "FAST_ROLL_OFF_MINIMUM_PHASE",
            "SLOW_ROLL_OFF_MINIMUM_PHASE",
            "FAST_ROLL_OFF_LINEAR_PHASE",
            "SLOW_ROLL_OFF_LINEAR_PHASE",
        ],
        help="Which of the four real PlaybackFilter enum values --baseline sends "
        "(default: %(default)s). This WILL become the device's active filter -- "
        "audible, harmless, reversible.",
    )
    parser.add_argument(
        "--include-documented",
        action="store_true",
        help="Add tier 2: the (family, index) pairs doc/usb-spec.md documents that this "
        "app's own source does NOT already send (currently one: family 0x96 index 0x17, "
        "'Physical Speakers Configuration'). Documented elsewhere, not app-issued -- a "
        "separate tier from the default for that reason.",
    )
    parser.add_argument(
        "--include-speculative",
        action="store_true",
        help="Add tier 3: frames NOBODY has observed the vendor's software sending -- "
        "the already-answered 0xE0 recheck, a bonus sweep of undocumented family bytes, "
        "and (with --speculative-index-range) a wider index walk. Prints a loud warning "
        "before building anything. There is exactly one G6 for this project and no "
        "replacement -- read the warning before using this.",
    )
    parser.add_argument(
        "--speculative-index-range",
        default="",
        help="Hex index range (e.g. '0-3f') to additionally walk across families 0x95 "
        "and 0x96, beyond the fixed proven-safe/documented index sets. Only takes effect "
        "with --include-speculative. Empty (default) = no index walk at all -- the "
        "one-device constraint means breadth must be opted into explicitly, not defaulted.",
    )
    parser.add_argument(
        "--speculative-families",
        default=f"{min(DEFAULT_BONUS_FAMILIES):x}-{max(DEFAULT_BONUS_FAMILIES):x}",
        help="Hex family bytes to try (at index 0 only) under --include-speculative "
        "(default: %(default)s -- undocumented, speculative).",
    )
    parser.add_argument(
        "--e0-recheck-subs",
        default=",".join(str(n) for n in DEFAULT_E0_RECHECK_SUBS),
        help="Sub-subs to reconfirm the 0xE0 rejection with, under --include-speculative "
        "(default: %(default)s). Decimal.",
    )
    parser.add_argument("--timeout", type=float, default=1.0, help="Seconds to wait for a response per frame (default: 1.0).")
    parser.add_argument("--delay", type=float, default=0.2, help="Seconds to sleep between frames (default: 0.2).")
    parser.add_argument("--yes", action="store_true", help="Skip the interactive confirmation prompt that --send otherwise shows.")
    args = parser.parse_args(argv)

    print(BANNER, file=sys.stderr)

    try:
        args.e0_recheck_subs = parse_int_list(args.e0_recheck_subs, base=10)
        args.speculative_families = parse_int_list(args.speculative_families, base=16)
        args.speculative_index_range = (
            parse_int_list(args.speculative_index_range, base=16)
            if args.speculative_index_range.strip()
            else []
        )
    except ValueError as exc:
        print(f"Could not parse a numeric argument: {exc}", file=sys.stderr)
        return 2

    # Belt-and-suspenders: 0x9B is never allowed as a family byte either,
    # even though it would only ever land in `intermediate` here (never the
    # command byte the flash dispatcher switches on -- see _assert_safe).
    # Filtered unconditionally, including on an explicit --speculative-families
    # override, given there is exactly one G6 and no replacement.
    filtered = [f for f in args.speculative_families if f not in FORBIDDEN_COMMANDS]
    if len(filtered) != len(args.speculative_families):
        print(
            "Note: dropped family byte(s) matching the flash-protocol command "
            f"{sorted(FORBIDDEN_COMMANDS)} from --speculative-families.",
            file=sys.stderr,
        )
    args.speculative_families = filtered

    tiers_selected = ["tier1-app-issued (default)"]
    all_cases: list[ProbeCase] = list(build_tier1_cases())

    if args.include_documented:
        tiers_selected.append("tier2-documented (--include-documented)")
        all_cases.extend(build_tier2_cases())

    if args.include_speculative:
        tiers_selected.append("tier3-speculative (--include-speculative)")
        print(SPECULATIVE_WARNING, file=sys.stderr)
        all_cases.extend(build_tier3_cases(args))

    if args.baseline:
        all_cases = build_baseline_cases(args.baseline_filter) + all_cases

    print(
        f"Prepared {len(all_cases)} case(s): "
        f"{'baseline + ' if args.baseline else ''}{', '.join(tiers_selected)}",
        file=sys.stderr,
    )

    if args.send and not args.yes:
        speculative_note = (
            " This INCLUDES the speculative tier -- frames nobody has observed the "
            "vendor sending, per the warning above."
            if args.include_speculative
            else ""
        )
        reply = input(
            f"About to transmit {len(all_cases)} frame(s) to a real G6 "
            f"({'including the --baseline WRITE' if args.baseline else 'read-only'})."
            f"{speculative_note} "
            "Make sure nothing is playing or recording through it. Continue? [y/N] "
        )
        if reply.strip().lower() not in ("y", "yes"):
            print("Aborted.", file=sys.stderr)
            return 1

    device_path: bytes | None = None
    if args.send:
        device_path = find_hid_device_path()
        if device_path is None:
            print(
                "No Sound Blaster X G6 HID control interface (VID "
                f"{G6_VENDOR_ID:#06x}, PID {G6_PRODUCT_ID:#06x}, interface "
                f"{G6_HID_INTERFACE}) was found. Nothing will be sent.",
                file=sys.stderr,
            )

    results: list[ProbeResult] = []
    current_campaign = None
    for case in all_cases:
        if case.campaign != current_campaign:
            current_campaign = case.campaign
            print(f"\n=== campaign: {current_campaign} ===")
        if not args.send:
            print(f"[dry run] {case.label}: request={case.request.hex()}")
            results.append(ProbeResult(case, sent=False, response=None, error=None))
            continue

        if device_path is None:
            results.append(ProbeResult(case, sent=False, response=None, error="device not found"))
            continue

        try:
            response = send_and_read(device_path, case.request, timeout_s=args.timeout)
            print(f"{case.label}: request={case.request.hex()} response={response.hex()}")
            results.append(ProbeResult(case, sent=True, response=response, error=None))
        except Exception as exc:  # noqa: BLE001 - this is a diagnostic tool, report everything
            print(f"{case.label}: request={case.request.hex()} <error: {exc}>")
            results.append(ProbeResult(case, sent=True, response=None, error=str(exc)))
        time.sleep(args.delay)

    print("\n" + "=" * 78)
    print("Grouped summary (identical responses collapsed -- paste this back):")
    print("=" * 78)
    by_campaign: dict[str, list[ProbeResult]] = {}
    for r in results:
        by_campaign.setdefault(r.case.campaign, []).append(r)
    for campaign, campaign_results in by_campaign.items():
        print_campaign_summary(campaign, campaign_results)

    if args.send:
        e0_results = [
            r for r in results if r.case.campaign == "tier3-e0-recheck" and r.response is not None
        ]
        if e0_results:
            reproduced = all(r.response.startswith(KNOWN_E0_REJECTION_PREFIX) for r in e0_results)
            if reproduced:
                print(
                    f"\ntier3-e0-recheck: reproduced the known rejection "
                    f"({KNOWN_E0_REJECTION_PREFIX.hex()}...) for all {len(e0_results)} case(s). "
                    "Command 0xE0 remains answered-negative on this firmware."
                )
            else:
                print(
                    "\ntier3-e0-recheck: DID NOT reproduce the known rejection -- this is new "
                    "and worth a closer look. See the campaign detail above."
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
