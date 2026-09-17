# SoundBlaster X G6 — Desktop GUI

A cross-platform desktop front-end for `soundblaster-x-g6-cli`, exposing every
CLI option as a native control. It runs on **Linux** and **macOS**.

The GUI is a client of the existing `g6_cli.g6_api.G6Api`; it does not
reimplement any part of the USB protocol, and it does not modify `g6_cli`.

## Install

```bash
pip install -e '.[gui]'
```

On **macOS**, follow the project's existing setup first (Homebrew Python 3.12,
`libusb`, `hidapi`, a virtualenv), then install the `gui` extra above.

On **Linux**, the GUI toolkit additionally needs system GTK — `pip` alone is not
enough:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0     # Debian / Ubuntu
sudo dnf install python3-gobject gtk3          # Fedora
sudo pacman -S python-gobject gtk3             # Arch
```

## Running the development version

This repository already has a `venv/` with the project installed **editable**,
so your edits to `src/` take effect immediately — no reinstall, no build step:

```bash
./venv/bin/soundblaster-x-g6-gui
```

Starting from scratch, or after the venv is gone:

```bash
python3.12 -m venv venv && ./venv/bin/pip install -e '.[gui]'
```

Check which version you are actually running — the development GUI reports its
own version, separate from the bundled CLI's:

```bash
./venv/bin/soundblaster-x-g6-gui --version
```

A few things worth knowing:

- **Re-run `pip install -e .` only after adding a new package directory** under
  `src/`. Editing existing files needs nothing.
- **Run the test suite with `./venv/bin/pytest tests/g6_gui`.** Do not run
  `tests/g6_cli`: that suite fails on Python 3.12 for reasons unrelated to this
  work (argparse changed its error wording upstream).
- The installed `.app` in `/Applications` is a *different* copy with its own
  bundled Python. Changing `src/` does not affect it — rebuild with
  `packaging/build-macos.sh` for that.
- To see a page without any hardware, build it against the recording double in
  `tests/g6_gui/fake_api.py`; that is how the screenshots in this repository
  were produced.

## Run (installed)

```bash
soundblaster-x-g6-gui
```

Flags mirror the CLI's general options, read once at startup as constructor
arguments of `G6Api`:

| Flag | Effect |
|---|---|
| `--dry-run` | Simulate device communication; send nothing to the G6 |
| `--debug` | Print device communication to the console |
| `--no-persist` | Do not read or write `~/.soundblaster-x-g6/g6.json` |
| `--version` | Print the version and exit |

**The G6 must be plugged in, even with `--dry-run`.** `G6Api()` raises
`IOError` at construction when no device is attached — `--dry-run` suppresses
*sending*, not *opening*. The GUI opens on a "Connect your Sound Blaster X G6"
screen with a Retry button instead of starting, and returns to it if the
device disappears while running.

## Tabs

macOS Audio is listed first — it is the actual Direct Mode control on macOS,
the most consequential setting on the device, so it leads rather than being
buried after Playback:

| Tab | Contents |
|---|---|
| **macOS Audio** | *macOS only.* Clock Source (DSP Clock / Stereo Direct) and Format, read and set directly via Core Audio, plus a read-only Output Volume/Channels display — see below |
| **Playback** | Output (Speakers/Headphones), Direct Mode, SPDIF-Out Direct Mode, Filter (5 variants, including a hidden Non-Over-Sampling mode), Decoder mode, *and on Linux* mute, volume + channels, speaker/headphone Stereo·5.1·7.1 |
| **Mixer** | *Linux only.* Playback mute, plus monitoring and recording mute/volume/channels for Line In, External Mic, SPDIF In and What U Hear |
| **Recording** | Mic boost, Voice Clarity (Noise Reduction + level, Acoustic Echo Cancellation, Smart Volume, Mic Equalizer + preset), *and on Linux* mute and mic recording/monitoring volumes |
| **SBX** | Profile editor and the five effects — see below |
| **Lighting** | Enable, R/G/B, colour preview |
| **System** | Version and state-file path, *and on Linux* Claim/Release audio interface and Reload audio services |

## What the settings actually do

Every control has an **ⓘ** button next to it. Press it and a plain-language
explanation expands underneath; press **✕** to collapse it. The button stays
usable even when the control itself is disabled, which is when you most want to
know why.

For the long version — every option, what it changes, when it does nothing, and
how confident we are in each claim — see
[settings-reference.md](settings-reference.md). The help text in the app is a
condensed version of that document, and both are generated from the same source
(`src/g6_gui/help.py`).

Some of that document's newer material comes from an independent firmware
reverse-engineering project rather than from Creative's own documentation or
listening tests — the mechanism behind Direct Mode, the hidden fifth DAC
filter, the full-scale volume warning, and what virtual 7.1 actually does
inside the device. That project is credited and digested for users (not
reverse engineers) in [firmware-findings.md](firmware-findings.md). Linux
users specifically should see [linux.md](linux.md) for what this fork adds
there and where it sits among other G6 Linux projects.

## Direct Mode on macOS — the macOS Audio tab

Direct Mode cannot be set by this app's Playback tab on macOS, so its switch is
**disabled** there. macOS continuously asserts the device's mode through Core
Audio and overwrites whatever the G6 was told — Creative documents this
themselves.

**SPDIF-Out Direct on Playback is left enabled.** macOS's Clock Source has only
two positions and neither corresponds to it, so it is *unverified* rather than
known-broken; disabling it would have asserted a limitation nobody has shown and
removed the only way to test it.

The real control lives in a dedicated **macOS Audio** tab, which reads and sets
the G6's Clock Source and Format directly through Core Audio — the same
mechanism Apple's own Audio MIDI Setup uses, so you no longer need to leave
this app to switch modes:

| Clock Source | What you get |
|---|---|
| **DSP Clock** | All effects available (SBX, filters), capped at 32-bit/48 kHz |
| **Stereo Direct** | Direct Mode — bit-perfect up to 32-bit/384 kHz, no SBX, **no microphone** |

Switching back from 384 kHz to DSP Clock is handled automatically: the tab
drops the format to something DSP Clock supports *before* changing the clock
source, so it cannot wedge the device the way doing this by hand can (DSP Clock
cannot do 384 kHz, and Core Audio does not renegotiate the format for you).

**Recording and SBX disable themselves automatically** whenever this tab
confirms Stereo Direct is active — both drive the G6's DSP over its own USB
protocol, which Stereo Direct bypasses entirely, so those controls would do
nothing right now. They stay enabled if the clock source can't be positively
identified, rather than guessing.

**[TESTED]** *(2026-09-16, real G6)*: the tab correctly identifies the device
(Core Audio calls it `Sound BlasterX G6`, though the tab does not rely on
knowing that — it identifies the device by its Clock Source shape instead),
reads and switches between DSP Clock and Stereo Direct, and picks up changes
made directly in Apple's Audio MIDI Setup too. If the tab ever reports it
could not find the G6, try **Audio MIDI Setup** directly
(`/Applications/Utilities/`) as a fallback, and see
[docs/settings-reference.md](settings-reference.md#macos-audio-tab)
for what that would mean.

One quirk worth knowing about, not a bug: the Format list includes an
`(Exclusive)` variant of several entries — Core Audio's exclusive/hog mode,
which bypasses macOS's audio mixer entirely. Also, a Clock Source switch
usually completes in well under a second but has occasionally taken longer on
real hardware for reasons not yet identified; the tab waits rather than
timing out prematurely.

The tab also shows the G6's current **Output Volume** and **Output
Channels**, read from Core Audio. Both are read-only by design — this app
does not move your system volume for you — but the volume row exists because
of a real problem: **[INFERRED]** (firmware disassembly, credited in
[firmware-findings.md](firmware-findings.md)) the G6 distorts at 100% volume,
a hardware limit never fixed across six years of releases. A warning appears
whenever the reading hits 100%; dropping a couple of steps (around 90%)
clears it. See
[settings-reference.md's full-scale volume section](settings-reference.md#full-scale-volume--the-g6-distorts-at-100)
for the evidence.

**[TESTED]** *(2026-09-17, real G6)*: the volume shown here is the G6's
**own hardware volume control** — exposed **per-channel only** (Core Audio's
`'volm'` on elements 1/2, no master `'vmvc'`) — not a host-side attenuation
macOS applies on top. So moving your Mac's volume for the G6 really does move
the same control Windows or Connect 2 would. What is *not* known is where
inside the device that control sits (digital, before the DAC, or analog,
after it) — see
[settings-reference.md's volume-mechanism section](settings-reference.md#volume-forwards-to-the-device-not-the-host)
for what that would change and why "keep it a few steps below 100%" is good
advice either way.

**[TESTED]** *(2026-09-17, real G6)*: Output Channels reads **2**, measured
rather than assumed — Core Audio's full available-format list (8 entries,
`44.1`/`48 kHz` × `24`/`32`-bit × ordinary/Exclusive) contains zero
non-stereo formats. So virtual 7.1 is genuinely unavailable on macOS.
Switching the G6 to 7.1 would need the USB AudioControl interface, which
macOS does not let any app claim — see
[settings-reference.md's Virtual 7.1 section](settings-reference.md#virtual-71)
for the full mechanism.

## Why macOS shows fewer controls

Every feature marked `[Audio]` in the CLI reaches the G6 through its USB
**AudioControl** interface. Using it requires detaching the kernel audio driver
first — that is what `--claim-and-release` does. macOS does not permit libusb to
take that interface away from its own USB audio class driver, so those features
cannot work there. Rather than show controls that silently fail, the GUI hides
them on macOS.

macOS therefore gets everything on the `[HID]` interface: output switching,
Direct Mode, filter, decoder, lighting, mic boost, Voice Clarity, and all of SBX.

On Linux those controls exist but stay **disabled** until you turn on *Claim
audio interface* in the System tab. Be aware of what claiming does: it detaches
the kernel driver, so **your system has no audio output until you release it
again**. The GUI releases the interface automatically when you quit.

Linux is where this app is most capable — the Mixer tab, playback volume and
mute, and real speaker/headphone Stereo·5.1·7.1 switching only exist there.
See [linux.md](linux.md) for what that actually gets you, how this fork
compares to the other G6 controllers already on Linux, and an honest note
about which of the 7.1-related flags are confirmed to do anything.

## Where your settings actually live

In the G6 itself, not in a file. Nothing is applied when the app starts, and
`~/.soundblaster-x-g6/g6.json` is a record of what was last sent — which is why
the GUI presents those values as last known state rather than claiming to have
read the device. **[TESTED/INFERRED]** the control protocol itself does
support reading a value back (decoded from this repo's own USB captures), but
a readback feature was designed and then deliberately not built — a closed
decision, not a pending item — see [device-state.md](device-state.md) for the
detail and the reasoning.

That also means the displayed values can drift from reality if the settings were
changed elsewhere (another machine, another OS, Creative's own software). If the
UI disagrees with what you hear, the device is right.

Full detail, including why this is how it works:
[device-state.md](device-state.md).

## SBX: editing profile vs active profile

This is the one part of the device that behaves counter-intuitively, so the GUI
makes it explicit.

The G6 holds exactly **one** live SBX state. `sbx_toggle` and `sbx_slider` send
identical data to the device no matter which profile is named — the profile name
only decides which entry is written in `~/.soundblaster-x-g6/g6.json`. Switching
profiles replays that profile's ten stored values to the device.

So the SBX tab has two distinct ideas:

- **Editing profile** — the profile your changes are recorded against.
- **Active profile** — what the device is currently playing.

When the two differ, the banner warns you that your change is audible now, but
is saved under the profile you are editing and will be replaced the next time you
switch profiles. Use **Switch to this profile** to make the edited profile active.

## Licensing

The GUI is built with **Toga** (BeeWare). Toga, Travertino and Rubicon-ObjC are
all BSD-3-Clause, which is compatible with this project's **GPL-2.0-only**
licence.

Qt bindings were deliberately not used. PySide6 is LGPLv3 and PyQt6 is GPLv3,
and both are *incompatible* with GPL-2.0-only: they add terms that GPLv2 does not
permit adding to a combined work, which blocks distribution in any form — source
or binary alike. Shipping source instead of a binary does not cure it.

Note that because this application derives from GPLv2 code, any binary you
distribute must be accompanied by an offer of complete corresponding source.
