# Running the CLI on macOS

For using `soundblaster-x-g6-cli` from the terminal on macOS, without the GUI.

If you just want a double-clickable app, ignore this file: download the `.dmg`
from the releases page, or see [gui.md](gui.md). The app bundles everything and
needs none of the setup below.

## What you need

| | Why |
|---|---|
| macOS, Apple Silicon or Intel | both have prebuilt wheels |
| Python 3.12 | the project requires `>=3.12` |
| `libusb` | `pyusb` loads it at runtime to reach the device |

You do **not** need Homebrew's `hidapi`, `cython`, or the `CFLAGS`/`LDFLAGS`
exports that older instructions call for. As of `hidapi` 0.15.0 the Python
package ships prebuilt wheels for macOS (both architectures) with libhidapi
statically linked, so nothing is compiled during install.

## Install

```bash
brew install python@3.12 libusb

python3.12 -m venv ~/g6
source ~/g6/bin/activate
pip install soundblaster-x-g6-cli
```

Check it:

```bash
soundblaster-x-g6-cli --version
```

The command lives in the virtualenv, so either keep it activated or call it by
its full path (`~/g6/bin/soundblaster-x-g6-cli`) — handy for shell aliases and
keyboard shortcuts.

## What works on macOS, and what does not

The G6 exposes two USB interfaces, and only one of them is reachable here.

**Works — the HID interface:**

- output switching (speakers / headphones)
- Direct Mode and SPDIF-Out Direct Mode
- playback filter
- decoder mode
- lighting
- microphone boost and the Voice Clarity features
- all SBX effects and profiles

**Does not work — the AudioControl interface:**

- playback volume and mute
- the entire mixer (monitoring and recording levels)
- microphone recording and monitoring volumes
- speaker/headphone 5.1 and 7.1 modes
- `--claim-and-release` and `--reload-audio-services`

Those features require detaching the kernel audio driver from the device first,
which is what `--claim-and-release` does on Linux. macOS does not allow libusb to
take that interface away from its own USB audio class driver, so they cannot
work. The commands exist, but will not do what you want.

Use macOS's own volume controls for playback volume.

## Examples

```bash
# switch output
soundblaster-x-g6-cli --set-output Headphones
soundblaster-x-g6-cli --toggle-output

# playback
soundblaster-x-g6-cli --playback-direct-mode Enabled
soundblaster-x-g6-cli --playback-filter SLOW_ROLL_OFF_LINEAR_PHASE
soundblaster-x-g6-cli --decoder-mode Night

# lighting
soundblaster-x-g6-cli --lighting-rgb 255 0 0
soundblaster-x-g6-cli --lighting-disable

# microphone
soundblaster-x-g6-cli --recording-mic-boost-db 20
soundblaster-x-g6-cli --recording-voice-clarity-noise-reduction Enabled

# SBX: switch the active profile (replays that profile's stored values)
soundblaster-x-g6-cli --sbx-profile-switch Music

# SBX: edit a profile's effects
soundblaster-x-g6-cli --sbx-profile Music --sbx-bass Enabled --sbx-bass-value 60
```

`--help` lists every option.

Before relying on `--sbx-profile` versus `--sbx-profile-switch`, read
[device-state.md](device-state.md) — editing a profile that is not the active one
behaves in a way that surprises people.

## Things that trip people up

**The device must be plugged in — even for `--dry-run`.** The API looks the
device up when it starts, so a dry run still fails with *"No SoundBlaster X G6
device could be found"* if nothing is connected.

**At least one real option is required.** Running with only `--dry-run`,
`--debug` or `--sbx-profile-print` fails with *"No meaningful argument has been
specified!"*. Pair it with something:

```bash
soundblaster-x-g6-cli --dry-run --sbx-profile-print --set-output Speakers
```

**Your settings live in the device, not in a config file.** Nothing is applied at
startup, and `~/.soundblaster-x-g6/g6.json` is a record of what was last sent,
not a configuration. See [device-state.md](device-state.md).

## Troubleshooting

| Symptom | Cause |
|---|---|
| `No SoundBlaster X G6 device could be found by pyusb` | Not connected, or `libusb` is missing — `brew install libusb`. |
| `No backend available` from pyusb | `libusb` is not installed, or not on a path Homebrew set up. |
| `No meaningful argument has been specified!` | See above — add a real option. |
| `... but the required AudioControl interface does not seem to be available` | Expected on macOS for the `[Audio]` features; they cannot work here. |
| The CLI succeeds but nothing changes | Check you are not passing `--dry-run`. |

## If a wheel is not available for your Python

The simple install works because prebuilt wheels exist for `hidapi` on Python
3.8–3.14. On a Python version or platform without one, pip falls back to
building from source, and then you do need the old recipe:

```bash
brew install cython hidapi
export CFLAGS="-I$(brew --prefix)/include"
export LDFLAGS="-L$(brew --prefix)/lib"
pip install Cython setuptools wheel
pip install soundblaster-x-g6-cli
```

Sticking to Python 3.12 avoids this.
