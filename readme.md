# SoundBlaster X G6 CLI

This project uses [hidapi](https://github.com/trezor/cython-hidapi) and,
transitively, [libusb](https://github.com/libusb/libusb) to control the
[SoundBlaster X G6](https://de.creative.com/p/sound-blaster/sound-blasterx-g6)
from the command line. It started as a Linux CLI; this fork adds a desktop GUI
(Linux and macOS) and macOS packaging on top of it.

## Important Disclaimer

I developed this CLI to the best of my belief, and I use it myself to control my
G6, and it works fine for me. Sending faulty data to a USB device can in
principle damage or brick it.

**USE THIS CLI AT YOUR OWN RISK.** I am not responsible for any damage to your
system or your device.

## Desktop GUI

A cross-platform desktop GUI exposing every CLI option as a native control.

**From a clone, for development** (editable install — edits under `src/` take
effect on next launch, no rebuild):

```bash
git clone https://github.com/zipleen/soundblaster-x-g6-cli.git
cd soundblaster-x-g6-cli
git checkout main-gui
python3.12 -m venv venv
./venv/bin/pip install -e '.[gui]'
./venv/bin/soundblaster-x-g6-gui            # add --version to confirm the build
./venv/bin/pytest tests/g6_gui              # test suite
```

The G6 must be plugged in even with `--dry-run` — the API opens the device on
construction, and `--dry-run` only suppresses sending. See
[docs/gui.md](docs/gui.md#running-the-development-version) for more.

**Into your own Python** (puts `soundblaster-x-g6-gui` on your `PATH`; run from
the repo root):

```bash
pip install -e '.[gui]'
soundblaster-x-g6-gui
```

**Standalone macOS app** — a self-contained `.app`/`.dmg` needing neither
Python nor Homebrew on the target machine:

```bash
packaging/build-macos.sh
```

Open `dist/Sound Blaster X G6-<version>.dmg`, drag the app to Applications, and
double-click it. Full build/signing/notarisation detail in
[packaging/README.md](packaging/README.md) and
[packaging/NOTARIZING.md](packaging/NOTARIZING.md). Pushes to `main-gui` build
the app in CI and publish a GitHub Release when `pyproject.toml`'s `version`
hasn't been released yet.

Linux additionally needs system GTK (`python3-gi`, `gir1.2-gtk-3.0` on
Debian/Ubuntu — see [docs/gui.md](docs/gui.md#install) for Fedora/Arch). The
GUI is built with Toga (BSD-3-Clause), compatible with this project's
GPL-2.0-only licence; Qt bindings (PySide6/PyQt) are not, and were deliberately
avoided.

Running the CLI on macOS from a terminal instead of using the GUI? See
[docs/macos-cli.md](docs/macos-cli.md).

### Tabs

| Tab | Contents |
|---|---|
| macOS Audio | *macOS only.* Clock Source / Format via Core Audio, read-only Output Volume/Channels |
| Playback | Output, Direct Mode, SPDIF-Out Direct Mode, Filter (5 variants), Decoder mode; *Linux also:* mute, volume, speaker/headphone Stereo·5.1·7.1 |
| Mixer | *Linux only.* Mute/volume/channels for Line In, External Mic, SPDIF In, What U Hear |
| Recording | Mic boost, Voice Clarity (NR, AEC, Smart Volume, Mic EQ+preset); *Linux also:* mute, mic volumes |
| SBX | Profile editor and the five effects |
| Lighting | Enable, R/G/B, colour preview |
| System | Version, state-file path; *Linux also:* Claim/Release, Reload audio |

Full guide, including per-setting help text and SBX's editing-profile vs
active-profile split: [docs/gui.md](docs/gui.md).

### Why macOS and Linux differ

Everything marked `[Audio]` in the CLI goes over the G6's USB **AudioControl**
interface, which requires detaching the kernel audio driver first
(`--claim-and-release`). macOS does not allow that against its own USB Audio
class driver, so those controls (the Mixer tab, playback/recording volume and
mute, real 5.1/7.1 switching) exist only on Linux. Direct Mode is HID-based and
works on both, but macOS itself continuously re-asserts the device's clock
mode over Core Audio, overriding this app's Playback-tab switch — so on macOS,
Direct Mode is instead controlled directly from the **macOS Audio** tab.

See [docs/linux.md](docs/linux.md) for what this fork adds on Linux beyond
upstream and how it compares to other Linux G6 controllers, and
[docs/settings-reference.md](docs/settings-reference.md) for what every
setting does, with the evidence for each claim (including a warning about
measurable distortion at 100% volume, and confirmation that macOS's volume
slider moves the G6's own hardware volume control). Independent firmware
reverse-engineering that informs several of those findings is credited and
digested in [docs/firmware-findings.md](docs/firmware-findings.md). How
settings are stored (and why `~/.soundblaster-x-g6/g6.json` is a record, not a
config file) is in [docs/device-state.md](docs/device-state.md).

### Branches in this fork

| Branch | Purpose |
|---|---|
| `main` | A clean mirror of upstream (`nils-skowasch/soundblaster-x-g6-cli`), always fast-forwardable, so a PR from this fork stays reviewable. |
| `main-gui` | This distribution: upstream plus the GUI and macOS packaging. Releases are built from here. |

## Firmware version

This software is tested with a G6 having the **Firmware version:**
`2.1.250903.1324`. Other versions may differ at the USB level. You can update
firmware with
[SoundBlaster Command](https://support.creative.com/Products/ProductDetails.aspx?prodID=21383&prodName=Sound%20Blaster)
on Windows, e.g. via a [QEMU/KVM VM](https://virt-manager.org/) with USB
Redirection.

## System requirements (Linux)

**udev rule**, so the app can access the device without root:

```shell
sudo tee /etc/udev/rules.d/50-soundblaster-x-g6.rules > /dev/null << 'EOF'
SUBSYSTEM=="usb", ATTRS{idVendor}=="041e", ATTRS{idProduct}=="3256", TAG+="uaccess"
EOF
sudo udevadm control --reload-rules && sudo udevadm trigger
```

**`/etc/asound.conf`**, so ALSA always finds the G6 by name rather than by an
index the kernel can reassign:

```text
pcm.!default { type hw; card G6 }
ctl.!default { type hw; card G6 }
```

**`libusb1`**:

```shell
sudo apt-get -y install libusb-1.0-0-dev libusb-1.0-0
```

## Installation (CLI)

### Via pipx (recommended)

```shell
pipx install soundblaster-x-g6-cli
```

Installs into `~/.local/share/pipx/venvs/soundblaster-x-g6-cli/`; add
`~/.local/share/pipx/venvs/soundblaster-x-g6-cli/bin/` to `$PATH` if the
`soundblaster-x-g6-cli` command isn't found. You still need the udev rule
above.

### From source

```shell
git clone git@github.com:nils-skowasch/soundblaster-x-g6-cli.git ~/soundblaster-x-g6-cli
cd ~/soundblaster-x-g6-cli
sudo apt-get install python3.12          # tested with Python 3.12, LinuxMint 22.1
chmod 0544 shell/*                       # ready-to-use toggle/set shell scripts
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## CLI usage

Run `soundblaster-x-g6-cli --help` for the full, current option list (general
flags, Playback/Decoder/Lighting over HID, Mixer/Playback/Recording over
Audio, and the full SBX effect set). What each option actually does, including
options Creative's own app doesn't expose, is documented in
[docs/settings-reference.md](docs/settings-reference.md).

## Development

Needs the **System requirements** above installed first.

```shell
python -m build              # builds dist/
python -m twine check dist/* # verifies the build
```

### Testing across Python versions (pyenv + tox)

```shell
curl -fsSL https://pyenv.run | bash   # then add pyenv to your shell, see its own docs
sudo apt install -y build-essential libssl-dev zlib1g-dev libbz2-dev \
    libreadline-dev libsqlite3-dev curl git libncursesw5-dev xz-utils tk-dev \
    libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
pyenv install 3.12.3 && pyenv rehash
tox              # all environments in pyproject.toml
tox -e py312     # a single environment
```

### Deploying (maintainers)

```text
# ~/.pypirc
[testpypi]
  username = __token__
  password = <api-token>
```

```shell
python -m twine upload --repository testpypi dist/*

# verify from a clean install:
pipx install --pip-args="--index-url https://test.pypi.org/simple --extra-index-url https://pypi.org/simple" soundblaster-x-g6-cli
```

# SoundBlaster X G6 USB specification

The USB specification was reverse-engineered by recording USB communication
with [Wireshark USBPCAP](https://wiki.wireshark.org/CaptureSetup/USB) and
reading the HEX codes sent from
[SoundBlaster Command](https://support.creative.com/Products/ProductDetails.aspx?prodID=21383&prodName=Sound%20Blaster)
(app `3.4.98.0`, driver `1.16.4.26`) to the device:
[usb-spec.md](https://github.com/nils-skowasch/soundblaster-x-g6-cli/blob/main/doc/usb-spec.md).

Basic information about the USB protocol:
[usb-protocol.md](https://github.com/nils-skowasch/soundblaster-x-g6-cli/blob/main/doc/usb-protocol.md).
