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

## Run

```bash
soundblaster-x-g6-gui
```

Flags mirror the CLI's general options. They are read once at startup, because
they are constructor arguments of `G6Api`:

| Flag | Effect |
|---|---|
| `--dry-run` | Simulate device communication; send nothing to the G6 |
| `--debug` | Print device communication to the console |
| `--no-persist` | Do not read or write `~/.soundblaster-x-g6/g6.json` |
| `--version` | Print the version and exit |

### The device must be attached

`G6Api` raises `IOError` at construction when no G6 is found — **including under
`--dry-run`**. The GUI therefore opens on a "Connect your Sound Blaster X G6"
screen with a Retry button, and returns to it if the device disappears while
running.

## Tabs

| Tab | Contents |
|---|---|
| **Playback** | Output (Speakers/Headphones), Direct Mode, SPDIF-Out Direct Mode, Filter, Decoder mode, *and on Linux* mute, volume + channels, speaker/headphone Stereo·5.1·7.1 |
| **Mixer** | *Linux only.* Playback mute, plus monitoring and recording mute/volume/channels for Line In, External Mic, SPDIF In and What U Hear |
| **Recording** | Mic boost, Voice Clarity (Noise Reduction + level, Acoustic Echo Cancellation, Smart Volume, Mic Equalizer + preset), *and on Linux* mute and mic recording/monitoring volumes |
| **SBX** | Profile editor and the five effects — see below |
| **Lighting** | Enable, R/G/B, colour preview |
| **System** | Version and state-file path, *and on Linux* Claim/Release audio interface and Reload audio services |

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

## Where your settings actually live

In the G6 itself, not in a file. Nothing is applied when the app starts, and
`~/.soundblaster-x-g6/g6.json` is a record of what was last sent — which is why
the GUI presents those values as last known state rather than claiming to have
read the device. The device cannot be read back at all.

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
