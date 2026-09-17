# What every setting actually does

A reference for the options this GUI/CLI exposes on the Sound Blaster X G6:
what each one changes, when it changes nothing at all, and how confident we
are. Written for two readers: someone deciding what to switch on, and someone
writing UI help text. Each section ends with a **Help box** line short enough
to drop into a tooltip; the wording lives in `src/g6_gui/help.py`, the single
source shared with this document.

## Evidence markers

- **[TESTED]** — observed on real hardware by this project, with a date.
- **[INFERRED]** — everything else: firmware disassembly, third-party
  measurements, USB captures made by others, and plain reasoning. The source
  is named inline, e.g. **[INFERRED]** (Audio Science Review measurement) or
  **[INFERRED]** (firmware disassembly, g6-re).

Two facts from [`device-state.md`](device-state.md) shape everything below:
this app **never reads the device back**, so every switch in the UI shows
what was last *sent*, not what the device *is* — even though the control
protocol itself does support reading a value back (see
[Control protocol and readback](#control-protocol-and-readback)); and
settings live in the G6's own firmware, so they persist across reboots and
across operating systems.

---

## The short version

| Setting | What it changes | Works over USB on macOS? |
|---|---|---|
| Output (Speakers/Headphones) | Front headphone jack vs. rear line/optical combo jack | Yes |
| Virtual 7.1 / 5.1 | Renders an 8-channel stream to binaural stereo inside the device's DSP | **No.** **[TESTED 2026-09-17]** Core Audio reports exactly 2 output channels and zero non-stereo formats. Works on Linux/Windows, where the OS opens the device with more channels |
| Volume at 100% | Measurable distortion at full digital scale — a hardware limit present in every firmware release | N/A — applies on every OS |
| Direct Mode | One position of an `Audio Effects · Direct · SPDIF-Out Direct` radio, not a switch. Device stops writing effect registers to the DSP | **No — inert.** **[TESTED 2026-09-16]** (confirmed by ear). macOS's Clock Source overrides it; use the [macOS Audio tab](#macos-audio-tab) instead |
| SPDIF-Out Direct Mode | Same bypass, optical output only; mutually exclusive with Direct Mode on the device | **Unknown, untested** — macOS has no equivalent setting |
| Filter | DAC reconstruction filter, 5 variants (1 hidden by Creative) | Yes, but inaudible except NOS |
| Decoder mode | Dolby Digital dynamic-range compression | **No.** Needs a Dolby bitstream on optical in |
| SBX profile | Picks which slot of `g6.json` you're editing | Yes — and merely selecting a different profile already re-sends it to the device (bug, below) |
| SBX Surround/Crystalizer/Bass/Dialog+ | Real-time playback DSP | Yes |
| SBX Smart Volume | Loudness levelling — slider **or** Night/"Loud", never both | Yes |
| Recording: Noise Reduction, AEC, Smart Volume | CrystalVoice mic processing | Yes (Smart Volume: **[TESTED 2026-09-16]** no audible effect) |
| Mic EQ + presets | 8-band EQ on the mic path | Yes |
| Volume/mute rows | USB Audio Class controls | **No** — macOS's kernel driver owns that interface |

---

# Playback

## Output — Speakers / Headphones

Picks the physical jack the G6 drives:

| UI label | Jack | What is on it |
|---|---|---|
| **Headphones** | Front 3.5 mm | Xamp headphone out; also carries the 3.5 mm mic input |
| **Speakers** | Rear combo jack | Line Out **and** mini-TOSLINK Out — the same socket |

**[INFERRED]** (Creative docs) The rear panel is a pair of combo jacks — Line
Out/optical out, Line In/optical in — each taking a 3.5 mm plug or mini-TOSLINK.
"Speakers" is the whole rear path, analog and optical; the two halves are
bypassed independently by [Direct Mode](#direct-mode) (analog) and
[SPDIF-Out Direct](#spdif-out-direct-mode) (optical only).

**[INFERRED]** (source: `src/g6_cli/g6_spec`) `toggle_to_speakers`/`toggle_to_headphones`
are genuinely different packets, each followed by a replay of feature slots
`0A`–`14`. The 5.1/7.1 variants (`speakers_to_5_1()`, `speakers_to_7_1()`, and
the headphone equivalents) are **byte-identical** to their stereo counterpart
— upstream's own comment guesses the channel count is set OS-side, not on the
device.

**Help box:** Selects the physical output the G6 drives. Channel-count
variants send identical bytes — the OS decides the channel count, not the
device.

## Virtual 7.1

The G6 has exactly **two** analog output channels, always, regardless of
"Stereo"/"5.1"/"7.1" selected anywhere in software. **[INFERRED]** (firmware
disassembly, g6-re): in 7.1 mode the host streams 8 channels to the G6 over
an ordinary USB Audio Class endpoint, and the G6's own onboard DSP (the
"Malcolm"-controlled VT1728 chip) renders that down to a binaural stereo mix
*inside the device*, using the same SBX/HRTF engine described in
[`firmware-findings.md`](firmware-findings.md#6-hrtf-mode--what-it-is-and-why-this-app-doesnt-touch-it).
Direct Mode disables this the same way it disables every other effect (see
[Direct Mode](#direct-mode)): with the register-write gate closed, an
8-channel stream gets only a fixed, non-adaptive downmix.

**Why it doesn't work on macOS:** **[INFERRED]** (firmware disassembly,
g6-re) the firmware does implement a `SetSpeakersConfig` command (vendor HID
message 90, sub 7, carrying a channel mask) — but its payload has never been
captured or decoded by anyone, and no tool in the ecosystem sends it.
**[INFERRED]** (g6-re) on Windows the channel count lives in the audio
driver's registry state (`KSAud_Device\SPeakerConfig`), a driver property
rather than a HID write. **[INFERRED]** (reasoning) macOS has no equivalent
knob at all: Core Audio derives channel count from the USB Audio Class
descriptor, and no API lets an application ask for something different.
**[TESTED 2026-09-17]** `experimental/verify-coreaudio-volume.py` against the
real G6 confirms the outcome directly: current format `48000 Hz, 24 bit,
2 channels`, **8 total formats enumerated, all 2-channel**,
`has_non_stereo_formats()` returns `False`. The macOS Audio tab's **Output
Channels** row is measured to read 2, not merely expected to.

This is a *missing mechanism everywhere on macOS*, not something Linux has
and macOS specifically withholds — distinct from the Mixer tab and
volume/mute rows, which really are hidden by the AudioControl claim gate
(`HANDOFF.md`); that gate is real but is not what stops 7.1.

**This project's own flags are not a workaround.** **[INFERRED]** (source:
`src/g6_cli/g6_spec/playback.py`):

```python
def speakers_to_7_1() -> list[UsbAudioData]:
    ...
    return speakers_to_stereo()
```

`speakers_to_7_1()`, `speakers_to_5_1()`, and the headphone equivalents all
return the byte-identical stereo packet. Whether `--playback-speakers-to-7-1`
changes anything on Linux is unconfirmed and, on the evidence of the bytes,
doubtful. A genuine channel-count switch would most likely need to happen at
the OS audio-stack level (telling ALSA/PipeWire to open the G6 as an
8-channel sink), not through this packet. See the
[Linux testing checklist](../LINUX-TESTING.md).

**Open question:** does the G6 remember a 7.1 selection made on Windows or
Linux, in a way macOS would then see (settings persist in firmware across
OSes)? Untested — see [Open questions](#open-questions).

**Help box:** Renders 8 channels to binaural stereo inside the G6's own DSP.
Not available over USB on macOS — Core Audio has no way to ask any device for
more than the channels its USB descriptor advertises, and the G6's descriptor
is 2-channel on this platform.

## Direct Mode

**Not a switch — one position of a radio group.** **[INFERRED]** (Creative,
Connect 2): each output has an **Output Mode** radio — Headphones:
`Audio Effects`/`Direct`; Speakers: `Audio Effects`/`Direct`/`SPDIF-Out
Direct`. This app models it as **two independent booleans**, so it can
represent `Direct=on, SPDIF-Out Direct=on`, a state the device can't hold
(it silently picks one; this app never finds out, since it doesn't read the
device back). The UI makes the two mutually exclusive to paper over the
worst of it, but the real fix — one three-way selector, including the
`Audio Effects` default this app's protocol capture never covered — is not
done. Creative's Setup pages also carry two settings never captured here:
**Configuration** (Stereo/5.1/7.1, both virtual) and **Apply Headphone
Virtualization to** (`Headphones` or `Line and Optical Out`).

**What it does [INFERRED, Creative]:** shuts the DSP down entirely — not
"turn effects off," powers down the block that implements them: SBX
(Surround, Crystalizer, Bass, Smart Volume, Dialog+), Scout Mode, the
playback EQ, the predefined profiles, **microphone recording** (Creative's
FAQ states this plainly — sidetone still works, which isn't proof the mic is
recording), and What-U-Hear. Stereo-only, engaged on the device by holding
**Scout Mode for 2 s** (Scout LED then blinks continuously). **The payoff:**
32-bit/384 kHz PCM plus DSD64/128 over DoP (DSD is Windows-only, unsupported
on macOS) — the CS43131 DAC is exactly a 32-bit/384 kHz part, so the limit
without Direct Mode is the DSP in front of it, not the converter.

**How much does it actually change?** Essentially nothing once effects are
already off. **[INFERRED]** (ASR measurement + forum reports by ear): "makes
no difference" once effects are off. Direct Mode is a statement about the
G6's own internals, not the whole chain — it doesn't undo anything the host
already applied (system EQ, Dolby Atmos for Headphones, a player's own DSP).

**Mechanism [INFERRED]** (firmware disassembly, g6-re): a RAM flag is checked
before every effect-parameter write in the register-write dispatcher; on,
the write is skipped entirely. Master volume lives in a separate register
block the gate doesn't touch, so it keeps working. SPDIF-Out Direct
additionally hard-switches the optical output's I²C registers to raw
passthrough. This is why every effect vanishes at once and why it's enforced
regardless of what software asks for — firmware refusing to send the data,
not a cooperative setting a program could bypass. Flag addresses across
firmware versions: [`firmware-findings.md`](firmware-findings.md#2-what-direct-mode-actually-does-inside-the-device).

**Why it does nothing on macOS:** **[INFERRED]** (Creative FAQ) Direct Mode
is set from **Audio MIDI Setup** on a Mac, not the device button, because
macOS always controls an audio device's mode via the USB Audio Class clock
selector and overwrites the device's own setting. **[TESTED 2026-09-16]**
(by ear): switching Clock Source to *Stereo Direct* stops SBX doing
anything; back to *DSP Clock* restores it. The GUI now disables this switch
on macOS with a note pointing at the [macOS Audio tab](#macos-audio-tab),
the same treatment the volume rows get.

**Help box:** Shuts down the entire DSP for a bit-perfect path; unlocks
32-bit/384 kHz and DSD. Disables SBX, Scout, the EQ, mic recording and
What-U-Hear (sidetone survives). **On macOS this switch does nothing** —
use the macOS Audio tab's Clock Source instead. With effects already off, it
is measurably identical to normal mode.

## SPDIF-Out Direct Mode

**[INFERRED]** (source: `src/g6_cli/g6_spec`) Structurally the same command
as Direct Mode with one field changed (target `0005` vs. `000d`) — same
opcode, same commit packet. **[INFERRED]** (Creative KB 128701, *G5: Direct
Mode versus SPDIF-Out Direct*): Direct Mode gives bit-perfect stereo playback
(192 kHz on the G5, 384 kHz on the G6); SPDIF-Out Direct gives bit-perfect
optical output up to 24-bit/96 kHz (S/PDIF's ceiling, not the device's); the
two are **mutually exclusive** in Creative's own UI. Behaviour, with
Windows' default playback device set to Speakers:

| Direct Mode | SPDIF-Out Direct | Headphone/Line Out | Optical Out |
|---|---|---|---|
| off | off | plays, with effects | plays, with effects |
| **on** | off | plays, no effects | **silent** |
| off | **on** | plays, with effects | plays, no effects, **volume no longer controllable** |

Three consequences: Direct Mode **kills optical output entirely**, not just
bypasses it; SPDIF-Out Direct only touches the optical output — *not*
"Direct Mode for the rear jack," the analog half keeps its effects; and it
hands volume control to the receiver (no digital scaling left to apply).
**[INFERRED]** (Creative G6 FAQ) confirms the middle/bottom rows for the G6
itself; the G5's 192 kHz becomes 384 kHz on the G6's analog side, and
"volume uncontrollable via G5" is **[INFERRED]** (extended by analogy) to
the G6 for the same bit-perfect reason, not separately confirmed. Because
the two are mutually exclusive on the device but ship as two independent UI
booleans, the app makes them mutually exclusive too, so `g6.json` can't
record a state the hardware can't hold. Creative's screenshots also show a
third advanced setting, **Headphone Surround for Line/Optical Out**, never
captured here.

**About S/PDIF bandwidth:** TOSLINK isn't limited to 256 kbit/s — consumer
S/PDIF carries ~3 Mbit/s, enough for 2-channel PCM up to 24-bit/96 kHz or a
compressed multichannel bitstream (Dolby up to 640 kbit/s, DTS up to
1.5 Mbit/s), but not uncompressed multichannel PCM — why 5.1 over optical
always means a lossy bitstream, and 2-channel PCM beats it on fidelity
because one is lossless, not because of bandwidth. **[INFERRED]** (Creative)
the G6's optical out supports up to 5.1 and decodes Dolby Digital but does
**not** encode it, so a Mac's PCM output can never become a bitstream for a
receiver.

**Help box:** The same DSP bypass as Direct Mode, applied to the optical
(S/PDIF) output only. Only relevant if something is plugged into the optical
out; mutually exclusive with Direct Mode on the device.

## Filter — five reconstruction filters, including a hidden one

**[INFERRED]** (source: `src/g6_cli/g6_spec`, opcode `6c03`) Four values are
visible in Creative's own app:

| Label | Bytes |
|---|---|
| Fast Roll Off — Minimum Phase | `0001` |
| Slow Roll Off — Minimum Phase | `0002` |
| Fast Roll Off — Linear Phase | `0004` |
| Slow Roll Off — Linear Phase | `0005` |

These are the **CS43131's built-in interpolation filters** **[INFERRED]**
(Cirrus datasheet), not a Creative invention, combining two axes: **roll-off**
(fast holds flat response to near 20 kHz then cuts hard; slow slopes earlier
and gentler, trading top-octave flatness for less ringing) and **phase**
(linear rings symmetrically — a small pre-echo before transients,
time-coherent; minimum puts ringing after the transient — no pre-echo,
frequency-dependent group delay). Default **[INFERRED]** (community): Fast
Roll Off — Minimum Phase. These "4 roll off filters" are **[INFERRED]**
(Creative FAQ) a G6-only addition — the G5 has none.

### The fifth filter — Non-Over-Sampling (NOS), hidden by Creative

**[INFERRED]** (g6-re, live testing on their own hardware, not this
project's): querying the CS43131 through Creative's SoundCore layer enumerates
**five** filter modes on a real G6, not four — the fifth is NOS, a real,
fully-supported silicon mode (Cirrus datasheet §5.9). **[INFERRED]** (g6-re,
decompiled `BaseFiltersPageViewModel.InitializeSetupDACFilter`) Creative's own
Windows app hard-skips the filter entry named `"NonOverSampling"` **by name**
when building the list — nothing about NOS is broken or firmware-gated, the
GUI code just doesn't offer it. **[INFERRED]** (g6-re + bytes) the wire
command matches this project's capture format: `5A 6C 03 00 <payload>` +
commit `5A 6C 01 01`, payload = SoundCore filter code minus 2. The four
visible filters are `0001`/`0002`/`0004`/`0005`; **NOS is payload `0003`** —
the one value never seen in upstream's own captures.

**What NOS does** on a delta-sigma DAC: bypasses the digital interpolation
filter, so output is a zero-order-hold rather than a reconstructed waveform.
**[INFERRED]** (DSP reasoning): no pre-ringing, minimum delay (the appeal);
passband droop (~−3.2 dB at 20 kHz at 44.1 kHz, worse at lower rates, better
at higher); and unfiltered images above Nyquist (inaudible directly, but
present unlike with every other filter). NOS is measurably the worst of the
five on droop and imaging, and also a legitimate listening-taste preference —
likely why Creative ships it in silicon/firmware but hides it in the app.

This app exposes NOS as a fifth option (`src/g6_gui/filters.py`) with a
warning. Because `PlaybackFilter` is an upstream-frozen enum this project's
rules forbid editing, NOS is a shim object mimicking the one attribute the
send path reads (`.value == bytes.fromhex("0003")`) rather than a real enum
member. The HID write happens correctly either way, but the separate
model-persistence step checks `isinstance(..., PlaybackFilter)` and raises on
the shim — so with model persistence on (default), selecting NOS is expected
to apply on the device, then error, revert the dropdown, and **not** save to
`g6.json`. Only `--no-persist` avoids this. Whether the device-side write
survives that error path is untested — see [Open questions](#open-questions).

### Picking one, practically

It doesn't matter for a DT 990 PRO, DT 880, or DT 770 — the entire
difference lives above ~18 kHz and in impulse ringing tens of dB below
signal, while the headphones differ by 10+ dB through the treble. If a rule
helps: **Slow Roll Off — Minimum Phase** has no pre-ringing and the gentlest
top end; **Fast Roll Off — Linear Phase** is the measurement-correct,
flattest-to-20kHz choice; stock **Fast Roll Off — Minimum Phase** is fine if
you'd rather not think about it. A bigger lever is the G6's **gain switch**
(physical, not software): the DT 990 PRO, DT 880 (250 Ω) and any 600 Ω
variant want high gain, the 80 Ω DT 770 doesn't. **[INFERRED]** (ASR
measurement + Creative): 85 mW into 300 Ω on high gain, ~1 Ω output
impedance — all three comfortably driven.

**Help box:** Picks the DAC's reconstruction filter. Differences among the
first four are confined to above ~18 kHz and impulse ringing — inaudible on
essentially any headphone. Slow Roll Off/Minimum Phase rings least; Fast Roll
Off/Linear Phase measures flattest. Non-Over-Sampling is a fifth filter the
device supports but Creative's app hides — offered here, with a warning.

## Decoder mode — Full / Normal / Night

This is **Dolby Digital Dynamic Range Control**, which is why changing it is
usually silent. **[INFERRED]** (Creative specs/Connect 2) the G6 decodes
Dolby Digital via Optical In; the knob sweeps Full → Normal → Night.
**[INFERRED]** (bytes) the three values are float32 `0000803F`/`00000040`/
`00004040` = 1.0/2.0/3.0, the knob's three detents in order.

- **Full** — no compression, mastered dynamic range.
- **Normal** — moderate compression, standard listening.
- **Night** — heavy compression: quiet dialogue up, loud peaks down.

**Why it does nothing on macOS (or Windows over USB):** DRC is a parameter of
the Dolby decoder itself, active only while actually decoding a Dolby Digital
bitstream arriving on the **optical input**. macOS sends the G6 plain PCM
over USB — no decoder in the path, nothing for the setting to modify. Not
broken, not macOS-specific. **[INFERRED]** (Creative): to exercise it, feed a
Dolby Digital source to the optical input — e.g. a PS4 (USB to the G6 for
chat, optical from the console for game audio, console output set to
digital/optical) or an Xbox. A Mac cannot produce a Dolby Digital bitstream
over USB, so no USB-only setup ever exercises this.

**Help box:** Dynamic-range compression for the built-in Dolby Digital
decoder. Full = untouched, Night = quiet parts raised and loud parts tamed.
Only has any effect while decoding a Dolby Digital bitstream from the optical
input — does nothing for PCM over USB.

## Audio interface — Mute, Volume, Channels

**[INFERRED]** (bytes) Standard USB Audio Class controls; volume is a signed
16-bit value in 1/256 dB units (100% = 0x0000/0 dB, 50% = −10.3 dB, 0% =
−64 dB), hence the coarse 10% steps and the log-feeling scale. **Hidden on
macOS**: these live on the AudioControl interface, which macOS's kernel audio
driver owns and will not release (see [`gui.md`](gui.md)).

---

# macOS: Audio MIDI Setup is the real control

**[INFERRED]** (Creative FAQ): on a Mac you change the DSP/Direct setting
from **Audio MIDI Setup**, not the device's button, because macOS always
controls an audio device's mode and overwrites the device's own setting. The
G6 is plug-and-play on macOS via Apple's stock USB audio driver — Creative
ships no Mac software at all.

## Clock Source — DSP Clock vs. Stereo Direct

Core Audio's "Clock Source" is normally about timing in a multi-device rig;
Creative overloads it as two internal signal paths:

| Clock Source | Path | Rates **[TESTED 2026-09-16]** | Effects |
|---|---|---|---|
| **DSP Clock** | Through the DSP | up to 32-bit/**48 kHz** | SBX, Scout, EQ all available |
| **Stereo Direct** | Straight to DAC | up to 32-bit/**384 kHz** | none — this *is* Direct Mode |

**`Stereo Direct` is how you turn Direct Mode on under macOS** — not this
app's switch, not the device's button. **[INFERRED]** (community reports on
the Sound Blaster E5 and a later Creative DAC) the same naming and the same
48 kHz DSP-mode ceiling on macOS appear on sibling Creative devices.

**Gotcha, TESTED on this Mac:** with the format at 32-bit/384 kHz under
Stereo Direct, switching back to DSP Clock breaks audio — DSP Clock can't do
384 kHz and Core Audio won't renegotiate for you. Recovery: switch back to
Stereo Direct → set the format to something DSP Clock supports (2 ch/24-bit/
48 kHz) → *then* switch to DSP Clock. **Drop the sample rate before changing
clock source, not after.**

## macOS Audio tab

The **macOS Audio** tab (first tab in the GUI, since this is the actual
Direct Mode control here) reads and writes Clock Source and Format through
the same public Core Audio API Audio MIDI Setup itself uses
(`AudioObjectGetPropertyData`/`SetPropertyData` on
`kAudioDevicePropertyClockSource`/`kAudioStreamPropertyPhysicalFormat`), and
automates the switch-back handoff above so this app cannot wedge the device.
**[INFERRED]** (read from this machine's Xcode SDK headers, not memory) —
`kAudioObjectPropertyName` is `'lnam'`, not the `'name'` a guess would
produce. It identifies the G6 **not by name** but by scanning for the one
device whose Clock Source options are exactly `{"DSP Clock", "Stereo
Direct"}` — the one fact Creative's docs confirm for certain about this
device; anything else greys the tab out with an explanation rather than
guessing. Switching **to DSP Clock** above 48 kHz auto-drops the format to
48 kHz (preferring 24-bit) before touching the clock source, reproducing the
manual recovery above in code. **[TESTED 2026-09-16]** (BlackHole and the
built-in devices, **not** the G6): picking the wrong fallback (lowest rate, not 48 kHz
specifically) was an actual bug caught validating this against real Core
Audio, before real G6 hardware was available.

### Confirmed against the real G6

**[TESTED 2026-09-16]** Core Audio calls the device exactly `Sound BlasterX
G6`; fingerprint identification (built to not depend on that name) found it
anyway, with clock sources spelled precisely `"DSP Clock"`/`"Stereo Direct"`.
The full flow works end to end — detects the device, reads real Clock
Source/Format, switches between the two, disables Recording/SBX the moment
Stereo Direct is confirmed, and picks up changes made in Apple's own Audio
MIDI Setup via Refresh. DSP Clock's format list is capped at 48 kHz
(8 entries); Stereo Direct offers 32, up to 384 kHz. **[TESTED 2026-09-17]**,
precisely, via `experimental/verify-coreaudio-volume.py`: on DSP Clock, 44.1
and 48 kHz × 24/32-bit × ordinary/`(Exclusive)` = 8 entries, all 2-channel
(this run didn't re-switch to Stereo Direct, so the 32-entry figure is from
2026-09-16 and expected to still hold).

**A real discovery, TESTED 2026-09-16:** the format list wasn't just large —
every (rate, bit depth) combination appeared twice. Read as raw
`AudioStreamBasicDescription` structs, they're genuinely different: one
ordinary, one with `kAudioFormatFlagIsNonMixable` set (Core Audio exclusive
mode, locking the device to one application) — also a bug in this app's tab,
whose `Format` type compared (rate, bits, channels) only, so picking the
second silently resolved to the first. Fixed by tracking the flag; the
exclusive variant is labelled `(Exclusive)` and independently selectable.

**Settle timing, TESTED 2026-09-16 — real hardware behaviour, not a bug:**
`current_clock_source` flips within ~20 ms of a switch; the separate
available-format-list property lags 100–200 ms — the tab now waits for the
format list to change before finishing a switch. Separately, most switches
settle under 300 ms, but the identical operation twice took over a second
with no identifiable pattern — unexplained, still open (see [Open
questions](#open-questions)); the settle-poll budget is generous (several
seconds) because of it, at no UI cost since the wait never blocks the main
thread.

**Cross-tab effect:** Recording and SBX auto-disable whenever this tab
confirms Stereo Direct (both drive the DSP over HID, which Stereo Direct
bypasses), stay enabled on DSP Clock, and — deliberately — stay enabled when
the clock source can't be positively identified, since ambiguous shouldn't
count as evidence of Stereo Direct (`_apply_clock_source_gate` in `app.py`,
`coreaudio.py`). The 48 kHz DSP-path cap matters: Creative's non-Direct
marketing figure is 96 kHz, but on macOS the DSP path tops out at 48 kHz —
above that you give up every effect, no middle setting.

**What Clock Source does *not* cover:** Creative's Output Mode is three-way
(`Audio Effects`/`Direct`/`SPDIF-Out Direct`); macOS's is two-way, mapping to
the first two. **There is no macOS equivalent of SPDIF-Out Direct**, so
"macOS overrides Direct Mode" doesn't extend to it — macOS may have no
opinion and let this app's HID packet through, untested. That's why the GUI
disables Direct Mode on macOS but leaves **SPDIF-Out Direct enabled**:
untested isn't broken, and disabling it would remove the only way to find
out (needs something plugged into the optical output).

## Format — bit depth and sample rate

Higher is not better here: 24-bit/48 kHz matches the overwhelming majority of
source material, 384 kHz is not audibly different on a DT 990
**[TESTED 2026-09-16]** (by ear), and ASR could not *measure* a difference between
Direct Mode and normal mode with effects off **[INFERRED]** (ASR). 24-bit
already covers ~144 dB of dynamic range, beyond both the G6's 130 dB DAC and
any listening room — more bit depth buys nothing audible. The genuine reasons
to pick Stereo Direct are DSD (unsupported on macOS at all) and hi-res files
you actually own; otherwise DSP Clock at 24-bit/48 kHz with effects on is the
better trade on a Mac.

## Full-scale volume — the G6 distorts at 100%

The macOS Audio tab shows the G6's current output volume and warns at 100%.

**[INFERRED]** (Audio Science Review, 2019 bench measurement): real,
measurable low-frequency distortion at full digital scale — THD+N approaching
1% at 20 Hz at 0 dBFS — that dropping the level by exactly 2 dB removed
entirely, taking SINAD from ~107 dB to ~112 dB. ASR's diagnosis was analog:
the G6 is bus-powered over USB and likely short of supply headroom driving
the DAC at full-scale low-frequency peaks. **[INFERRED]** (firmware
disassembly, g6-re): every DSP/DAC gain and drive constant — master-gain
ladder, headphone gain-patch tables, profile gain tables, boot parameters —
is **byte-identical across all five public firmware releases, 2019–2025**;
no headroom-trim constant was added in six years. Full comparison:
[`firmware-findings.md`](firmware-findings.md#1-the-full-scale-distortion-issue--real-old-and-permanent).

**What this means:** the distortion at 100% is a permanent hardware property
of every G6 on every firmware version — an analog power-supply headroom
limit firmware can't fix, and won't be patched. **The fix, unchanged since
2019:** keep the volume a couple of steps below 100% (~90% is comfortably
clear) before the signal reaches the DAC. This app can't change your system
volume, but shows the current level and warns at 100%. **Unverified:**
nobody has run a THD+N measurement against this project's own G6, or any G6
on macOS specifically — the reasoning rests on the constants being
unchanged, not a fresh measurement.

### Volume forwards to the device, not the host

**[TESTED 2026-09-17]**, via `experimental/verify-coreaudio-volume.py`: the
macOS volume slider for the G6 moves a real hardware volume control inside
the device, not a host-side software gain:

```
'vmvc' (VirtualMainVolume)              not implemented
'volm' output/main                      not implemented
'volm' output/ch1                       0.5625
'volm' output/ch2                       0.5625
'vold' output/main                      not implemented
'mute' output/main                      0.0000
```

Core Audio's `'volm'`/`'mute'` are a passthrough to the G6's own USB Audio
Class descriptor, which advertises a hardware volume control on the output
terminal — the same control Windows' volume mixer and Connect 2 would move.
**Closed.** **A portability gotcha:** the G6 implements volume **only per
output channel** (elements 1/2 above), never on the master/main element, and
doesn't implement `'vmvc'` at all — code that only checks the main element
or `'vmvc'` will wrongly conclude the G6 has no volume control. This app's
`coreaudio.py` already reads/writes per-channel for this reason; the
measurement confirms that was correct against real hardware, not just
BlackHole. Whether a per-channel `'vold'` also exists wasn't probed —
**[unknown]**.

**Still open: where inside the G6 does attenuation happen** — digitally
before the CS43131 DAC, or in the analog stage after it (the Xamp, or an
attenuator ahead of it)? This decides whether lowering volume genuinely
reduces what the DAC/analog stage handle (consistent with ASR's −2 dB
finding) or only reduces something after an already full-scale DAC output
(less consistent). **[INFERRED]** (reasoning, not measured): the practical
advice — a couple of steps below 100% — holds either way, since it matches
ASR's supply-sag diagnosis regardless of where in the chain the reduction
happens; reasoning from the outcome, not a measurement of the signal path.
What would settle it: `docs/g6-re/tools/thd_test.py`, a THD+N script g6-re
prepared but deliberately never ran, at multiple volume settings with a
loopback cable — nobody has run it on any G6.

**What this means for the app on macOS:** Direct Mode's switch does nothing
(disabled with a note); everything else on the HID interface works — output
switching, filter, decoder, lighting, mic boost, CrystalVoice, all of SBX —
**[TESTED 2026-09-16]**, despite Creative's FAQ claiming no Acoustic Engine
customization on Mac (true of *their* software, not the device); selecting
Stereo Direct correctly kills SBX's audible effect and mic recording —
device behaviour, not app failure.

**Help box:** On macOS, Direct Mode is selected in Audio MIDI Setup → Clock
Source, not here. *DSP Clock* keeps all effects and caps at 48 kHz; *Stereo
Direct* is Direct Mode — bit-perfect to 384 kHz, no effects, no mic recording.

---

# Hardware facts worth having

**[INFERRED]** (Creative technical specifications, SID 200065):

| | |
|---|---|
| Model / DSP | SB1770 / SB-Axx1 audio processor |
| DAC | Cirrus Logic CS43131, 130 dB SNR/DNR |
| Headphone amp | Xamp Discrete HP Bi-Amp, 1 Ω output impedance |
| Headphones supported | 16 – 600 Ω |
| Dolby Digital decoding | Yes — via Optical In |
| DSD over PCM | DSD64, DSD128 — Direct Mode only, not on macOS |
| Playback (Direct Mode) | 16/24/32-bit at 44.1/48/88.2/96/176.4/192/352.8/384 kHz |
| Recording | up to 32-bit/192 kHz, Line In/Optical In/Mic In alike |
| Jacks | Line In+optical In combo · Line Out+optical Out combo · Headphone/Headset · Ext Mic In · USB |
| macOS driver | Apple's in-box driver — Creative ships none |

All three of your Beyerdynamics (DT 990 PRO, DT 880, DT 770) sit comfortably
inside 16–600 Ω. Note the two *separate* front jacks: Headphone/Headset and
Ext Mic In.

**[INFERRED]** (Creative KB 200066) On Windows, reaching 32-bit/384 kHz uses
the same idea as macOS through a different dialog: set speaker configuration
to Stereo, then pick *32 bit, 384000 Hz (Studio Quality)* in the playback
device's format properties — no Direct Mode switch involved. On both OSes,
the high-rate stereo path is entered by choosing the format in the OS.

# The physical controls

Not software, but the only status this app gives you at all, since it
doesn't read the device back. **[INFERRED]** (Creative):

| Action | Control | Result |
|---|---|---|
| Toggle Scout Mode | Press Scout Mode button | Scout Mode on/off |
| Toggle Direct Mode | Hold Scout Mode 2 s | Scout LED blinks continuously (ignored on macOS) |
| Toggle Sidetone | Hold volume knob 2 s | Knob LED white→red, icon headphone→mic; blinking white = muted |
| Gain | Physical switch | High gain for 250 Ω+ headphones |
| **Factory reset** | Hold Scout Mode + volume knob 5 s | 3 side LEDs cycle; **erases every saved setting** |
| Soft reset | Unplug USB, wait 3 s, replug | Recovers an unresponsive card |

**Factory reset is the most useful entry on this list**: it's the only way to
force a known state that `g6.json`'s assumed defaults can agree with, since
this app can drift out of sync with the hardware with no way to compare (the
protocol does support a register readback, this app just doesn't use it —
see [below](#control-protocol-and-readback)). It also wipes lighting and
everything else.

---

# SBX

## Profiles — Gaming / Music / Cinema / Special

**[INFERRED]** (source: `src/g6_cli/g6_spec`) `sbx_toggle()`/`sbx_slider()`
build packets from the feature and value only — `profile_name` never reaches
the wire. **The G6 has exactly one live SBX state.** The four profiles also
ship empty (`Profile.init()` calls `SBX.default()` for all four: every
effect off, every slider at 50, no Smart Volume special) — no factory
Gaming/Cinema voicing is captured anywhere in this codebase. **[INFERRED]**
(Creative FAQ): BlasterX Acoustic Engine and SBX Pro Studio share core
algorithms; the Acoustic Engine's addition is preset/customisable profiles,
including game-tuned ones — Connect 2 ships 20 (Gaming, Music, Movie,
Adventure and Action, FPS, RPG, RTS, Driving Simulation, Stadium, and 11
title-specific ones). None of that content exists here; this project's four
names (Gaming/Music/Cinema/Special) are a local abstraction borrowing three
of Creative's names — Creative has *Movie*, not *Cinema*, and nothing called
*Special*.

So a "profile" is really just a **named row in `g6.json` recording what you
last set**: editing a non-active profile is audible immediately (bytes go to
the single live SBX state), the edit saves under the profile you were
editing, and `sbx_profile_switch()` — the only bulk replay in the codebase —
walks the target profile's saved values and resends them all, overwriting
your other edits. The SBX tab warns about this.

### Bug: changing "Editing profile" already switches the profile

**[INFERRED]** (bytes, reproduced without touching real hardware via the fake
API): picking a different profile in the **Editing profile** dropdown is
supposed to just repoint the controls at another slot, sending nothing. It
doesn't. `on_editing_change` repopulates every control by assigning
`.value`, and on the Cocoa/Toga backend, assigning `.value` **fires
`on_change`** whenever the new value differs from the old
(`toga_cocoa/widgets/switch.py`) — so each control that actually changed
submits to the device. Reproduced with the fake API: making Cinema differ
from Gaming in four values, then selecting Cinema in the dropdown, produces
four device writes from an action that should send nothing.

**Consequences:** the sound changes the moment you browse profiles, so
"Switch to this profile" *appears* to do nothing — but it's not fully
redundant, since it still records the newly selected profile in `g6.json`
and updates the banner (bookkeeping catching up with audio that already
moved). The SBX tab's implied safety property — "editing another profile is
audible but doesn't switch you" — is therefore false; merely browsing
profiles rewrites the live SBX state. Missed by tests because the default
fake-API model has all four profiles identical, so the `value != old_value`
guard never fires; a regression test needs profiles that actually differ.
**Fix sketch, not applied:** a reentrancy flag on `on_editing_change`,
matching the guard already used in `slider_row`'s snap handler.

**Help box:** Profiles are slots in this app's own file, not presets on the
device. The G6 has one live SBX state, so editing any profile is heard
immediately; switching profiles replays that slot's saved values over it.

## How Creative's own UI presents these five

**[INFERRED]** (Creative, Connect 2) this GUI presents all five identically
(on/off + 0–100 slider); Connect 2 does not — it folds "off" into the bottom
of three knobs instead of a separate switch. **[INFERRED]** (bytes) the
protocol has both a toggle slot and a slider slot for all five, so this app
isn't inventing controls. To roughly match Creative's detents: 0/50/100 for
Surround, 0/33/66/100 for Dialog+ (whether the firmware interpolates or
snaps to the nearest detent is **[unknown]**):

| Effect | Creative's control | What it does **[INFERRED, Creative unless noted]** | Help box |
|---|---|---|---|
| **Surround** | Normal·Wide·Ultra Wide (no separate on/off) | HRTF-based virtual surround over two channels. **[INFERRED]** (community): good for positional cues in games with a real surround source, less useful on stereo music. | Widens the stage and places sounds around you from a multichannel source. Effective for games, less so for stereo music. |
| **Crystalizer** | 0–100 + on/off | An expander with a treble tilt restoring detail lost to lossy compression; adds bite to films/games/streams. Easy to overdo on a bright headphone like the DT 990 PRO. | Re-expands dynamics and sharpens transients to counter compression artefacts. Audible immediately; go easy on bright headphones. |
| **Bass** | 0–100 + on/off | Fuller, deeper low end via added harmonics, not just level. | Bass enhancement — adds depth and harmonic weight to the low end. |
| **Dialog Plus** | Off·Normal·Balanced·Dialog Focus (no separate on/off) | Analyses centre-channel/dialogue content and lifts the vocal band via filtering and a frequency/time-domain algorithm, so speech sits above the mix and room noise. | Lifts voices and dialogue above the rest of the mix. Useful for films with buried dialogue. |

**Smart Volume (+ special)** — loudness levelling: continuous gain/attenuation
so quiet/loud passages and different tracks arrive at consistent volume. The
slider and the "special" mode are mutually exclusive by construction:
**[INFERRED]** (bytes) `sbx_profile_switch()` sends the slider (feature `05`)
only if `smart_volume_special is None`, otherwise the special mode (feature
`06`) and never the slider:

| Special | Bytes | As float32 | Connect 2 calls it |
|---|---|---|---|
| Loud | `0000803F` | 1.0 | **Auto** |
| Night | `00000040` | 2.0 | Night |

**Naming warning [INFERRED]:** this app's "Loud" label is probably wrong —
Connect 2's knob reads Off/Auto/Night, so 1.0 is ordinary automatic levelling
("Auto"), not "make it louder"; same byte, misleading label, unconfirmed (see
[Open questions](#open-questions)). **[INFERRED]** (Creative): Night mode
adds a gentle equal-loudness EQ curve so bass/treble don't vanish at low
volume. A special mode means a fixed levelling curve and an inert slider;
`None` means a variable-strength leveller.

**Help box (Smart Volume):** Evens out volume differences between quiet and
loud passages. A special mode (Night or Loud) replaces the slider entirely —
Night adds equal-loudness compensation for low-volume listening.

---

# Recording (CrystalVoice)

Everything here processes the **microphone**, not what you hear.

## What actually works — listening tests

**[TESTED 2026-09-16]** on a ModMic V2 (condenser) through the G6 on macOS:

| Control | Result |
|---|---|
| Mic Boost | Works — immediate, obvious loudness increase |
| Noise Reduction (toggle) | Works — audibly drops the noise floor even at level 0 |
| Noise Reduction Level | Works — at 100 the suppression starts eating the voice; mid-range is the better trade |
| Acoustic Echo Cancellation | Works — removes echo, costs some clarity; sensible on for calls, off for recording |
| Mic Equalizer + presets | Works — on/off is clear and the presets genuinely differ |
| **Smart Volume** | **No audible effect** |

**Nothing here removes keyboard/mouse clicks** — confirmed no combination
suppresses key or mouse noise. Expected, not a failing: Noise Reduction is a
*steady-state* suppressor (estimates a constant noise profile and subtracts
it); keyboard/mouse noise is short, loud, broadband transients that look
like speech onsets to that algorithm. Removing them needs a transient
suppressor or gate, on the computer, not this device.

**Recording Smart Volume did nothing** — the one control here with no
observed effect while everything else behaved as documented, an unlikely
candidate for user error. Unconfirmed explanations: its threshold may need a
bigger mic-distance change than normal speech produces; it may be inactive
over USB on macOS, like Direct Mode; or it may need another CrystalVoice
block active first. **[INFERRED]** (bytes): the packet is unremarkable —
feature `2C`, the same enable/commit shape as NR (`04`) and AEC (`00`), both
of which demonstrably work — unlikely to be malformed. Open question, not a
bug (see [Open questions](#open-questions)).

**[TESTED 2026-09-16]** the "Dynamic Mic 1" preset **distorts** on the
ModMic V2 — correct behaviour applied to the wrong mic type: the ModMic is a
condenser, and Dynamic Mic 1 exists to add 8–12 dB for a dynamic mic's much
lower output (the G6 supplies no phantom power **[INFERRED, Creative]** and
takes a 3.5 mm 3-pole mono mic). Preset 6 is the most noticeable numbered
preset — its aggressive presence lift reads as a slight echo, which AEC
then partly removes, so the two audibly interact.

## Noise Reduction, AEC, Smart Volume (recording)

| Control | What it does **[INFERRED, Creative unless noted]** | Feature slot **[INFERRED, bytes]** | Help box |
|---|---|---|---|
| **Noise Reduction** (+Level) | Identifies steady background noise (fans, AC, hum) and suppresses it | toggle `04`, level `05` | Suppresses steady background noise on the mic. Level steps in 20% increments; the maximum sends half the device's full-scale parameter. |
| **Acoustic Echo Cancellation** | Removes echo from speaker output picked up by the mic — a call-quality, not sound-quality, feature. Useful on **speakers**; near-pointless on **headphones** (no acoustic path) — a noticeable effect there is expected anyway, since AEC also runs an adaptive filter that can colour the voice with nothing to cancel | `00` | Cancels your speakers' sound being picked up by the mic during calls. Only meaningful when using speakers. |
| **Smart Volume** (recording) | Automatically levels your own voice to constant loudness for the other party regardless of mic distance — the mic-side twin of playback Smart Volume. Useful for calls/streaming, undesirable for anything you plan to edit (destroys original dynamics). No audible effect observed — see [listening tests](#what-actually-works--listening-tests) | `2C` | Keeps your voice at a consistent level regardless of how close you are to the mic. Great for calls, bad for recordings you intend to edit. |

**[INFERRED]** (bytes): Noise Reduction's level scale is not linear 0–1 —
0/20/40/60/80/100 on the slider send float32 0.0/0.1/0.2/0.3/0.4/**0.5**.
The slider's 100% sends 0.5, not 1.0, in steps of 20 only: either Creative
deliberately caps the UI at the middle of the underlying range, or the upper
half was never captured — either way, "100" isn't "as much as the device
can do."

## Mic Equalizer + presets

**[INFERRED]** (bytes): 8 float32 gains in dB, feature slots `14`–`1B`, low
band to high:

| Preset | B1 | B2 | B3 | B4 | B5 | B6 | B7 | B8 | Shape |
|---|---|---|---|---|---|---|---|---|---|
| 1 | −3 | −4 | 0 | *(0)* | +3 | −3 | +4 | +5 | Cut lows, scoop mids, lift presence |
| 2 | −3 | −4 | 0 | *(0)* | +4 | −2 | +2 | +4 | As 1, gentler top |
| 3 | −2 | −3 | +3 | +4 | +4 | −4 | +3 | +2 | Forward mids, notch, mild air |
| 4 | −3 | −5 | 0 | +4 | 0 | −3 | 0 | 0 | Clean-up only |
| 5 | −2 | −3 | +2 | +4 | +4 | 0 | −3 | +2 | Warm, mid-forward, tamed presence |
| 6 | −5 | −4 | −2 | 0 | +3 | +4 | +6 | +7 | Aggressive bright/telephone tilt |
| 7 | 0 | +3 | −2 | −4 | −4 | −2 | +5 | +7 | Smile curve: body + air, scooped mids |
| 8 | 0 | 0 | +2 | +2 | +3 | −4 | +2 | +4 | Mild all-round lift |
| 9 | 0 | 0 | +2 | +2 | −2 | 0 | −4 | +4 | Softens presence, keeps air |
| 10 | 0 | +2 | −2 | 0 | +3 | +5 | +6 | +5 | Bright, intelligibility-focused |
| Dynamic Mic 1 | 0 | +8 | 0 | +12 | +12 | +4 | +8 | +10 | Huge broadband lift |

Presets are unnamed in Creative's software too — voicings, not scenarios. The
pattern is a classic broadcast-mic toolkit: cut low rumble/proximity mud
(bands 1–2), lift presence/air (7–8) for intelligibility. Band ordering
(low→high) is **[INFERRED]** from slot order and the consistent shape, not
documented. **Dynamic Mic 1** is the one with a real name (`PRESET_DM_` in
source): dynamic mics (SM58, Procaster) run quieter and darker than an
electret headset mic, and +8–12 dB broadband matches that — **don't use it
with a headset mic**, it will be loud and harsh.

Practical picks: **4** for cleanup with minimal colour; **6 or 10** for
maximum call intelligibility; **7** for a fuller "radio" voice; **Dynamic
Mic 1** only with an actual dynamic mic.

**A bug, [INFERRED] from the bytes alone** (source:
`src/g6_cli/g6_spec/recording.py`) — already certain, just never hand-verified
by ear: band 4 of Presets 1 and 2 is written as `0000 4000`, breaking the
`0000 XX40`/`XXC0` pattern every other entry follows; it decodes to a denormal
float (~0) rather than the evident intent of `0000 0040` (+2 dB) — a
byte-swap. Band 4 comes out flat instead of +2 dB on those two presets. Worth
reporting upstream.

**Help box:** An 8-band EQ on the mic path. Presets are voicings, not
scenarios — most cut low rumble and lift presence. "Dynamic Mic 1" adds
8–12 dB and is only for an actual dynamic microphone, not a headset.

## Mic Boost, Recording Volume, Monitoring

**[INFERRED]** (bytes) — three different things that all look like "volume":

- **Mic Boost** — analog preamp gain, plain integer dB: 0/10/20/30. Raises
  noise floor too; use the least that gets a healthy level.
- **Recording Volume** — level sent to the computer, signed 16-bit/1/256 dB:
  0% = −48 dB, 100% = **+9 dB** — the top of the slider is amplification, not
  just "no attenuation."
- **Monitoring Volume** — sidetone, how loud *you* hear yourself. Same dB
  table as playback volume (0% = −64 dB, 100% = 0 dB). **[INFERRED]**
  (Creative): on the *hardware* control, sidetone volume is **synced with
  mic recording volume** — turning the knob in sidetone mode also changes how
  loud you are to everyone else. Whether this app's two controls (HID
  monitoring vs. UAC recording volume) stay independent is **[unknown]** —
  test before trusting the sidetone slider as monitor-only.

**[INFERRED]** (Creative): sidetone is off by default and toggled **on the
device**, not in software — hold the volume knob 2 s; the knob LED goes
white→red and the side icon switches headphone→mic; a blinking white LED
means sidetone is muted.

**Help box:** Mic Boost is analog preamp gain (0–30 dB, boosts noise too).
Recording Volume is the level sent to the computer (−48 dB to +9 dB).
Monitoring is sidetone — how loudly you hear yourself, heard by nobody else.

---

# Mixer, Lighting, System

**Mixer** — per-source mute/volume for Line In, External Mic, S/PDIF In and
What U Hear, split into recording and monitoring level. All USB Audio Class
controls, so the **whole tab is hidden on macOS**.

**Lighting** — on/off plus 24-bit RGB. **[INFERRED]** (bytes): cosmetic only;
enabling takes three packets (`3A02`/`3A06`/`3A09`), colour is plain 0–255
per channel.

**System** — version info and the model file path. On Linux, the
audio-interface claim switch releases the kernel driver so volume controls
work; macOS forbids that, which is why the volume rows are absent there.

The System tab's device-info row is labelled a **USB device revision**
(`bcdDevice` — a USB descriptor field cached by hidapi/pyusb, a passive read
that writes nothing), and is explicitly *not* a firmware-version readback.
**[INFERRED]** (bytes/protocol): the G6's control protocol has no documented,
wire-verified way to return a firmware version string like
`2.1.250903.1324` — a different request (the `0xE0` GET group) from the
decoded DSP-register readback described [below](#control-protocol-and-readback),
which this app doesn't use either way. `help_text.SYSTEM_DEVICE_INFO` in
`src/g6_gui/help.py` states this accurately.

**[TESTED 2026-09-17]** `experimental/probe-g6-hid.py` swept every
sub-command of the `5A E0` GET group against the real G6; all nine returned a
byte-identical response (`5a 02 0a e0 81 ...`) — no firmware version came
back. The "USB device revision" label is the honest one to show, not a
placeholder for an easy fix. Frame-format analysis: [`hid-probe-findings.md`](hid-probe-findings.md).

---

# Control protocol and readback

Every "no readback" statement elsewhere in this document is about this app's
own behaviour, not a limit of the G6 itself:

- **[INFERRED]** (real captured USB traffic in this repo's `payloads/raw/*.pcapng`,
  recorded by upstream and decoded by this project 2026-09-17, not reproduced
  live by us): the G6's HID protocol has a real, decoded read path — a
  `WRITE` (`12 07`), a `READ REQUEST` (`11 03`), and a `READ RESPONSE`
  (`11 08`) carrying the value back. Full grammar and captured proof:
  [`device-state.md`](device-state.md#the-control-protocol-and-why-readback-is-real-but-unused).
  **[INFERRED]** (reasoning from the 31 captured ACKs, all status `0x00`, none
  a failure): status `0x81` most likely signals rejection, by contrast, not
  by direct confirmation of a failure case.
- This app doesn't use that read path today. `src/g6_cli` already sends a
  read request after most writes — misleadingly named
  `DataFragmentMode.COMMIT` — receives the real value back, and discards it.
- A related but separate question — a firmware-version string over this
  protocol — **was** tested directly against real hardware and refused (see
  the System tab section above, and [`hid-probe-findings.md`](hid-probe-findings.md)).

---

# What this app does *not* expose

Never captured in the upstream protocol work — not bugs:

| Feature | Detail **[INFERRED, Creative]** |
|---|---|
| Scout Mode | Button or Connect 2 hotkey; temporarily disables SBX and the EQ |
| Playback equalizer | 10 bands, 31 Hz–16 kHz, plus Bass/Treble, with genre presets |
| Output Mode / Configuration | The 3-way `Audio Effects·Direct·SPDIF-Out Direct` radio, and Stereo/5.1/7.1 — this app has only two loose booleans |
| Headphone virtualization target | `Headphones` or `Line and Optical Out` |
| Speaker type | Desktop/Bookshelf/Tower/Custom, crossover 10 Hz–1000 Hz |
| Voice Morph | Real-time voice alteration |
| Lighting modes | Only *Solo* here; Connect 2 adds Pulsate, Music Reactive, Cycle (speed 10–250) |
| LED indicator off | Firmware-dependent switch, off entirely |
| Firmware update | Windows-only, via Connect 2 |
| 20 BlasterX Experience profiles | See [Profiles](#profiles--gaming--music--cinema--special) |
| Gain switch | Physical, set for your headphone impedance |
| Sample-rate selection | Done by the OS, not the device |

Connect 2 itself is Windows-only (7/8/10) and won't run without the G6
attached — there's never been a Mac equivalent, the gap this project fills.

---

# How this maps onto the UI

Every control carries an **ⓘ** button that expands a plain-text summary of
its section here (`✕` collapses it); the wording lives in `src/g6_gui/help.py`,
kept in sync with this document by hand. The button stays clickable even when
its control is disabled, which is exactly when the explanation is most
wanted. Current UI decisions driven by this research, not repeated
elsewhere in this document: Direct Mode is disabled on macOS with an **Open
Audio MIDI Setup** button; SPDIF-Out Direct and Direct Mode are mutually
exclusive in the UI (mirroring the device); Smart Volume special sits
directly under the Smart Volume slider it overrides; and help text uses the
system label colour rather than a fixed grey, which was close to unreadable
in macOS dark mode.

---

# Open questions

| # | Question | What's known, and the test that would settle it |
|---|---|---|
| 1 | Why does recording Smart Volume do nothing? | See [listening tests](#what-actually-works--listening-tests). Test: try it on Windows with Creative's software — inert there points at the device/mic, working there points at this app or macOS. |
| 2 | Are sidetone and mic recording volume linked in software too? | Creative documents the *hardware* control as sharing level with recording volume; this app exposes two independent controls. Test: monitoring 100%/recording 10%, have someone confirm your level, repeat at monitoring 0%. |
| 3 | Why does a clock-source switch occasionally take over a second? | Confirmed real and reproducible (2026-09-16), cause unidentified — most switches settle under 300 ms, two took over a second with nothing else different. Candidates: USB transaction queuing, macOS re-enumeration. Test: log timing across many consecutive switches. |
| 4 | Are the SBX sliders continuous, or quantised to Creative's detents? | Connect 2 gives Surround 3 positions and Dialog+ 4; the wire format is a float 0.0–1.0. Test: sweep Surround slowly and listen for steps. |
| 5 | Is "Loud" really "Auto"? | See [Smart Volume](#how-creatives-own-ui-presents-these-five) — almost certainly the same mode as Connect 2's "Auto." Worth confirming before renaming the UI label. |
| 6 | Decoder mode with a real Dolby source | Needs a Dolby bitstream on optical in (PS4/Xbox set to bitstream output); Full vs. Night should then be obvious on a wide-dynamics film. |
| 7 | Does SPDIF-Out Direct work on macOS, and does the G5 behaviour table hold on a G6? | Direct Mode provably doesn't work on macOS, but that doesn't transfer (no Clock Source equivalent). The no-effects rule is confirmed for the G6; "optical goes silent"/"volume uncontrollable" aren't. Needs something plugged into the optical output. |
| 8 | Confirm the band-4 preset bug by ear | Already certain from the bytes (see [Mic Equalizer](#mic-equalizer--presets)); an audible/measured confirmation would let it be reported upstream with corroborating evidence. |
| 9 | What does a factory reset actually restore? | The only way to make the device and `g6.json`'s assumed defaults agree. Worth doing once deliberately — costs lighting and every saved setting. |
| 10 | What is the 2025 firmware's new capability bit for? | **[INFERRED]** (g6-re): the Direct Mode enable ACK byte changed `0x81`→`0x83` between 2019 and 2025 firmware, no corresponding feature identified anywhere. |
| 11 | Does NOS actually apply on real hardware, given the persistence bug? | See [NOS](#the-fifth-filter--non-over-sampling-nos-hidden-by-creative). Should write correctly then error/revert the UI without saving; whether the device-side write survives and audibly applies is untested. Test: select NOS, then listen for reduced pre-ringing/treble roll-off despite the error. |
| 12 | Would `SpeakersHRTFMode` do anything audible here? | See [`firmware-findings.md` §6](firmware-findings.md#6-hrtf-mode--what-it-is-and-why-this-app-doesnt-touch-it) — live and controllable per g6-re, but speaker-framed; not implemented here at all (headphone-only development). Needs a speaker setup and the `SET 30` message. |
| 13 | Is "G6X" (USB PID `0x3263`) really the USB-C G6 revision? | See [`firmware-findings.md` §7](firmware-findings.md#7-sound-blasterx-g6-versus-g6x--what-the-evidence-actually-shows) — one third-party project says yes, two USB-ID databases attribute the PID elsewhere; neither confirmed against hardware. Test: read a real G6's USB descriptors (`lsusb -v` / `system_profiler SPUSBDataType`). |
| 14 | Does the G6 remember a 7.1 selection made on another OS? | See [Virtual 7.1](#virtual-71). Present-state baseline is measured (2 ch, zero non-stereo formats); whether a Windows/Linux 7.1 selection persists into a later macOS session is untested. |
| 15 | Do `--playback-speakers-to-7-1`/`-to-5-1` do anything at all? | See [Virtual 7.1](#virtual-71) — the CLI sends byte-identical packets for stereo/5.1/7.1, doubtful but unconfirmed. Test on Linux: `--playback-speakers-to-7-1 --claim-and-release`, then check `pactl list sinks`/`pw-cli ls Node` for a channel-count change. |
| 16 | Where inside the G6 does volume attenuation happen — digital or analog? | See [above](#volume-forwards-to-the-device-not-the-host). That macOS forwards to the device is closed; pre- vs. post-DAC is not, and decides how the [full-scale fix](#full-scale-volume--the-g6-distorts-at-100) actually works. Test: `docs/g6-re/tools/thd_test.py` at several volume settings with a loopback cable. |

---

# Documents still wanted

Creative's knowledge base geo-redirects and renders via JavaScript, so it
can't be fetched here — but prints to PDF fine. SID 200074, 200065 and 200066
are already supplied, in `docs/pdfs/`. Still wanted:

| Wanted | Why |
|---|---|
| A screenshot of Connect 2's Voice → Clarity page | Settles whether Creative's "Voice Enhancer" is this app's *Mic Equalizer*, and shows the eight band frequencies |
| The settings behind any one BlasterX Experience profile | Would let the four empty slots be filled with a real voicing — even one establishes the format |
| Anything on the playback filters with actual curves | Creative's own page says only "4 options to control steepness" |

Reddit is the other gap: blocked by policy in the built-in browser, and not
indexed by Anthropic's crawler, so pasting threads in is the only route.

# Sources

- [Creative — Acoustic Engine](https://us.creative.com/technology/acousticengine/) — Surround, Crystalizer, Bass, Smart Volume, Dialog Plus
- [Creative — Sound Blaster technologies](https://us.creative.com/soundblaster/technology/) — Smart Volume Night mode, Scout Mode, CrystalVoice
- [Creative — CrystalVoice](https://us.creative.com/technology/crystalvoice/) — Noise Reduction, AEC, mic Smart Volume
- Creative KB SID 200071 — *G6 FAQ*: G5-vs-G6 table, Direct Mode on macOS (Q19), mic recording in Direct Mode (Q42), optical+SBX (Q14), sidetone (Q12), factory reset (Q17), Mac feature set (Q18). PDF supplied.
- Creative KB SID 128701 — *G5: Direct Mode versus SPDIF-Out Direct* — mutual-exclusivity rule and behaviour table. PDF supplied.
- Creative KB SID 200074 — *G6: Sound Blaster Connect 2 Software* — Output Mode radio, Acoustic Engine ranges, Dolby knob, 20 profiles, 10-band EQ, lighting modes. PDF supplied (`docs/pdfs/200074.pdf`).
- Creative KB SID 200065 — *G6: Technical Specifications* — SB-Axx1 DSP, 16–600 Ω, Dolby via Optical In, per-mode rates. PDF supplied.
- Creative KB SID 200066 — *Enabling 32bit 384kHz Playback in Windows* — Windows equivalent of the macOS clock-source dance. PDF supplied.
- [Creative — G6 product page](https://us.creative.com/p/sound-blaster/sound-blasterx-g6-usb-c) — 32-bit/384 kHz, 1 Ω output impedance, optical I/O
- [Audio Science Review — G6 review and measurements](https://www.audiosciencereview.com/forum/index.php?threads/review-and-measurements-of-sound-blasterx-g6.7016/) — CS43131 DAC, 85 mW into 300 Ω; [page 2](https://www.audiosciencereview.com/forum/index.php?threads/review-and-measurements-of-sound-blasterx-g6.7016/page-2#post-158688) for the Direct Mode null result
- [Cirrus Logic CS43131](https://www.cirrus.com/products/cs43131) and [datasheet](https://statics.cirrus.com/pubs/proDatasheet/CS43131_DS1155F2.pdf) — selectable interpolation filters
- [r/SoundBlasterOfficial — Direct mode vs default](https://www.reddit.com/r/SoundBlasterOfficial/comments/m1paan/direct_mode_vs_default_on_sbx_g6/) — what Direct Mode disables
- [guru3D — G6 DAC/amp thread](https://forums.guru3d.com/threads/purchased-creative-g6-external-dac-amp.428000/page-4) — filter listening impressions
- [r/SoundBlasterOfficial — direct mode question](https://www.reddit.com/r/SoundBlasterOfficial/comments/1556zzq/sound_blasterx_g6_direct_mode_question/) — host-side effects pass through in Direct Mode
- [mobileaudiophile — Creative DAC review](https://mobileaudiophile.com/reviews/creative-soundblaster-g8-dac-the-bridge-between-devices/) — corroborates 48 kHz DSP-mode ceiling on macOS on a sibling DAC
- `toga_cocoa/widgets/switch.py` in `venv/` — the `set_value`→`on_change` behaviour behind the profile bug
- `src/g6_cli/g6_spec/` in this repo — source for every bytes-derived claim
