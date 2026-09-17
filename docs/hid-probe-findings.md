# HID probe findings — what the probe found, and how to run it

What `experimental/probe-g6-hid.py` sends to a real G6, what came back, and
how to run it. The core protocol grammar (write / read-request / read-response
/ ACK frame shapes) is explained once, in
[`device-state.md`](device-state.md#the-control-protocol-and-why-readback-is-real-but-unused);
this page covers what's specific to the probe: the evidence behind its
default sweep, its safety guards, and the commands to run.

## Evidence convention

**[TESTED]** = observed on real hardware by this project, with a date.
**[INFERRED]** = everything else (captured USB traffic, firmware
disassembly, reasoning) — evidence named inline.

---

## What is established

**[TESTED]**, 2026-09-17, real G6: the original probe sent `5A E0 01 <n>`
for n = 1..9 (command `0xE0`, g6-re's documented GET group for "versions,
serial, feature mask"). All nine returned a byte-identical
`5a 02 0a e0 81 00 ...`. No firmware version was obtained.

**[INFERRED]** (captured traffic in `payloads/raw/*.pcapng`, with direction
derived mechanically from USB transfer semantics — a `SET_REPORT` control
transfer can only be host-initiated, an `IN`-endpoint interrupt transfer can
only be device-initiated, not from trusting a logged direction bit): that
reply decodes as the generic ACK `5A 02 0A <echoed-cmd> <status>` — here,
"command `0xE0`, status `0x81`." Every `5A 02 0A` ACK captured anywhere in
this repo (31 examples, across commands `0x12`/`0x3a`/`0x3c`) has
`status == 0x00`, and **no capture contains a failure at all**. So "`0x81` =
rejected" is inferred from contrast with an all-`0x00` sample, not confirmed
against any captured failure — treat it as likely, not established. Command
`0xE0` itself never appears anywhere in `payloads/raw/`.

**[INFERRED]** (same captures): the DSP-register read/write/ACK protocol
described in [`device-state.md`](device-state.md#the-control-protocol-and-why-readback-is-real-but-unused)
is real captured USB traffic, recorded by upstream for unrelated reasons
(documenting mixer/recording/lighting behaviour), not reproduced by this
project against the device. `0x11` and `0x12` separate cleanly by direction
across every frame seen — zero exceptions. That's the strongest evidence in
this document: real traffic, mechanically-derived direction, reproducible by
anyone with the repo.

Mode/direction tally across every file in `payloads/raw/*.pcapng`:

| mode | direction | count | note |
|---|---|---|---|
| `020a` | device→host | 31 | generic ACK |
| `1103` | host→device | 14 | read request |
| `1108` | device→host | 26 | read response |
| `110e` | device→host | 2 | longer reply (14 bytes of payload vs. 8 for the normal case), unexplored — plausibly a compound/stereo read |
| `1207` | host→device | 14 | write |
| `260b` | device→host | 2 | another read-response-shaped frame under a different command, unexplored |
| `3a02`/`3a06`/`3a09` | host→device | 3 each | lighting |
| `3c02` | host→device | 32 | mic boost |
| `3c04` | **both** | 32 dev→host, 8 host→dev | overloaded: host sends `...3c0400...`, device replies `...3c0401...` — the trailing byte plausibly distinguishes query from answer. Not investigated further. |

**[INFERRED], flagged as an open coincidence, not a finding:** g6-re records
the `SetStereoDirectMode` ACK's capability word (offset +4) as `0x81` on 2019
firmware, `0x83` on 2025 (see
[`firmware-findings.md` §5](firmware-findings.md#5-the-feature-mask--hidden-but-on-versus-locked-off)).
The captured `5A 02 0A E0 81` above also has its distinguishing byte at
offset +4. Same value, same offset, but a different command and (per
g6-re's disassembly) a different reply-building code path. This could mean
the firmware reports `0x81` as some default/baseline capability class
regardless of context, or it could be coincidental — offset +4 is simply
where small status bytes tend to land in these frames. Nothing here
distinguishes the two; don't build on it without independent confirmation.

## Why the default sweep is deliberately narrow

There is exactly one G6 for this project and no replacement. In the device
owner's own words: "you can't assume anything regarding the usb spec — if
this device dies I don't have another one." That constraint outranks
coverage.

The sweep's tier 1 is every `(family, index)` pair this app's own source
already writes — not just the 5 pairs that happen to appear in
`payloads/raw/` (family `0x95`, indices `{0x00, 0x04, 0x05, 0x13, 0x2c}`),
but all **37** pairs across `sbx.py`, `recording.py`, `decoder.py` and
`playback.py`. Each of those sends a DATA frame (`5A 12 07`) followed by a
COMMIT frame (`5A 11 03` — confirmed to be the READ REQUEST, see
`device-state.md`) carrying the identical `intermediate`/`audio_feature`. So
for every register this app ever writes, it already asks the device to read
that register back — replaying the request is not new protocol surface; only
the answer is new information.

**[TESTED]**, 2026-09-16, real G6 (serial E5004E4F57X): `HANDOFF.md` §8
records Playback, Recording, Lighting and SBX all exercised against this
exact unit and restored afterward; mic boost, noise reduction, AEC, and mic
EQ + presets confirmed by ear; Recording Smart Volume had no audible effect.
That makes tier 1 frames this application already sends in normal use,
replayed against a device already run against with this exact application
repeatedly, without incident — a stronger safety argument than captured
traffic alone, and why tier 1 could be widened from 5 to 37 entries without
violating the one-device constraint.

Tier-1 set, by source function:

| Family | Indices | From | Exercised against this unit? |
|---|---|---|---|
| `0x95` (recording) | `00,04,05,13,14,15,16,17,18,19,1A,1B,2C` | `recording.py`: AEC toggle, noise-reduction toggle+level, mic-EQ toggle, all 8 EQ-band values, recording Smart Volume toggle | Yes |
| `0x96` (playback/SBX) | `00–14, 18, 19` (23 values) | `sbx.py`'s 11 `AudioFeature` ids; `playback.py`'s speaker/headphone output toggles | Yes |
| `0x97` (decoder) | `02` | `decoder.py`'s `decoder_mode()` | Playback is named as exercised and decoder mode lives on that tab, but this specific index isn't separately cited |

Widening the *index range* further is a different decision from widening
tier 1: tier 1 grew because the evidence changed (source-derived, not
guessed), not because coverage is inherently good. An index-range walk
beyond tiers 1–2 is exactly the "nobody has observed this" input the
one-device constraint is about — it lives behind `--include-speculative`,
with a warning, not a flag away from the default.

## What the rebuilt sweep covers

`experimental/probe-g6-hid.py` has three tiers plus an opt-in baseline:

| Tier | Sends | Why |
|---|---|---|
| 1 — default, no flag | `5A 11 03 01 <family> <index>` for the 37 pairs above (families `0x95`/`0x96`/`0x97`) | This app's own source already writes every one of these; all four areas confirmed exercised and restored (above). |
| 2 — `--include-documented` | Family `0x96` index `0x17` ("Physical Speakers Configuration") | Documented in `doc/usb-spec.md` but not in this repo's own captures and not sent by this app's source — kept as its own tier for that reason. |
| 3 — `--include-speculative` | The `e0-recheck` campaign (replaying the already-answered v1 frames), a bonus sweep of undocumented family bytes `0x90–0x9F` (minus `0x9B`, see guard below), and — only with `--speculative-index-range` — a wider index walk across `0x95`/`0x96`/`0x97` beyond tiers 1+2 | Frames nobody has observed the vendor or this app sending. Prints a loud warning before building anything, given the one-device constraint. |
| `--baseline` (opt-in, outside the tiers) | `g6_cli.g6_spec.playback.playback_filter()`'s real two-frame data+commit sequence, built with upstream's own helper | A known-good, already-used, reversible WRITE, so a rejection elsewhere has something real to compare against. Predicts (untested until run) a `5A 02 0A 6C 00` ACK — command `0x6C` never appears in `payloads/raw/`, so this is first evidence either way. |

Tiers 1 and 2 send only read requests (`5A 11 03`, value always zero); no
tier builds a write frame except `--baseline`, which is the same frame the
GUI already sends during ordinary use.

Responses within each tier collapse to one line per distinct byte string
with a count, so "all N identical" is impossible to miss, and anything that
differs from a tier's majority response prints in full, flagged, and
attributed to the request(s) that produced it.

**Safety guard:** dry-run by default; `--send` plus a `y`/`N` prompt
(`--yes` skips it) to transmit. Every frame is built through `_assert_safe()`,
which refuses to construct anything targeting command `0x9B` (155 decimal)
or containing the byte pair `AA 55`/`55 AA` anywhere — the firmware's
flash-update handshake, per `docs/g6-re/REPORT.md` ("FW dispatcher case
90/155 (0x9B): `AA 55`/`55 AA` handshake ... 4KB erase blocks + write"). No
tier here was ever close to hitting it — dispatch switches on the frame's
command byte, not on a family/index value inside it — and the script
additionally filters `0x9B` out of the speculative family-bonus range
unconditionally, belt-and-suspenders.

## If a firmware-version read is ever found

Command `0xE0` is **[TESTED]** refused on this firmware/personality (above).
The `0x11`/`0x12` family+index scheme confirmed in `device-state.md` only
reaches the op-149/150/151-style DSP register space (recording/playback/
decoder effect parameters, per g6-re) — a different address space from
device identity fields, with no reason to expect a version string there.

If a firmware-version read exists at all, it most likely needs a different,
not-yet-identified top-level command byte, and its reply would plausibly
resemble one of the two device→host shapes already seen: a short
`5A 11 08`-style response (unlikely to fit a string like
`2.1.250903.1324` in 4 bytes), or the longer, unexplored `5A 11 0E` shape
generalised to carry ASCII/BCD bytes instead of a float. Until that command
is identified, this remains **unknown** — the realized result of this
investigation is the general DSP-register readback, not a firmware-version
string.

## Recommended commands

```
./venv/bin/python experimental/probe-g6-hid.py --send --baseline
```

Runs tier 1 (the default — all 37 read requests this app's own source
already sends) plus the baseline DAC-filter re-select, with the usual `y`/`N`
confirmation before anything is transmitted. Paste back the "Grouped
summary" section — that's the part designed to make "everything came back
identical" or "this one row differs" equally impossible to miss.

```
./venv/bin/python experimental/probe-g6-hid.py --send --baseline --include-documented
```

Also tries the one documented-but-not-app-sent index (family `0x96`, `0x17`).

Only after reviewing those results, and only having read "Why the default
sweep is deliberately narrow" above, consider:

```
./venv/bin/python experimental/probe-g6-hid.py --send --baseline --campaigns all
```

which also tries the speculative, undocumented family bytes — it prints a
loud warning first, on purpose.
