# What every setting actually does

A reference for the options this GUI/CLI exposes on the Sound Blaster X G6:
what each one changes, when it changes nothing at all, and how confident we are.

Written for two readers: someone deciding what to switch on, and someone writing
the help text for a UI tooltip. Every section ends with a **Help box** line short
enough to drop straight into the UI.

## How to read the confidence markers

| Marker | Meaning |
|---|---|
| **[bytes]** | Read directly out of the packets in `src/g6_cli/g6_spec/`. Not an opinion — this is what leaves the machine. |
| **[Creative]** | Creative's own documentation or product pages. |
| **[measured]** | Someone put it on a test bench. |
| **[community]** | Consistent reports from forums. Plausible, not proof. |
| **[inferred]** | Our reasoning from the bytes plus the above. Flagged wherever it appears. |
| **[this Mac]** | Observed directly on Luis's own G6 (serial E5004E4F57X) on macOS. |
| **[unknown]** | We could not establish it. Listed in [Open questions](#open-questions) with a test. |

Two facts from [`device-state.md`](device-state.md) shape everything below:
**there is no readback**, so every switch shows what was last *sent*, not what
the device *is*; and the settings live in the G6's firmware, so they persist
across reboots and across operating systems.

---

## The short version

| Setting | What it changes | Works over USB on macOS? |
|---|---|---|
| Output (Speakers/Headphones) | Front headphone jack vs rear line/optical jack | Yes |
| Direct Mode | One position of an `Audio Effects · Direct · SPDIF-Out Direct` radio — not a switch | **No — inert on macOS** (confirmed by ear). Use [Audio MIDI Setup → Clock Source](#macos-audio-midi-setup-is-the-real-control) |
| SPDIF-Out Direct Mode | Bypass for the optical output **only**; mutually exclusive with Direct Mode | **Unknown.** macOS has no equivalent setting, so it may well work — untested |
| Filter | The DAC's reconstruction filter (4 variants) | Yes, but inaudible — see below |
| Decoder mode | Dolby Digital dynamic-range compression | **No.** Needs a Dolby bitstream on optical in |
| SBX profile | Picks which slot of `g6.json` you are editing | Yes — and **changing it already switches the profile** ([bug](#bug-changing-editing-profile-already-switches-the-profile)) |
| SBX Surround / Crystalizer / Bass / Dialog Plus | Real-time DSP on playback | Yes |
| SBX Smart Volume | Loudness levelling — slider **or** Night/"Loud", never both. ["Loud" is likely mislabelled](#smart-volume-and-smart-volume-special) | Yes |
| Recording / Noise Reduction, AEC, Smart Volume | CrystalVoice mic processing | Yes |
| Mic EQ + preset | An 8-band EQ on the mic path | Yes |
| Volume / mute rows | USB Audio Class controls | **No** — macOS owns that interface |

---

# Playback

## Output — Speakers / Headphones

Picks which **physical jack** the G6 drives. On the hardware that is:

| UI label | Jack | What is on it |
|---|---|---|
| **Headphones** | Front 3.5 mm | Headphone out, driven by the Xamp. The front also carries the 3.5 mm mic input. |
| **Speakers** | Rear 3.5 mm | Line Out **/ mini-TOSLINK Out combo jack** — the same socket is the optical output. |

The rear panel is a pair of combo jacks: **Line Out / optical out**, and
**Line In / optical in**, each accepting either a 3.5 mm analog plug or a
mini-TOSLINK optical one. **[Creative]** So "Speakers" is the whole rear output
path, analog *and* optical. The two halves are bypassed by different switches:
[Direct Mode](#direct-mode) for the analog path, and
[SPDIF-Out Direct Mode](#spdif-out-direct-mode) for the optical half only.

**[bytes]** The two commands are genuinely different packets
(`toggle_to_speakers` uses intermediate `0002`, headphones `0004`), each followed
by a long replay of feature slots `0A`–`14`.

The 5.1 and 7.1 variants in the CLI are worth knowing about: **[bytes]**
`speakers_to_5_1()` and `speakers_to_7_1()` literally `return speakers_to_stereo()`.
Upstream's own comment says Sound Blaster Command sends identical packets
whatever channel count you pick, so the channel count is almost certainly set
host-side through the OS, not on the device.

**Help box:** Selects the physical output the G6 drives. Channel-count variants
send identical bytes — the OS decides the channel count, not the device.

## Direct Mode

The single most misunderstood switch on the device — and this GUI models it
wrongly, which is worth knowing before anything else.

### It is not a switch. It is one position of a radio group.

**[Creative]** In Sound Blaster Connect 2, Direct Mode is not a checkbox. Each
output has an **Output Mode** radio group, and Direct is one of its positions:

| Output tab | Output Mode choices |
|---|---|
| **Headphones** | `Audio Effects` · `Direct` |
| **Speakers** | `Audio Effects` · `Direct` · `SPDIF-Out Direct` |

That single fact explains the mutual exclusivity the G5 article describes: they
are not two switches that happen to conflict, they are **three states of one
setting**. There is also a third state this GUI cannot express at all —
`Audio Effects`, the normal/default mode.

**This app exposes two independent booleans instead**, so it can represent
`Direct = on, SPDIF-Out Direct = on`, which the device has no state for. The
honest model would be a single three-way selector per output. **Not changed
here.**

Creative's Setup pages also carry two settings this project never captured:
**Configuration** (Stereo / 5.1 / 7.1 — 5.1 and 7.1 are explicitly *virtual*
outputs), and **Apply Headphone Virtualization to** (`Headphones` or `Line and
Optical Out`) — the latter being the "Headphone Surround for Line/Optical Out"
checkbox in the G5 article.

**What it is meant to do [Creative][community]:** put the G6 into a bit-perfect
path by shutting down the DSP entirely. Not "turn the effects off" — power down
the block that implements them. Everything that touches the signal goes:

- SBX (Surround, Crystalizer, Bass, Smart Volume, Dialog Plus)
- Scout Mode
- The playback equalizer
- The pre-defined audio profiles
- **Microphone recording [Creative]** — Creative's G6 FAQ states it plainly:
  microphone recording is not available in Direct Mode. **Sidetone monitoring
  still works**, which is a useful detail — hearing yourself is not proof the mic
  is being recorded.
- What-U-Hear **[Creative]** — also explicitly broken in Direct Mode.

**Direct Mode is stereo-only [Creative]**, and on the device it is engaged by
holding the **Scout Mode button for 2 seconds**; the Scout Mode indicator then
**blinks continuously** to show you are in Direct Mode. That blink is the only
honest status readout you have, since the protocol has no readback.

**The sample-rate payoff [Creative]:** the G6 FAQ's own G5-vs-G6 table gives
Direct Mode as **32-bit/384 kHz PCM**, plus **DSD64/DSD128 over DoP**. The DAC is
a **Cirrus Logic CS43131 [measured]**, exactly a 32-bit/384 kHz part — the limit
is the DSP in front of it, not the converter. **DSD is Windows-only: Creative
states macOS does not support DSD playback.**

**How much difference does it actually make?** Essentially none, if you already
had the effects off. Amir at Audio Science Review tested the G6 dashboard with
and without Direct Mode and reported that **"it makes no difference"** once the
effects were turned off, adding that Creative kept the pipeline clean when
features are disabled. **[measured]** Forum users with Beyerdynamic headphones
report the same null result by ear. **[community]**

**"Bit perfect" only covers the G6.** Direct Mode stops the *device* adding
anything; it cannot undo what the host already did. Anything applied before the
USB stream leaves the computer — Windows' Dolby Atmos for Headphones, macOS
system EQ, a player's own DSP — still arrives at the DAC and still plays.
**[community]** Direct Mode is a statement about the G6's internals, not about
the whole chain.

So the honest summary: Direct Mode is for unlocking >96 kHz and DSD, and for
peace of mind. It is not a sound-quality upgrade over "all effects off".

### Why this switch does nothing on macOS — answered

Not a bug in this app, and not something a different packet would fix. Creative's
G6 FAQ answers it directly **[Creative]**: to enable Direct Mode on a Mac you
must change the DSP/Direct setting **from the Audio MIDI Setup menu**, not from
the button on the G6 — because **macOS always controls the mode setting of any
audio device, and overwrites the device's own setting.**

That is the whole explanation. macOS asserts the mode through the USB Audio Class
clock selector, continuously. Whatever this app writes over HID, Core Audio
overrides it. So on macOS:

- The **Direct Mode switch in this GUI is inert**, and so is the 2-second
  button-hold on the device itself.
- The real control is **Audio MIDI Setup → Clock Source**. See
  [the macOS section](#macos-audio-midi-setup-is-the-real-control) below.
- Your observation — SBX audible regardless of this switch — is exactly what the
  documentation predicts. You had Clock Source set to *DSP Clock*, so the DSP was
  in the path no matter what.

**Confirmed by ear [this Mac].** Switching Audio MIDI Setup to *Stereo Direct*
makes the SBX controls stop doing anything; switching back to *DSP Clock* brings
them back. That is Direct Mode working correctly — just not through this app.

This also means the switch should probably be **disabled with an explanatory note
on macOS**, the way the volume rows already are. Not changed here.

**Help box:** Shuts down the entire DSP for a bit-perfect path, and unlocks
32-bit/384 kHz and DSD. Disables SBX, Scout, the EQ, mic recording and
What-U-Hear (sidetone survives). **On macOS this switch does nothing** — macOS
overrides the device's mode; use Audio MIDI Setup → Clock Source instead. With
effects already off it is measurably identical to normal mode.

## SPDIF-Out Direct Mode

**[bytes]** Structurally the same command as Direct Mode with one field changed:

```
Direct Mode        5a 3903 0005 <01|00> 00000000 …
SPDIF-Out Direct   5a 3903 000d <01|00> 00000000 …
                            ^^^^
```

Same opcode, same commit packet, different target selector.

**[Creative]** Creative's knowledge-base article *Direct Mode versus SPDIF-Out
Direct* (Solution ID 128701) documents this for the **Sound BlasterX G5**, the
G6's immediate predecessor. Its three key statements:

- **Direct Mode** gives direct playback to the stereo speaker channel, at up to
  192 kHz on the G5 (384 kHz on the G6, which has the better DAC).
- **SPDIF-Out Direct** allows bit-to-bit streaming of up to **24-bit/96 kHz PCM**
  to the optical output, without processing. That 96 kHz ceiling is S/PDIF's, not
  the device's.
- **They are mutually exclusive.** Enabling either one automatically disables the
  other. The article shows the checkbox greying out in Creative's own UI.

### The behaviour table

This is the part worth memorising — it is more specific than "bypasses the DSP",
and it corrects the obvious guess. From Creative's own table, with Windows'
default playback device set to Speakers:

| Direct Mode | SPDIF-Out Direct | Headphone / Line Out | Optical Out |
|---|---|---|---|
| off | off | plays, **with** effects | plays, **with** effects |
| **on** | off | plays, **no** effects | **silent** |
| off | **on** | plays, **with** effects | plays, **no** effects, and **the G5 can no longer control its volume** |

Three things fall out of that:

1. **Direct Mode kills the optical output entirely.** Not "passes it through
   unprocessed" — no sound at all. If you ever run optical, this is the switch
   that will make you think the device broke.
2. **SPDIF-Out Direct is narrow.** It only touches the optical output. The analog
   Headphone/Line Out keeps its effects. So it is *not* "Direct Mode for the rear
   jack" — the rear jack's analog half is unaffected.
3. **SPDIF-Out Direct hands volume control to the receiver.** Bit-perfect means no
   digital volume scaling, so the G6's knob stops affecting the optical stream.
   Expected, and alarming if you do not know it.

**Confirmed for the G6 [Creative].** The article above covers the G5, but the
G6's own FAQ states the same rule in its own words: the optical output *does*
carry audio processing and SBX effects in normal mode, and does *not* once
SPDIF-Direct is selected. So the middle and bottom rows of that table apply to
the G6 as written. The G5-specific part is the 192 kHz figure — the G6 does
384 kHz on the analog side — and the "volume cannot control via G5" wording,
which is **[inferred]** to hold for the G6 for the same bit-perfect reason.

### One consequence for this GUI

Because the two are mutually exclusive on the device but are **two independent
switches in this UI**, you can put both on. The G6 will silently turn one off,
this app will never know (no readback), and `g6.json` will record a state the
hardware is not in. Worth making them mutually exclusive in the UI. Not changed
here.

Creative's screenshots also show a third advanced setting, **Headphone Surround
for Line/Optical Out**, which this project does not expose at all — it was never
captured in the protocol work.

### About S/PDIF itself

Worth correcting a common figure: TOSLINK is not limited to 256 kbit/s. Consumer
S/PDIF carries roughly 3 Mbit/s, which is enough for **2-channel PCM up to
24-bit/96 kHz**, or a compressed multichannel bitstream — Dolby Digital at up to
640 kbit/s, DTS at up to 1.5 Mbit/s. What it cannot carry is uncompressed
multichannel PCM, which is why 5.1 over optical always means a compressed
bitstream.

So the intuition is right for the wrong reason: two-channel PCM over optical
beats Dolby Digital 5.1 over optical on raw fidelity, because one is lossless and
the other is a lossy codec — not because of a bandwidth ceiling.

The G6's optical in and out share the rear combo jacks with Line In and Line Out
**[Creative]**, and the optical out supports up to 5.1 channels. It decodes Dolby
Digital; it does **not** do Dolby Digital Live *encoding* **[community]**, so it
cannot turn your Mac's stereo or multichannel PCM into a 5.1 bitstream for a
receiver. Optical out from a Mac therefore means 2-channel PCM.

**Help box:** The same DSP bypass as Direct Mode, applied to the optical
(S/PDIF) output path instead of the analog one. Only relevant if something is
plugged into the optical out.

## Filter — the four reconstruction filters

**[bytes]** Four values, sent as the target field of opcode `6c03`:

| Label | Bytes |
|---|---|
| Fast Roll Off — Minimum Phase | `0001` |
| Slow Roll Off — Minimum Phase | `0002` |
| Fast Roll Off — Linear Phase | `0004` |
| Slow Roll Off — Linear Phase | `0005` |

These are the **CS43131's built-in interpolation filters [measured]**, not a
Creative invention. Cirrus documents the part as offering selectable responses
combining fast/slow roll-off with linear/minimum-phase behaviour. Two independent
axes:

- **Roll-off** — how sharply the filter cuts just below Nyquist. *Fast* holds
  flat response to nearly 20 kHz then cuts hard; *slow* starts sloping earlier
  and cuts gently, trading a little top-octave flatness for less ringing.
- **Phase** — where the filter's ringing goes. *Linear phase* rings symmetrically,
  so there is a small pre-echo *before* each transient, and it is time-coherent
  across frequency. *Minimum phase* puts all the ringing after the transient —
  no pre-echo, at the cost of frequency-dependent group delay.

**Default [community]:** Fast Roll Off — Minimum Phase.

**[Creative]** The G6 FAQ's G5-vs-G6 comparison lists "4 roll off filters" as a
G6 addition — the G5 has none at all. So this control is genuinely part of what
you paid for, even if the audible result is what follows.

Creative's own description is almost content-free — Connect 2's Filters page says
only that it controls the roll-off frequencies, with four options for the
steepness of the transition. No frequency response curves, no guidance on which
to pick. The DAC datasheet is the better source, which is why this section leans
on it.

### Which one for a DT 990 PRO, DT 880 or DT 770?

Honest answer: **it does not matter, pick any and stop thinking about it.**

The entire difference between these four lives in the top half-octave — above
roughly 18 kHz — and in the pre/post-ringing of a single impulse at a level
tens of dB below the signal. For scale: your three Beyerdynamics differ from each
other by *ten-plus dB* through the treble, and the DT 990's 8–10 kHz peak is
itself around +10 dB. The filter choice moves things by a fraction of a dB in a
region where the headphone is already doing something dramatic, and where most
adults cannot hear at all.

If you want a rule anyway:

- **Slow Roll Off — Minimum Phase** — no pre-ringing at all, gentlest top end.
  The "least filter" option, and the one worth trying first on the DT 990, whose
  treble peak is the sharpest of the three.
- **Fast Roll Off — Linear Phase** — the measurement-correct choice: flattest to
  20 kHz, time-coherent. What most desktop DACs default to.
- Leave it on the stock Fast Roll Off — Minimum Phase if you would rather not
  think about it. Nothing is broken.

A far bigger lever for all three headphones is the G6's **gain switch** (a
physical switch on the device, not exposed in software). The DT 990 PRO and
DT 880 at 250 Ω, and any 600 Ω variant, want **high gain**; the 80 Ω DT 770 does
not. The G6 drives 85 mW into 300 Ω on high gain **[measured]** and has ~1 Ω
output impedance **[Creative]**, so all three are comfortably driven.

**Help box:** Picks the DAC's reconstruction filter. Differences are confined to
above ~18 kHz and to impulse ringing — inaudible on essentially any headphone.
Slow Roll Off / Minimum Phase rings least; Fast Roll Off / Linear Phase measures
flattest.

## Decoder mode — Full / Normal / Night

This is **Dolby Digital Dynamic Range Control**, and it is why you hear nothing
when you change it.

**[Creative]** Confirmed twice over: the G6 technical specifications list Dolby
Digital Decoding as *"Yes (via Optical In)"* — the optical qualifier is Creative's
own — and Connect 2's Dolby page is a single knob sweeping **Full → Normal →
Night**, described as Dynamic Range Control for Dolby Digital media.

**[bytes]** The three values are float32, and they are exactly the knob's three
detents — 1.0, 2.0, 3.0 in knob order:

| Label | Bytes | As float32 |
|---|---|---|
| Full | `0000 803F` | 1.0 |
| Normal | `0000 0040` | 2.0 |
| Night | `0000 4040` | 3.0 |

**[Creative]** Creative describes the integrated Dolby decoder's Dynamic Range
Control as letting you tailor how wide the swing between loud and quiet passages
is, on a scale from Full through Normal to Night.

- **Full** — no compression. The full dynamic range as mastered: explosions loud,
  whispers quiet.
- **Normal** — moderate compression, the standard listening setting.
- **Night** — heavy compression. Quiet dialogue pulled up, loud peaks pulled
  down, so you can watch a film at 11pm without riding the volume knob.

**Why it does nothing on your Mac:** dynamic range control is a parameter *of the
Dolby Digital decoder*. It applies only while the G6 is actually decoding a Dolby
Digital bitstream, which on this device means a DD stream arriving at the
**optical input**. macOS sends the G6 plain PCM over USB. No Dolby decoder in the
path, nothing for the setting to modify. The packet is sent and accepted; it
simply has no work to do.

It is not broken, and it is not macOS-specific — it would do nothing over USB on
Windows either.

**[Creative]** Dolby Digital decoding is one of the headline G6-over-G5 upgrades:
the FAQ's comparison table lists it as *Yes* for the G6 and *No* for the G5. So
the decoder is real hardware, it simply needs feeding.

**How to actually feed it [Creative]:** connect a Dolby Digital source to the
optical **input**. Creative's documented example is a PS4 — USB to the G6 for
chat, optical from the console for game audio, with the console's Primary Output
Port set to digital/optical. An Xbox connects optical-out to the G6's optical-in.
A Mac cannot produce a Dolby Digital bitstream over USB, so no USB-only setup
will ever exercise this.

**Help box:** Dynamic-range compression for the built-in Dolby Digital decoder.
Full = untouched, Night = quiet parts raised and loud parts tamed. Only has any
effect while decoding a Dolby Digital bitstream from the optical input — it does
nothing for PCM over USB.

## Audio interface — Mute, Volume, Channels

Standard USB Audio Class controls. **[bytes]** Volume is sent as a signed 16-bit
value in 1/256 dB units, the USB-AC convention: 100% is `0x0000` (0 dB), 50% is
−10.3 dB, 0% is −64 dB. That is why the steps are coarse (10% increments) and why
the scale sounds logarithmic rather than linear.

**Hidden on macOS.** These live on the AudioControl interface, which macOS's
kernel audio driver owns and will not release. See [`gui.md`](gui.md).

---

# macOS: Audio MIDI Setup is the real control

The most important thing to know about running a G6 on a Mac, and the answer to
"why does Direct Mode do nothing?".

**[Creative]** Creative's G6 FAQ: on a Mac you change the DSP/Direct setting from
the **Audio MIDI Setup** menu rather than with the button on the G6, because
**macOS always controls the mode setting of any audio device and overwrites the
device's own setting**. The G6 is plug-and-play on macOS, driven by Apple's stock
USB audio driver, and Creative ships no Sound Blaster Command for it.

Open **Audio MIDI Setup** (`/Applications/Utilities/`), select the G6, and you
get two rows that matter.

## Clock Source — DSP Clock vs Stereo Direct

Normally a Core Audio "Clock Source" picks which device supplies timing in a
multi-device rig. Creative overloads it: on the G6 the two clock sources are two
**internal signal paths**, and picking one selects the mode.

| Clock Source | Path | Channels | Rates observed **[this Mac]** | Effects |
|---|---|---|---|---|
| **DSP Clock** | Through the DSP | Stereo | up to 32-bit / **48 kHz** | SBX, Scout, EQ all available |
| **Stereo Direct** | Straight to the DAC | Stereo only | up to 32-bit / **384 kHz** | none — this *is* Direct Mode |

**So `Stereo Direct` is how you turn Direct Mode on under macOS.** Not the switch
in this app, not the button on the device.

**[community]** The same two names appear on other Creative DACs — reports on the
Sound Blaster E5 describe switching its clock source between Stereo Direct and
DSP Clock in Audio MIDI Setup for exactly this reason — and a reviewer of a later
Creative DAC records the same 48 kHz ceiling in DSP mode on macOS while only
direct mode reaches 32-bit/384 kHz. Your G6 behaves identically.

### Gotcha: switching back from 384 kHz can wedge the device

**[this Mac]** With the format set to 32-bit/384 kHz under *Stereo Direct*,
switching Clock Source back to *DSP Clock* breaks audio — DSP Clock cannot do
384 kHz, and Core Audio does not renegotiate the format for you. The recovery is:

1. Switch back to **Stereo Direct**.
2. Set the format to something DSP Clock supports — **2 ch, 24-bit, 48 kHz**.
3. *Now* switch to **DSP Clock**. Effects return.

So: **drop the sample rate before changing clock source**, not after. Worth a
line in any UI help text about Direct Mode on macOS.

The 48 kHz cap is worth dwelling on: Creative's marketing figure for non-direct
playback is 96 kHz, but **on macOS the DSP path tops out at 48 kHz**. If you want
anything above 48 kHz on a Mac, you must give up every effect. There is no
middle setting.

## Format — bit depth and sample rate

The second row picks the stream format from whatever the current clock source
allows. Two things worth knowing:

- **Higher is not better here.** 24-bit/48 kHz is a perfectly sensible choice; it
  matches the overwhelming majority of source material, and you will not hear the
  difference at 384 kHz. You already confirmed as much on the DT 990
  **[this Mac]** — and Audio Science Review could not *measure* a difference
  between Direct Mode and normal mode with effects off. **[measured]**
- **Bit depth beyond 24 buys nothing audible.** 24-bit already covers ~144 dB of
  dynamic range, far beyond both the G6's 130 dB DAC and any listening room.

The genuine reasons to choose Stereo Direct are DSD playback (**not supported on
macOS at all [Creative]**) and hi-res files you actually own. Otherwise DSP Clock
at 24-bit/48 kHz, with the effects you like, is the better trade on a Mac.

## What this means for this app

- The **Direct Mode switch does nothing on macOS.** macOS re-asserts the mode
  continuously, so the HID packet is overridden. The switch should probably be
  disabled with a note pointing at Audio MIDI Setup — the way the volume rows
  already are. **Not changed here.**
- Everything else on the HID interface **does** work: output switching, filter,
  decoder, lighting, mic boost, Voice Clarity, and all of SBX. That is worth
  stating plainly, because Creative's FAQ claims there is "no customization of
  Acoustic Engine features" on Mac — true of *their* software, since they never
  shipped a Mac app, but not of the device. This project drives those features
  over HID on macOS and they work. **[this Mac]**
- If you select **Stereo Direct**, expect the SBX tab to stop having any audible
  effect, and mic recording to stop working. That is the device behaving
  correctly, not the app failing.

## What the clock source does *not* cover

Worth being precise, because it is easy to over-generalise (this document did,
in an earlier revision).

Creative's own Output Mode is a **three-way** choice — `Audio Effects`,
`Direct`, `SPDIF-Out Direct`. macOS's Clock Source offers only **two** positions,
DSP Clock and Stereo Direct. Those map onto the first two.

**There is no macOS equivalent of SPDIF-Out Direct.** So the conclusion that
macOS overrides Direct Mode does *not* automatically extend to it: macOS may
simply have no opinion about that third state and let this app's HID packet
through. Nobody has tested it, and it cannot be tested without something plugged
into the optical output.

That is why the GUI **disables Direct Mode on macOS but leaves SPDIF-Out Direct
enabled**. Untested is not the same as broken, and disabling the switch would
have removed the only means of ever finding out.

**Help box:** On macOS, Direct Mode is selected in Audio MIDI Setup → Clock
Source, not here. *DSP Clock* keeps all effects and caps at 48 kHz; *Stereo
Direct* is Direct Mode — bit-perfect to 384 kHz, no effects, no mic recording.

---

# Hardware facts worth having

**[Creative]**, from the G6 technical specifications (SID 200065):

| | |
|---|---|
| Model / DSP | SB1770 / **SB-Axx1** audio processor |
| DAC | Cirrus Logic CS43131 **[measured]**, 130 dB SNR/DNR |
| Headphone amp | Xamp Discrete HP Bi-Amp, **1 Ω** output impedance |
| Headphones supported | **16 – 600 Ω** |
| Dolby Digital decoding | **Yes — via Optical In** |
| DSD over PCM | DSD64, DSD128 — **Direct Mode only**, and not on macOS |
| Playback (Direct Mode) | 16/24/32-bit at 44.1 / 48 / 88.2 / 96 / 176.4 / 192 / 352.8 / **384 kHz** |
| Recording | up to 32-bit/192 kHz, Line In, Optical In and Mic In alike |
| Jacks | Line In + mini-TOSLINK In combo · Line Out + mini-TOSLINK Out combo · Headphone/Headset · Ext Mic In · USB |
| macOS driver | **Apple's in-box audio driver** — Creative ships none |

All three of your Beyerdynamics sit comfortably inside 16–600 Ω. Note the two
*separate* front jacks: Headphone/Headset and Ext Mic In.

**On Windows**, reaching 32-bit/384 kHz is the same idea as on macOS but through
a different dialog **[Creative]**: set the G6's speaker configuration to
**Stereo**, then pick *32 bit, 384000 Hz (Studio Quality)* as the Default Format
in the playback device's properties. Note what is *not* in those instructions —
any mention of toggling a Direct Mode switch. On both operating systems, the
high-rate stereo path is entered by choosing the format in the OS.

# The physical controls

Not software, but you cannot reason about the device without them — and with no
readback, the LEDs are the only status you get. **[Creative]**

| Action | Control | Result |
|---|---|---|
| Toggle Scout Mode | Press the Scout Mode button | Scout Mode on/off |
| Toggle Direct Mode | **Hold** Scout Mode for 2 s | Scout indicator **blinks continuously** while in Direct Mode (ignored on macOS) |
| Toggle Sidetone | **Hold** the volume knob for 2 s | Knob LED white → red; side icon headphone → mic. Blinking white = sidetone muted |
| Gain | Physical switch | Set it for your headphone impedance — high gain for 250 Ω+ |
| **Factory reset** | **Hold Scout Mode + volume knob together for 5 s** | The 3 side LEDs cycle. **Erases every saved setting in the G6.** |
| Soft reset | Unplug USB, wait 3 s, replug | Recovers an unresponsive card |

**The factory reset is the most useful thing on this list.** Because there is no
readback, this app can drift out of sync with the hardware and you have no way to
compare. A factory reset is the one way to force a known state — after which
`g6.json`'s assumed defaults and the device genuinely agree. Note it also wipes
lighting and everything else.

---

# SBX

## Profiles — Gaming / Music / Cinema / Special

The one section where the UI is honestly misleading, and the code says so plainly.

**[bytes]** `sbx_toggle()` and `sbx_slider()` build their packets from the audio
feature and the value **only**. The `profile_name` argument never reaches the
wire. The G6 has exactly one live SBX state.

**[bytes]** And the four profiles ship empty. `Profile.init()` calls
`SBX.default()` for all four, which is identical every time: every effect off,
every slider at 50, Smart Volume special `None`. There are no factory Gaming or
Cinema voicings in this codebase — Creative's own software has preset content,
but none of it was captured here.

**[Creative]** For context on what is missing: the G6 FAQ explains that BlasterX
Acoustic Engine and SBX Pro Studio share the same core algorithms, and that the
Acoustic Engine's addition is exactly the **preset and customisable profiles** —
including professionally tuned ones for specific games. Connect 2 ships **20**
of them — Gaming, Music, Movie, Adventure and Action, FPS, RPG, Real Time
Strategy, Driving Simulation, Stadium, and eleven title-specific ones (CS:GO,
DOTA 2, Overwatch, PUBG, The Witcher 3, Rocket League, Project CARS, League of
Legends, Arena of Valor, Call of Duty, Metal Gear Solid V). Predefined profiles
cannot be deleted, only reverted; custom ones can be added.

**None of that content exists here.** Note also that this project's four names
are its own: Creative has *Movie*, not *Cinema*, and nothing called *Special*.
The four slots are a local abstraction that happens to borrow three of Creative's
names, which is why they start empty.

So what a profile really is: **a named row in `g6.json` recording what you last
set**. Consequences:

- Editing a profile that is not the active one is **audible immediately** — the
  bytes go straight to the single live SBX state.
- Those edits are saved under the profile you were editing.
- `sbx_profile_switch()` is the only bulk replay in the codebase: it walks the
  chosen profile's saved values and re-sends them all. That is the moment your
  edits to other profiles get overwritten.

The SBX tab already warns about this. Worth keeping.

### Bug: changing "Editing profile" already switches the profile

**[bytes][measured]** Confirmed and reproduced, without touching the device.

Picking a different profile in the **Editing profile** dropdown is supposed to be
a pure UI action — repoint the controls at another slot, send nothing. It does
not work that way on macOS.

`on_editing_change` repopulates every control from the newly selected profile:

```python
row.toggle.switch.value = getattr(sbx, toggle_getter)()
row.slider.slider.value = getattr(sbx, slider_getter)()
```

On the Cocoa backend, assigning `.value` **fires `on_change`**:

```python
# toga_cocoa/widgets/switch.py
def set_value(self, value):
    old_value = self.native.state == NSOnState
    self.native.state = NSOnState if value else NSOffState
    if self.interface.on_change and value != old_value:
        self.interface.on_change()          # ← fires on a programmatic set
```

So each repopulated control submits to the device. Reproduced with the fake API:
building the SBX page, making Cinema differ from Gaming in four values, then
setting the dropdown to `Cinema`, produces **four device writes** —
`sbx_toggle`/`sbx_slider` for surround and bass — from an action that should send
nothing.

Note `value != old_value`: only controls whose value actually *differs* fire.
That is why the effect scales with how different the two profiles are, and why it
is invisible when they match.

**Consequences**

- Your observation is exactly right: the sound changes the moment you pick a
  different profile, so **"Switch to this profile" appears to do nothing.**
- The button is not *entirely* redundant. It still calls `sbx_profile_switch()`,
  which re-sends every value and — importantly — records the newly selected
  profile in `g6.json` and updates the banner. The audio has already moved; the
  button makes the bookkeeping agree.
- The safety property the SBX tab's warning relies on ("editing another profile
  is audible but does not switch you") is therefore **not** what happens. Merely
  browsing profiles rewrites the live SBX state.

**Why the tests never caught it:** the suite asserts on `FakeG6Api` calls, and
with the default model **all four profiles are identical**, so `value !=
old_value` is never true and nothing fires. A regression test needs profiles that
actually differ.

**Fix sketch** (not applied): guard `on_editing_change` with a reentrancy flag
that suppresses submits while repopulating — the same shape as the existing
re-entry guard in `slider_row`'s snap handler.

**Help box:** Profiles are slots in this app's own file, not presets on the
device. The G6 has one live SBX state, so editing any profile is heard
immediately; switching profiles replays that slot's saved values over it.

## How Creative's own UI presents these five

**[Creative]** Worth knowing, because this GUI presents all five identically —
an on/off switch plus a 0–100 slider — and Connect 2 does not:

| Effect | Creative's control | Separate on/off? |
|---|---|---|
| Surround | knob: **Normal · Wide · Ultra Wide** | no — *Normal* is the low end |
| Crystalizer | knob **0–100** | **yes** |
| Bass | knob **0–100** | **yes** |
| Smart Volume | knob: **Off · Auto · Night** | no — *Off* is the low end |
| Dialog+ | knob: **Off · Normal · Balanced · Dialog Focus** | no — *Off* is the low end |

**[bytes]** The protocol has a toggle slot *and* a slider slot for all five, so
this app is not inventing the extra switches — Creative simply chooses not to
show three of them, folding "off" into the bottom of the knob instead.

The practical read: for **Surround** and **Dialog+**, your 0–100 slider is a
finer-grained version of a control Creative ships with 3–4 labelled detents. If
you want to match Creative's positions, use roughly 0 / 50 / 100 for Surround and
0 / 33 / 66 / 100 for Dialog+. Whether the firmware interpolates between them or
quantises to the nearest detent is **[unknown]**.

## Surround

**[Creative]** Opens up a wider sound field and simulates a surround speaker
layout over two channels — HRTF-based virtualisation. Connect 2's three detents
are **Normal**, **Wide** and **Ultra Wide**.

**[community]** Reported to work genuinely well for positional cues in games with
a real surround source, with modest quality cost. Less useful on stereo music.
Slider sets the strength.

**Help box:** Virtual surround. Widens the stage and places sounds around you
from a multichannel source. Effective for games, less so for stereo music.

## Crystalizer

**[Creative]** Aims to restore detail and dynamic range lost to lossy compression
— an expander with a treble tilt, in practice. Creative pitches it at MP3/streamed
material and at adding bite to films and games.

Immediately audible, and easy to overdo: it is boosting transients and top end,
so on an already-bright headphone like the DT 990 PRO a high setting gets harsh
fast.

**Help box:** Re-expands dynamics and sharpens transients to counter compression
artefacts. Audible immediately. Go easy on bright headphones.

## Bass

**[Creative]** Fuller, deeper low end, with added harmonics rather than pure
level. Slider sets amount.

**Help box:** Bass enhancement — adds depth and harmonic weight to the low end.

## Smart Volume (and Smart Volume special)

**[Creative]** Loudness levelling: continuously measures level and applies gain
and attenuation so that quiet and loud passages, and different tracks, arrive at
a consistent volume.

You noticed these two controls are entangled, and that is real.

**[bytes]** They are mutually exclusive by construction. `sbx_profile_switch()`:

```python
if smart_volume_special is None:
    self.sbx_slider(..., SMART_VOLUME_SLIDER, value=...)
else:
    self.sbx_smart_volume_special(..., smart_volume_special_hex=...)
```

If a special mode is set, the **slider is never sent**. They write different
feature slots (`05` for the slider, `06` for special) and set a *mode*, not an
amount:

| Special | Bytes | As float32 | Connect 2 calls it |
|---|---|---|---|
| Loud | `0000 803F` | 1.0 | **Auto** |
| Night | `0000 0040` | 2.0 | Night |

**Naming warning [inferred]:** this app's label **"Loud" is probably wrong for
the G6.** The name comes from upstream's capture; Connect 2's Smart Volume knob
reads **Off · Auto · Night**, so value 1.0 is *Auto* — ordinary automatic
levelling, not a "make it louder" mode. Same byte either way, but the UI label
sets a misleading expectation. Worth renaming.

Same 1.0/2.0 encoding as the decoder modes — an index, not a level. **[Creative]**
describes Night mode as adding a gentle equalisation curve compensating for how
human hearing behaves at low volume (equal-loudness compensation, so bass and
treble do not vanish when you turn things down).

That is why the volume behaves oddly: with a special mode set you are running a
fixed levelling curve and the slider is inert; with it on `None` you are running a
variable-strength leveller.

The UI would read better with Smart Volume special directly under Smart Volume
rather than at the end of the tab. **Noted, not changed** — you asked to leave it.

**Help box:** Evens out volume differences between quiet and loud passages.
Setting a special mode (Night or Loud) replaces the slider entirely — Night adds
equal-loudness compensation for low-volume listening.

## Dialog Plus

**[Creative]** Your reading is right. It analyses centre-channel and dialogue
content, extracts the vocal band through filtering and a frequency/time-domain
algorithm, and lifts it so speech sits above the soundtrack and above room noise
— without simply turning the whole mix up.

**Help box:** Lifts voices and dialogue above the rest of the mix. Useful for
films with buried dialogue.

---

# Recording (CrystalVoice)

Everything in this tab processes the **microphone**, not what you hear.

## What actually works — listening tests

**[this Mac]** Tested by ear on a ModMic V2 (a condenser) through the G6 on
macOS:

| Control | Result |
|---|---|
| Mic Boost | **Works.** Immediate and obvious — the mic gets audibly louder. |
| Noise Reduction (toggle) | **Works.** Audibly drops the noise floor *even with the level at 0*, so the toggle alone is doing real work. |
| Noise Reduction Level | **Works.** At 100 the suppression is heavy enough to start eating parts of the voice. Mid-range is the better trade. |
| Acoustic Echo Cancellation | **Works.** Removes echo, and costs some vocal clarity doing it. Sensible on for calls, off for recording. |
| Mic Equalizer + presets | **Works.** On/off is clear and the presets genuinely differ. |
| **Smart Volume** | **No audible effect.** See below. |

### Nothing here removes keyboard and mouse clicks

**[this Mac]** Confirmed: no combination of these controls suppresses key
clatter or mouse clicks.

That is expected rather than a failing. Noise Reduction is a *steady-state*
noise suppressor — it estimates a constant noise profile (fans, hum, hiss) and
subtracts it. Keyboard and mouse noise is the opposite: short, loud, broadband
transients that look like speech onsets to that kind of algorithm. Removing them
needs a transient suppressor or a gate, which lives on the computer, not on this
device.

### Smart Volume (recording) did nothing

**[this Mac]** The one control on this tab with no observable effect, while
every other control on the same tab behaved exactly as documented — which makes
a simple "user error" explanation unlikely.

Candidate explanations, none confirmed:

- Its threshold may need a larger change in mic distance than ordinary speech
  produces, so normal talking never triggers it.
- It may be inactive over USB on macOS, the way Direct Mode is.
- It may need Noise Reduction or another CrystalVoice block active first.

**[bytes]** The packet itself is unremarkable — feature slot `2C`, the same
enable/commit shape as Noise Reduction (`04`) and AEC (`00`), both of which
demonstrably work. So the command is very unlikely to be malformed.

Recorded as an open question rather than a bug.

### A note on the "Dynamic Mic 1" preset

**[this Mac]** Confirmed: on a ModMic V2 it **distorts**. That is the preset
behaving correctly and being applied to the wrong kind of microphone — the
ModMic is a condenser, and Dynamic Mic 1 exists to add 8–12 dB for a *dynamic*
mic's much lower output. Also worth knowing that the G6 does not supply phantom
power **[Creative]** and takes a 3.5 mm 3-pole mono mic.

Separately: **Preset 6** is the most noticeable of the numbered presets, and its
aggressive presence lift can read as a slight echo — which Acoustic Echo
Cancellation then partly removes, so the two interact audibly.

## Noise Reduction (+ Level)

**[Creative]** Analyses the mic signal, identifies steady background noise, and
suppresses it so your voice carries over it. Fans, air conditioning, hum.

**[bytes]** The toggle writes feature `04`. The level writes feature `05` — and
the level scale is not what the UI suggests:

| UI level | Bytes | As float32 |
|---|---|---|
| 0 | `0000 0000` | 0.0 |
| 20 | `CDCC CC3D` | 0.1 |
| 40 | `CDCC 4C3E` | 0.2 |
| 60 | `9A99 993E` | 0.3 |
| 80 | `CDCC CC3E` | 0.4 |
| 100 | `0000 003F` | **0.5** |

The slider's 100% sends 0.5, not 1.0. Steps of 20 only. **[inferred]** So the UI
maximum is the middle of the underlying parameter's range — either Creative caps
it deliberately, or the upper half was never captured. Either way, "100" is not
"as much as the device can do".

**Help box:** Suppresses steady background noise on the mic. Level steps in 20%
increments; the maximum sends half the device's full-scale parameter.

## Acoustic Echo Cancellation

**[Creative]** Removes the echo caused by your speakers' output being picked up
by your mic and sent back to the far end. A call-quality feature, not a
sound-quality one.

**[bytes]** Feature slot `00`.

Genuinely useful on **speakers**; near-pointless on **headphones**, where there
is no acoustic path from output to mic. You reported noticing an effect — that is
expected, because AEC also runs an adaptive filter on the mic signal, so it can
colour the voice even with nothing to cancel.

**Help box:** Cancels your speakers' sound being picked up by the mic during
calls. Only meaningful when using speakers — on headphones there is no echo path.

## Smart Volume (recording)

**[Creative]** Automatically levels *your own voice* so you arrive at a constant
loudness to the other party whether you are leaning into the mic or sitting back.
The mic-side twin of playback Smart Volume.

**[bytes]** Feature slot `2C`.

Very useful for calls and streaming. Undesirable for recording anything you plan
to edit, since it destroys the original dynamics.

**Help box:** Keeps your voice at a consistent level regardless of how close you
are to the mic. Great for calls, bad for recordings you intend to edit.

## Mic Equalizer + presets

**[bytes]** This is the best-documented thing on the page, because the presets are
not opaque — they are eight float32 gains in dB, written to feature slots
`14`–`1B`, low band to high. Decoded in full:

| Preset | B1 | B2 | B3 | B4 | B5 | B6 | B7 | B8 | Shape |
|---|---|---|---|---|---|---|---|---|---|
| Preset 1 | −3 | −4 | 0 | *(0)* | +3 | −3 | +4 | +5 | Cut lows, scoop mids, lift presence |
| Preset 2 | −3 | −4 | 0 | *(0)* | +4 | −2 | +2 | +4 | As 1, gentler top |
| Preset 3 | −2 | −3 | +3 | +4 | +4 | −4 | +3 | +2 | Forward mids, notch, mild air |
| Preset 4 | −3 | −5 | 0 | +4 | 0 | −3 | 0 | 0 | Clean-up only: cut rumble, one mid lift |
| Preset 5 | −2 | −3 | +2 | +4 | +4 | 0 | −3 | +2 | Warm and mid-forward, tamed presence |
| Preset 6 | −5 | −4 | −2 | 0 | +3 | +4 | +6 | +7 | Aggressive bright/telephone tilt |
| Preset 7 | 0 | +3 | −2 | −4 | −4 | −2 | +5 | +7 | Smile curve: body + air, scooped mids |
| Preset 8 | 0 | 0 | +2 | +2 | +3 | −4 | +2 | +4 | Mild all-round lift |
| Preset 9 | 0 | 0 | +2 | +2 | −2 | 0 | −4 | +4 | Softens presence, keeps air |
| Preset 10 | 0 | +2 | −2 | 0 | +3 | +5 | +6 | +5 | Bright, intelligibility-focused |
| Dynamic Mic 1 | 0 | +8 | 0 | +12 | +12 | +4 | +8 | +10 | Huge broadband lift |

**Reading the table.** The presets are unnamed in Creative's software too — they
are voicings, not scenarios. The pattern across them is a classic broadcast-mic
toolkit: cut low-frequency rumble and proximity-effect mud (bands 1–2), and lift
the presence and air bands (7–8) for intelligibility. Bands run low to high;
that ordering is **[inferred]** from the slot order and the consistent
low-cut/high-boost shape, not documented.

**Dynamic Mic 1 is the one with a real name**, and it is the giveaway: `PRESET_DM_`
in the source. Dynamic microphones (an SM58, a Procaster) put out far less signal
than the electret condenser in a headset, and are darker. +8 to +12 dB of
broadband lift is exactly what you would apply to one. **Do not use it with a
headset mic** — it will be loud and harsh.

Practical picks: **Preset 4** if you just want cleanup with minimal colour;
**Preset 6 or 10** for maximum intelligibility on voice calls; **Preset 7** if you
want a fuller "radio" voice; **Dynamic Mic 1** only with an actual dynamic mic.

### A bug in two presets

**[bytes]** Band 4 of Preset 1 and Preset 2 is written as `0000 4000`. Every
other entry in the table follows the pattern `0000 XX40` (positive) or
`0000 XXC0` (negative). `0000 4000` decodes to 5.88 × 10⁻³⁹ — a denormal float,
effectively zero.

It is a byte-swap: the intended value is almost certainly `0000 0040`, i.e.
**+2 dB**. The consequence is small but real — band 4 comes out flat instead of
+2 dB on those two presets. This is upstream's capture, in
`src/g6_cli/g6_spec/recording.py`, and is worth reporting.

**Help box:** An 8-band EQ on the mic path. Presets are voicings, not scenarios —
most cut low rumble and lift presence. "Dynamic Mic 1" adds 8–12 dB and is only
for an actual dynamic microphone, not a headset.

## Mic Boost, Recording Volume, Monitoring

**[bytes]** Three different things that all look like "volume":

- **Mic Boost** — analog preamp gain, in plain integer dB: 0, 10, 20, 30.
  Raises signal *and* noise floor. Use the least that gets you a healthy level.
- **Recording Volume** — the level sent to the computer. Signed 16-bit, 1/256 dB:
  0% is −48 dB, 100% is **+9 dB**. Note it goes positive — the top of this slider
  is amplification, not just "no attenuation".
- **Monitoring Volume** — sidetone. How loudly *you* hear yourself in your own
  headphones. Uses the same dB table as playback volume (0% = −64 dB, 100% = 0 dB).
  **Caveat [Creative]:** on the *hardware* control, sidetone volume is **synced
  with the mic recording volume** — so turning the knob in sidetone mode also
  changes how loud you are to everyone else. Whether the two HID/UAC controls in
  this app stay independent of each other is **[unknown]** and worth testing
  before trusting the sidetone slider as a monitor-only control.

Sidetone is off by default and is toggled **on the device**, not in software
**[Creative]**: hold the volume knob for 2 seconds. The knob's LED goes white →
red, and the side indicator switches from the headphone icon to the mic icon. A
blinking white LED means sidetone is muted.

**Help box:** Mic Boost is analog preamp gain (0–30 dB, boosts noise too).
Recording Volume is the level sent to the computer (−48 dB to +9 dB). Monitoring
is sidetone — how loudly you hear yourself, heard by nobody else.

---

# Mixer, Lighting, System

**Mixer** — per-source mute and volume for Line In, External Mic, S/PDIF In and
What U Hear, split into recording level and monitoring level. All USB Audio Class
controls, so the **whole tab is hidden on macOS**.

**Lighting** — on/off plus a 24-bit RGB colour. **[bytes]** Cosmetic only; enabling
takes three packets (`3A02`/`3A06`/`3A09`) and the colour is plain 0–255 per channel.

**System** — version info and the model file path. On Linux, the audio-interface
claim switch that releases the kernel driver so the volume controls work. macOS
forbids that, which is why the volume rows are absent there.

---

# What this app does *not* expose

Not bugs — never captured in the upstream protocol work:

| Feature | Detail **[Creative]** |
|---|---|
| **Scout Mode** | Button on the G6, or Connect 2 with an assignable hotkey. Enabling it **temporarily disables SBX and the EQ** until you turn it off. |
| **Playback equalizer** | 10 bands, **31 Hz – 16 kHz**, plus Bass and Treble, with presets: Acoustic, Classical, Country, Dance, Flat, Hip Hop, Jazz, Pop, R&B, Rock, Vocal. Unrelated to the mic EQ here. |
| **Output Mode / Configuration** | The `Audio Effects · Direct · SPDIF-Out Direct` radio, and Stereo/5.1/7.1. This app has only two of those as loose booleans. |
| **Headphone virtualization target** | `Headphones` or `Line and Optical Out`. |
| **Speaker type** | Desktop / Bookshelf / Tower / Custom, with a **crossover from 10 Hz to 1000 Hz**. |
| **Voice Morph** | Real-time voice alteration for chat and casting. |
| **Lighting modes** | Only *Solo* (a fixed colour) is exposed here. Connect 2 adds **Pulsate**, **Music Reactive** and **Cycle**, each with speed 10–250. |
| **LED indicator off** | A firmware-dependent switch to turn the volume and Direct Mode LEDs off entirely. |
| **Firmware update** | Windows-only, via Connect 2. |
| **20 BlasterX Experience profiles** | See [Profiles](#profiles--gaming--music--cinema--special). |
| **Gain switch** | Physical switch on the device. Set it for your headphone impedance. |
| **Sample-rate selection** | The OS, not the device. |

Connect 2 itself is **Windows-only** (7/8/10) and refuses to run without the G6
attached over USB. There has never been a Mac equivalent — which is the gap this
project fills.

---

# How this document maps onto the UI

Every control in the GUI carries an **ⓘ** button. Pressing it expands a plain-text
summary of the relevant section below, and pressing **✕** collapses it again. The
wording lives in `src/g6_gui/help.py`, which is the single source shared with
this document — if the two ever disagree, that file and this file should be
changed together.

The ⓘ button stays clickable even when the control it explains is disabled,
which is exactly when the explanation is most wanted (`widgets.set_enabled`
skips anything marked `always_enabled`).

Changes made to the UI as a result of this research:

| Change | Why |
|---|---|
| **Direct Mode is disabled on macOS**, with a warning and an **Open Audio MIDI Setup** button | macOS overrides the device's mode, so the switch was silently inert. See [the macOS section](#macos-audio-midi-setup-is-the-real-control). |
| **SPDIF-Out Direct is left enabled on macOS** | macOS has no equivalent setting for it, so it is unverified rather than known-broken. See [what the clock source does not cover](#what-the-clock-source-does-not-cover). |
| **Help text uses the system label colour** | A fixed grey that looks muted on a white background is close to unreadable in macOS dark mode. |
| **The two are now mutually exclusive** — turning one on turns the other off | They are two positions of one three-way Output Mode on the device, so both-on was a state the hardware cannot hold. |
| **Smart Volume special moved directly under Smart Volume** | It overrides the Smart Volume slider, so stranding it at the bottom of the tab hid the relationship. |
| **Changing "Editing profile" no longer writes to the device** | It was silently performing the profile switch. See [the bug](#bug-changing-editing-profile-already-switches-the-profile). |
| **A note under Decoder mode** saying it only affects Dolby over optical | The single most confusing "this does nothing" in the app. |

Still deliberately *not* changed, and why:

- **The Output Mode radio** is still modelled as two booleans rather than one
  three-way selector per output. Mutual exclusivity papers over the worst of it,
  but the honest fix is a redesign of that section, and it would also want the
  `Audio Effects` state the protocol capture never covered.
- **"Loud" has not been renamed to "Auto"**, because that is still
  **[inferred]** rather than confirmed.
- **The profile model** still has four local slots with no Creative preset
  content.

---

# Open questions

Most of the original list is now answered — by Creative's own G6 FAQ, by the G5
knowledge-base article, and by reproducing the profile bug against the fake API.
What is left:

### 0. Why does recording Smart Volume do nothing? **[unknown]**

See [the listening tests](#what-actually-works--listening-tests). The most
informative next step is trying it on Windows with Creative's own software: if it
is inert there too, it is the device or the mic; if it works there, it is
something about this app's or macOS's handling.

### 1. Are sidetone and mic recording volume linked in software too? **[unknown]**

Creative documents the *hardware* sidetone control as sharing its level with mic
recording volume. This app exposes them as two independent controls. If they are
linked in the device, turning up your monitor level also makes you louder to
everyone else — which would make the sidetone slider actively misleading.

Test: set monitoring to 100% and recording to 10%, then have someone confirm your
level; repeat with monitoring at 0%.

### 2. Does this app's Direct Mode packet do anything on Windows? **[unknown]**

On macOS it is provably overridden — confirmed by ear. On Windows, where the OS
does not assert the mode, the same packet may well work. Nobody has tested this
project there. Note that even Creative's own Windows instructions for reaching
384 kHz never mention the Direct Mode toggle, only the OS format dialog.

### 2b. Are the SBX sliders continuous, or quantised to Creative's detents? **[unknown]**

Connect 2 gives Surround three labelled positions and Dialog+ four, while the
wire format is a float from 0.0 to 1.0. Either the firmware interpolates — in
which case this app offers finer control than Creative's own software — or it
snaps to the nearest detent and most slider positions are wasted. Audible test:
sweep Surround slowly and listen for steps.

### 2c. Is "Loud" really "Auto"? **[inferred]**

Value 1.0 is labelled *Loud* here and *Auto* in Connect 2. Almost certainly the
same mode under two names, but worth confirming before renaming the UI.

### 3. Decoder mode with a real Dolby source **[unknown]**

Needs a Dolby Digital bitstream on the optical input — a PS4/Xbox set to
bitstream output, per Creative's documented wiring. Then Full vs Night should be
obvious on a film with wide dynamics.

### 4. SPDIF-Out Direct on a G6 **[unknown]**

Two separate unknowns here.

**Does it work on macOS at all?** Direct Mode provably does not, but that
argument does not transfer — see
[what the clock source does not cover](#what-the-clock-source-does-not-cover).
The switch is deliberately left enabled so this can be answered.

**Does the G5 behaviour table hold for a G6?** The no-effects rule is confirmed
for the G6, but "optical goes silent in Direct Mode" and "volume no longer
controllable" have not been verified on one.

Both need something plugged into the optical output — a receiver, a soundbar, or
anything with a TOSLINK input.

### 5. The band-4 preset bug **[bytes]**

Already certain from the bytes; confirming by ear or measurement would let it be
reported upstream with evidence.

### 6. What a factory reset actually restores **[unknown]**

Worth doing once deliberately, because it is the only way to make the device and
`g6.json`'s assumed defaults genuinely agree. Costs you your lighting colour and
every saved setting.

---

# Documents still wanted

Creative's knowledge base geo-redirects and renders via JavaScript, so it cannot
be fetched from here — but it prints to PDF fine. These would each close a gap:

SID 200074, 200065 and 200066 have all been supplied and are now in
`docs/pdfs/`. Still outstanding:

| Wanted | Why |
|---|---|
| A screenshot of **Connect 2's Voice → Clarity page** | Would settle whether Creative's "Voice Enhancer" is what this app calls *Mic Equalizer*, and show the eight band frequencies |
| The **settings behind any one BlasterX Experience profile** | Would let the four empty slots be filled with Creative's real voicings — even one (Gaming, say) would establish the format |
| Anything on the **playback filters** with actual curves | Creative's own page says only "4 options to control steepness" |

Reddit is the other gap: it is blocked by policy in the built-in browser *and*
Anthropic's crawler does not index it, so pasting threads in — as you have been
doing — is the only route.

# Sources

- [Creative — Acoustic Engine](https://us.creative.com/technology/acousticengine/) — Surround, Crystalizer, Bass, Smart Volume, Dialog Plus
- [Creative — Sound Blaster technologies](https://us.creative.com/soundblaster/technology/) — Smart Volume Night mode, Scout Mode, CrystalVoice
- [Creative — CrystalVoice](https://us.creative.com/technology/crystalvoice/) — Noise Reduction, Acoustic Echo Cancellation, mic Smart Volume
- **Creative KB Solution ID 200071 — *Sound BlasterX G6: Frequently Asked Questions*** — the single best source here. G5-vs-G6 table, Direct Mode on macOS (Q19), mic recording in Direct Mode (Q42), optical + SBX (Q14), sidetone (Q12), factory reset (Q17), Mac feature set (Q18). Supplied as PDF.
- **Creative KB Solution ID 128701 — *Sound BlasterX G5: Direct Mode versus SPDIF-Out Direct*** — the mutual-exclusivity rule and the behaviour table. Supplied as PDF.
- **Creative KB Solution ID 200074 — *Sound BlasterX G6: Sound Blaster Connect 2 Software*** — the richest source. The `Audio Effects · Direct · SPDIF-Out Direct` radio, the Acoustic Engine knob ranges, the Dolby knob, the 20 profiles, the 10-band EQ, lighting modes, and everything this project does not expose. Supplied as PDF (`docs/pdfs/200074.pdf`).
- **Creative KB Solution ID 200065 — *Sound BlasterX G6: Technical Specifications*** — SB-Axx1 DSP, 16–600 Ω, Dolby decoding via Optical In, per-mode sample rates. Supplied as PDF.
- **Creative KB Solution ID 200066 — *Enabling 32bit 384kHz Playback in Windows*** — the Windows equivalent of the macOS clock-source dance. Supplied as PDF.
- [Creative — Sound BlasterX G6 product page](https://us.creative.com/p/sound-blaster/sound-blasterx-g6-usb-c) — 32-bit/384 kHz, 1 Ω output impedance, optical I/O
- [Audio Science Review — G6 review and measurements](https://www.audiosciencereview.com/forum/index.php?threads/review-and-measurements-of-sound-blasterx-g6.7016/) — CS43131 DAC, 85 mW into 300 Ω; [page 2](https://www.audiosciencereview.com/forum/index.php?threads/review-and-measurements-of-sound-blasterx-g6.7016/page-2#post-158688) for the Direct Mode null result
- [Cirrus Logic CS43131](https://www.cirrus.com/products/cs43131) and [datasheet](https://statics.cirrus.com/pubs/proDatasheet/CS43131_DS1155F2.pdf) — the selectable interpolation filters
- [r/SoundBlasterOfficial — Direct mode vs default on SBX G6](https://www.reddit.com/r/SoundBlasterOfficial/comments/m1paan/direct_mode_vs_default_on_sbx_g6/) — what Direct Mode disables; mic and line-in behaviour
- [guru3D — Creative G6 DAC/amp thread](https://forums.guru3d.com/threads/purchased-creative-g6-external-dac-amp.428000/page-4) — filter listening impressions, APU bypass
- [r/SoundBlasterOfficial — Sound BlasterX G6, direct mode question](https://www.reddit.com/r/SoundBlasterOfficial/comments/1556zzq/sound_blasterx_g6_direct_mode_question/) — host-side effects still pass through in Direct Mode; no mic on the G6 in Direct Mode
- [mobileaudiophile — Creative DAC review](https://mobileaudiophile.com/reviews/creative-soundblaster-g8-dac-the-bridge-between-devices/) — corroborates the 48 kHz DSP-mode ceiling on macOS on a sibling Creative DAC
- `toga_cocoa/widgets/switch.py` in `venv/` — the `set_value` → `on_change` behaviour behind the profile bug
- `src/g6_cli/g6_spec/` in this repo — every **[bytes]** claim
