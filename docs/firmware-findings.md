# Firmware findings — what the G6's own code says

A user-facing digest of an independent firmware reverse-engineering project,
[`HyperRamzey/g6-re`](https://github.com/HyperRamzey/g6-re), vendored
read-only at [`docs/g6-re/`](g6-re/). Credit for the underlying analysis is
entirely theirs: five public G6 firmware releases (2019–2025) and Creative's
decompiled Windows app, disassembled and cross-checked live against a real G6
on Windows. This page restates it in terms relevant to a user of *this* app.

## Evidence convention

**[TESTED]** = observed on real hardware by this project, with a date.
**[INFERRED]** = everything else, including g6-re's own firmware
disassembly/decompile (solid static analysis, but not independently
re-verified by this project — no G6 was attached to the machine most of this
was written on) and the web sources named inline. See g6-re's
[`REPORT.md`](g6-re/REPORT.md) and [`docs/fw_notes.md`](g6-re/docs/fw_notes.md)
for exact addresses and decompiled code.

---

## 1. The full-scale distortion issue — real, old, and permanent

**[INFERRED]** (Audio Science Review, March 2019): at 0 dBFS the G6's low end
distorts — THD+N near 1% at 20 Hz — and dropping level by 2 dB fixes it
(SINAD ~107 dB → ~112 dB). ASR's own diagnosis: analog, not digital —
bus-powered over USB, likely insufficient input capacitance to ride out a
full-scale low-frequency peak.

**[INFERRED]** (g6-re firmware diff, all five public releases
v1.13–2.1.250903.1324): every DSP/DAC-relevant constant — the 57/66-float
parameter tables, master-gain ladder, headphone gain-patch tables, SPDIF
passthrough registers, boot parameters — is **byte-identical across all six
years**. No headroom-trim constant was ever added to the gain path. This is a
hardware property, not an unpatched bug: it affects every G6 on every
firmware version, and no firmware update will fix an analog power-supply
headroom limit. g6-re did not run the live THD+N measurement themselves (a
script exists, `tools/thd_test.py`, but needs tones plus a loopback cable;
deliberately deferred) — the verdict rests on the firmware diff plus ASR's
2019 measurement, not a fresh one.

See [`settings-reference.md`'s full-scale volume section](settings-reference.md#full-scale-volume--the-g6-distorts-at-100)
for the macOS Audio tab's handling of this, and its
[open question #13](settings-reference.md#volume-forwards-to-the-device-not-the-host)
for whether the attenuation happens digitally or in the analog stage —
unresolved, and exactly what `thd_test.py` would settle.

## 2. What Direct Mode actually does inside the device

**[INFERRED]** (firmware disassembly): Direct Mode is not a DSP mode or an
analog bypass relay — the control MCU refuses to send effect parameters to
the DSP at all. The write dispatcher checks a RAM flag (`0x1001422C` in 2025
firmware, an equivalent flag in 2019) before every op-150 (SBX/effects)
write, and returns without writing when Direct Mode is on. Only master
volume (a separate register block) keeps reaching the DSP. SPDIF-Out Direct
additionally hard-switches the optical output's I²C registers to bit-perfect
passthrough.

This explains, mechanistically, what `docs/settings-reference.md` already
documents from Creative's knowledge-base articles and listening tests on real
hardware: Direct Mode silences SBX, the EQ, Scout Mode, What-U-Hear and
microphone recording all at once — enforced by the device's own firmware, not
by any host software's cooperation. The Output Mode radio (`Audio Effects` /
`Direct` / `SPDIF-Out Direct`) is not a UI convention a different program
could ignore.

## 3. Virtual 7.1

Full explanation: [`settings-reference.md`'s Virtual 7.1 section](settings-reference.md#virtual-71).
Short version, **[INFERRED]** (g6-re, live-tested on Windows): the G6 has
exactly two analog output channels. In 7.1 mode the host streams 8 channels
over USB, and the device's own DSP — not the host — renders that down to a
binaural stereo mix using the SBX/HRTF engine. Direct Mode disables this the
same way it disables everything else in §2.

**[TESTED]**, 2026-09-17, real G6: Core Audio reports the device's current
format, and its full 8-entry available-format list, as entirely 2-channel
(`has_non_stereo_formats()` returns `False`) — confirming on macOS
specifically what the firmware evidence explains in principle: there is no
channel-count command anywhere in the ecosystem.

## 4. The hidden fifth DAC filter — Non-Over-Sampling (NOS)

**[INFERRED]** (g6-re, live-queried via Creative's SoundCore layer): the
G6's CS43131 DAC reports **five** filter modes; Creative's Windows app shows
four.

| Index | SoundCore code | Filter |
|---|---|---|
| 0 | 3 | Fast Roll-off, Minimum Phase |
| 1 | 4 | Slow Roll-off, Minimum Phase |
| 2 | **5** | **Non-Over-Sampling (NOS)** |
| 3 | 6 | Fast Roll-off, Linear Phase |
| 4 | 7 | Slow Roll-off, Linear Phase |

Creative's decompiled `BaseFiltersPageViewModel.InitializeSetupDACFilter`
hard-skips the entry named `"NonOverSampling"` by name when building the
filter list — nothing rejects it at the device or firmware level. The
CS43131 datasheet (Cirrus DS1155F2, §5.9) documents NOS as a real, supported
silicon mode with its own pop-free enable/disable sequence.

The wire command, cross-checked against this repo's own `doc/usb-spec.md`
and `payloads/raw/` captures and matching exactly: filter selection is
`5A 6C 03 00 <payload>` followed by commit `5A 6C 01 01`, where payload is
the SoundCore code minus 2. The four visible filters are payloads
`0001`/`0002`/`0004`/`0005`; **NOS is `0003`**, the one value the capture
catalogue never records because Creative's own software never sends it.

Listening detail (droop, images, pre-ringing) is in
[`settings-reference.md`'s filter section](settings-reference.md#filter--five-reconstruction-filters-including-a-hidden-one).
This app offers NOS as a fifth option (`src/g6_gui/filters.py`), with a
warning when it's selected.

## 5. The feature mask — hidden-but-on versus locked-off

**[INFERRED]** (g6-re, live-read on Windows): every G6 reports a capability
bitmask on request; `FeatureBitwiseMask1 = 0x5041B810`. Creative runs one
shared firmware codebase across many products and switches features on or
off per device model. Two categories fall out of it:

**Enabled in the mask, but never wired up in Creative's own G6 app** — usable
today by any software that speaks the protocol directly, no firmware change
needed:

- **`SpeakersHRTFMode`** (bit 30) — see §6.
- **`MalcolmParameterCustomization`** (bit 16) — an engineering/debug
  interface into the DSP's 159 named parameters (AEC, noise reduction,
  VoiceFX, mic EQ, reverb, CMSS-3D, and more). The read side was confirmed
  live; the write side exists in Creative's own COM library but wasn't
  exercised.
- Front-panel **button emulation** and **jack-state queries** — software can
  press the G6's physical buttons and read its jacks over the same protocol.
- A **firmware flash protocol** over HID (the same mechanism the official
  installer uses) — located and documented, but deliberately never
  exercised, since a failed write could brick the device.

**Present in the shared firmware, but this personality actively rejects it**
(the firmware itself returns an error):

- **96 kHz optical-in passthrough** — the handler exists; the G6 rejects the
  command with `E_FAIL`. This specific product's firmware personality says
  no, even though the silicon can very likely do it.
- **Host-controlled headphone gain** — the physical gain switch works; a
  software command to do the same is refused. Gain stays a front-panel-only
  control by design.
- Bluetooth, relay mode, and add-on installs are not merely masked off — the
  G6 has no radio hardware for them at all, and the firmware dispatcher
  doesn't implement the handlers.

**[INFERRED]**, unexplained even by g6-re themselves: the firmware's
acknowledgement byte for enabling Direct Mode changed from `0x81` in the 2019
firmware to `0x83` in the 2025 firmware — a new capability bit appeared with
no corresponding feature anywhere in Creative's app.

## 6. HRTF mode — what it is, and why this app doesn't touch it

A head-related transfer function (HRTF) is a filter that encodes how a
sound's frequency content changes depending on the angle it arrives from
relative to your ears and head shape. Applying the right HRTF filter is what
lets a virtual-surround mix on stereo headphones sound like it's coming from
beside or behind you — the core trick behind every "virtual surround" or
"binaural" feature on a gaming headset or DAC, including this device's.

**[INFERRED]** (g6-re, live-tested): the G6's firmware implements
`SpeakersHRTFMode` (feature bit 30, enabled in the mask). g6-re set it
directly over HID (`SetSpeakersHRTFMode(1)`), got a success response, and
confirmed the device retained it — then set it back to 0, restoring the
device exactly as found. Creative's own G6 app only touches this feature
indirectly, wiring it into a single confusingly-named toggle ("USB HP
Virtualization") rather than exposing `SpeakersHRTFMode` as its own control.
This app's `--sbx-surround` is the closest existing equivalent — Creative
describes Surround as "HRTF-based virtualisation" — but it is not the same
protocol message as `SpeakersHRTFMode` itself.

**This app does not implement `SpeakersHRTFMode` as its own control, and
that is a deliberate choice:**

- It would require a new HID message (`SET 30`, `5A 1E 02 <0|1>` per g6-re's
  decode) that nothing in this codebase currently sends. `src/g6_cli` is
  upstream and frozen (`HANDOFF.md` §2), so it would need a new,
  non-upstream module, the way `src/g6_gui/filters.py` added the NOS filter.
- Per g6-re's own read of the feature — grouped with the Speaker-Model/Preset
  structures belonging to the X3/Avalon speaker-dock product line, which the
  G6's firmware merely retains handlers for — it's primarily meant for
  **speaker output**, not headphones, and the device available to develop
  and test this app is used with headphones. There's no way to evaluate
  whether toggling it does anything audible without a speaker setup.
- It's parked, not rejected: the wire message is simple, so implementing it
  isn't hard *if* someone can test it.

## 7. Sound BlasterX G6 versus "G6X" — what the evidence actually shows

The vendored `docs/g6-re/docs/LINUX-ECOSYSTEM.md` lists a third-party project
supporting "both G6 (041e:3256) and G6X (041e:3263)." This is surprising
since Creative has only ever marketed one G6.

**[INFERRED]** (web, solid): Creative did release a second hardware revision
of this exact product, the **Sound BlasterX G6 (USB-C)**, model number
`SBX-G6UC`, still sold under the *Sound BlasterX* name on Creative's own
current product pages. Coverage describes it as a connector and software
refresh — Micro-USB-B to USB-C, a newer Sound Blaster Command build — while
keeping the same headline specs (32-bit/384 kHz Direct Mode, 130 dB DAC, 1 Ω
output impedance, 16–600 Ω headphone range): the same DAC/amp generation with
a modernised port, not a new product tier.

**[INFERRED]** (web, thin — treat with real skepticism): two independent,
community-maintained USB-ID databases (not Creative, not this project) list
USB PID `0x3263` under Creative's vendor ID as belonging to a much older,
unrelated product — the **SB X-Fi Surround 5.1 Pro** (roughly 2008–2009) —
not any version of the G6, directly conflicting with the third-party Linux
project's "G6X" label. Neither claim could be confirmed against real hardware
or an authoritative Creative source; community USB-ID listings are
crowd-submitted and can be stale, but so can a single hobbyist project's PID
label.

**Best-guess reading, clearly inference:** "G6X" most likely is not an
official Creative product name at all, but a label the third-party Linux
project's author gave the USB-C hardware revision to distinguish it in code —
and the specific PID they recorded for it may or may not be accurate. This
has not been confirmed either way; nothing about a Creative product
officially called "G6X" turned up anywhere in this research.

**Does this app work with the other device?** `src/g6_cli/g6_core.py`
hard-codes:

```python
G6_VENDOR_ID = 0x041e
G6_PRODUCT_ID = 0x3256
```

That is the *original* G6's PID. As shipped, this app will not even see a
device presenting a different PID, let alone talk to it. Whether the wire
protocol reverse-engineered from the original G6 is byte-compatible with a
USB-C hardware revision (different USB controller silicon, quite possibly a
different HID descriptor layout) is completely unverified. **Confidence:
low**, on both the identity of PID `0x3263` and on compatibility. Anyone with
a USB-C G6 wanting to try this app should expect to need to add its PID to
`g6_core.py` (or a non-upstream shim, per the `HANDOFF.md` §2 rule against
touching `src/g6_cli`) and should expect the first attempt to possibly fail
outright rather than silently work.

---

## Sources

- [HyperRamzey/g6-re](https://github.com/HyperRamzey/g6-re) — the vendored
  project this whole page summarises. See `docs/g6-re/README.md`,
  `docs/g6-re/REPORT.md`, `docs/g6-re/docs/fw_notes.md`,
  `docs/g6-re/docs/LINUX.md`, `docs/g6-re/docs/LINUX-ECOSYSTEM.md` in this
  repository.
- Audio Science Review, "Review and Measurements of Sound BlasterX G6," March
  2019 — the original full-scale distortion finding.
- Cirrus Logic CS43131 datasheet (DS1155F2), §5.9 — the NOS filter mode.
- Creative Labs product pages for the Sound BlasterX G6 and the
  [Sound BlasterX G6 (USB-C)](https://us.creative.com/p/sound-blaster/sound-blasterx-g6-usb-c) —
  current official framing of the USB-C revision, checked 2026-09-16.
- guru3d.com and itechguides.com coverage of the USB-C revision (`SBX-G6UC`)
  — the "connector and software refresh, not a new generation" framing.
- Community USB ID listings (devicehunt.com, the-sz.com/products/usbid) for
  PID `0x3263` — the conflicting "SB X-Fi Surround 5.1 Pro" attribution,
  given no weight beyond "this contradicts the ecosystem survey's label."
