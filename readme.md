# SoundBlaster X G6 CLI

This project makes use of the [hidapi](https://github.com/trezor/cython-hidapi) library and thus transitively from
[libusb](https://github.com/libusb/libusb) to provide a CLI to control
the [SoundBlaster X G6](https://de.creative.com/p/sound-blaster/sound-blasterx-g6) device from command line. This
empowers the people to control the G6 in Linux.

## Important Disclaimer

I developed this CLI to the best of my belief, and I use it myself to control my G6, and it works fine for me.
I read pretty often that you are able to damage or brick a USB device if you send faulty data to it.

That's why I want to point out, that you **USE THIS CLI AT YOUR OWN RISK**! I am not responsible for any damage to your
system or your device!

## Desktop GUI

A cross-platform desktop GUI (Linux and macOS) is available alongside the CLI,
exposing every CLI option as a native control:

```bash
pip install -e '.[gui]'
soundblaster-x-g6-gui
```

On Linux it additionally needs system GTK (`python3-gi`, `gir1.2-gtk-3.0` on
Debian/Ubuntu). macOS shows fewer controls than Linux, because the features that
go through the USB AudioControl interface require detaching the kernel audio
driver, which macOS does not permit.

The GUI is built with Toga (BSD-3-Clause), which is compatible with this
project's GPL-2.0-only licence; Qt bindings are not, and were deliberately
avoided.

### Standalone macOS app

To build a self-contained `.app` and `.dmg` that need neither Python nor
Homebrew on the target machine:

```bash
packaging/build-macos.sh
```

Open the resulting `dist/Sound Blaster X G6-<version>.dmg`, drag the app into
Applications, and double-click it. See [packaging/README.md](packaging/README.md)
for build requirements, the self-containment checks, and the Gatekeeper caveat
for downloaded copies. To produce a build that opens with no Gatekeeper warning,
see [packaging/NOTARIZING.md](packaging/NOTARIZING.md).

Pushes to `main` build the app in CI and publish a GitHub Release whenever the
`version` in `pyproject.toml` has not been released yet.

See [docs/gui.md](docs/gui.md) for the full guide, including the SBX
editing-profile vs active-profile semantics.


## Firmware version

This software is tested with a G6 having the **Firmware version:** `2.1.250903.1324`.

Make sure that you have the same version, since I do not know whether the USB specification may differ between the
versions. You are able to update your Firmware with
[SoundBlaster Command](https://support.creative.com/Products/ProductDetails.aspx?prodID=21383&prodName=Sound%20Blaster)
in Windows by using a [QEMU/KVM VM](https://virt-manager.org/) and the USB Redirection feature.

## System requirements

### Create udev-rule

In `/etc/udev/rules.d/` create a rule file as root (e.q. with name `50-soundblaster-x-g6.rules`) having the
following content:

```text
SUBSYSTEM=="usb", ATTRS{idVendor}=="041e", ATTRS{idProduct}=="3256", TAG+="uaccess"
```

```shell
# Add udev rule:
sudo cat > /etc/udev/rules.d/50-soundblaster-x-g6.rules << EOF
SUBSYSTEM=="usb", ATTRS{idVendor}=="041e", ATTRS{idProduct}=="3256", TAG+="uaccess"
EOF
```

This allows you (and the application) to access the USB device directly and is mandatory for the application to be  
able to send data to the device.

Apply the udev rules by issuing:

```shell
# Reload udev rules:
sudo udevadm trigger
```

### Configure /etc/asound.conf

Configure `/etc/asound.conf` to let ALSA reliably detect the G6 device on reload:

```text
# Force ALSA to always use the Sound BlasterX G6 by its card name (not index)
# The name "G6" is fixed by the driver and never changes even if the kernel
# reassigns card numbers because of other USB devices.

pcm.!default {
    type hw
    card G6
}

ctl.!default {
    type hw
    card G6
}
```

### Install libusb1

The following libusb packages are required:

```txt
libusb-1.0-0-dev/jammy-updates,now 2:1.0.25-1ubuntu2 amd64 [installed]
libusb-1.0-0/jammy-updates,now 2:1.0.25-1ubuntu2 amd64 [installed]
```

```shell
sudo apt-get -y install libusb-1.0-0-dev libusb-1.0-0 
```

## Installation

### Via pipx package (recommended)

To install the CLI tool using `pipx`, run:

```shell
pipx install soundblaster-x-g6-cli
```

The soundblaster-x-g6-cli package is installed in `~/.local/share/pipx/venvs/soundblaster-x-g6-cli/`.

The command `soundblaster-x-g6-cli` should now be available in your shell, otherwise you may have to add the
directory `~/.local/share/pipx/venvs/soundblaster-x-g6-cli/bin/` to your `$PATH` variable.

Note that you still need to create the **udev rule** and create a **sudoers entry** as described above!

### Manual installation (from source)

This section describes how to use the program from source. It contains the following steps:

- clone the repository
- install Python 3.12
- make the prebuilt shell scripts executable
- create a venv and download dependencies using pip

#### Clone repository:

Select a directory of your choice and clone the repository into it:

```shell
(cd $HOME; git clone git@github.com:nils-skowasch/soundblaster-x-g6-cli.git)
```

This should create the directory `~/soundblaster-x-g6-cli`, containing all files.

#### Install Python 3.12:

Install Python3.12. The application has been tested with **Python3.12** (LinuxMint 22.1).

```shell
sudo apt-get install Python3.12
```

#### Make shell scripts executable:

The directory `~/soundblaster-x-g6-cli/shell` contains ready to use shell scripts to toggle or set the device output
of the SoundBlaster X G6. Set the required file permissions and you should be good to go:

```shell
chmod 0544 ~/soundblaster-x-g6-cli/shell/*
```

#### Create a virtual environment and download dependencies

Create a virtual environment and download the dependencies using pip:

```shell
# create virtual environment 'venv'
cd ~/soundblaster-x-g6-cli/
python -m venv venv

# install virtualenv package (if required) and activate 'venv'
pip install virtualenv
virtualenv venv
source venv/bin/activate

# install dependencies into 'venv'
pip install -r requirements.txt
```

### Conclusion

The shell scripts in `/home/<your-username>/soundblaster-x-g6-cli/shell/` should now be usable and the installation
is complete.

## CLI usage

```text
usage: soundblaster-x-g6-cli [-h] [--dry-run] [--debug] [--no-persist] [--version]
                 [--claim-and-release]
                 [--reload-audio-services] 
                 [--toggle-output] 
                 [--set-output {Speakers|Headphones}]
                 [--playback-mute {Enabled|Disabled}]
                 [--playback-volume {0..100}]
                 [--playback-volume-channels {Both|Left|Right}]
                 [--playback-speakers-to-stereo] [--playback-speakers-to-5-1]
                 [--playback-speakers-to-7-1]
                 [--playback-headphones-to-stereo]
                 [--playback-headphones-to-5-1] [--playback-headphones-to-7-1]
                 [--playback-direct-mode {Enabled|Disabled}]
                 [--playback-spdif-out-direct-mode {Enabled|Disabled}]
                 [--playback-filter {FAST_ROLL_OFF_MINIMUM_PHASE|SLOW_ROLL_OFF_MINIMUM_PHASE|FAST_ROLL_OFF_LINEAR_PHASE|SLOW_ROLL_OFF_LINEAR_PHASE}]
                 [--decoder-mode {Normal|Full|Night}] [--lighting-disable]
                 [--lighting-rgb {0..255} {0..255} {0..255}]
                 [--mixer-playback-mute {Enabled|Disabled}]
                 [--mixer-monitoring-line-in-mute {Enabled|Disabled}]
                 [--mixer-monitoring-line-in-volume {0|10|20|..|100}]
                 [--mixer-monitoring-line-in-volume-channels {Both|Left|Right}]
                 [--mixer-monitoring-external-mic-mute {Enabled|Disabled}]
                 [--mixer-monitoring-external-mic-volume {0|10|20|..|100}]
                 [--mixer-monitoring-external-mic-volume-channels {Both|Left|Right}]
                 [--mixer-monitoring-spdif-in-mute {Enabled|Disabled}]
                 [--mixer-monitoring-spdif-in-volume {0|10|20|..|100}]
                 [--mixer-monitoring-spdif-in-volume-channels {Both|Left|Right}]
                 [--mixer-recording-line-in-mute {Enabled|Disabled}]
                 [--mixer-recording-line-in-volume {0|10|20|..|100}]
                 [--mixer-recording-line-in-volume-channels {Both|Left|Right}]
                 [--mixer-recording-external-mic-mute {Enabled|Disabled}]
                 [--mixer-recording-external-mic-volume {0|10|20|..|100}]
                 [--mixer-recording-external-mic-volume-channels {Both|Left|Right}]
                 [--mixer-recording-spdif-in-mute {Enabled|Disabled}]
                 [--mixer-recording-spdif-in-volume {0|10|20|..|100}]
                 [--mixer-recording-spdif-in-volume-channels {Both|Left|Right}]
                 [--mixer-recording-what-u-hear-mute {Enabled|Disabled}]
                 [--mixer-recording-what-u-hear-volume {0|10|20|..|100}]
                 [--mixer-recording-what-u-hear-volume-channels {Both|Left|Right}]
                 [--recording-mute {Enabled|Disabled}]
                 [--recording-mic-recording-volume {0|10|20|..|100}]
                 [--recording-mic-recording-volume-channels {Both|Left|Right}]
                 [--recording-mic-boost-db {0|10|20|30}]
                 [--recording-mic-monitoring-mute {Enabled|Disabled}]
                 [--recording-mic-monitoring-volume {0|10|20|..|100}]
                 [--recording-mic-monitoring-volume-channels {Both|Left|Right}]
                 [--recording-voice-clarity-noise-reduction {Enabled|Disabled}]
                 [--recording-voice-clarity-noise-reduction-level {0|20|40|..|100}]
                 [--recording-voice-clarity-aec {Enabled|Disabled}]
                 [--recording-voice-clarity-smart-volume {Enabled|Disabled}]
                 [--recording-voice-clarity-mic-eq {Enabled|Disabled}]
                 [--recording-voice-clarity-mic-eq-preset {PRESET_1|PRESET_2|PRESET_3|PRESET_4|PRESET_5|PRESET_6|PRESET_7|PRESET_8|PRESET_9|PRESET_10|PRESET_DM_1}]
                 [--sbx-profile {Gaming,Music,Cinema,Special}]
                 [--sbx-profile-switch {Gaming,Music,Cinema,Special}]
                 [--sbx-profile-print]
                 [--sbx-surround {Enabled|Disabled}]
                 [--sbx-surround-value {0..100}]
                 [--sbx-crystalizer {Enabled|Disabled}]
                 [--sbx-crystalizer-value {0..100}]
                 [--sbx-bass {Enabled|Disabled}] [--set-bass-value {0..100}]
                 [--sbx-smart-volume {Enabled|Disabled}]
                 [--sbx-smart-volume-value {0..100}]
                 [--sbx-smart-volume-special-value {Night|Loud}]
                 [--sbx-dialog-plus {Enabled|Disabled}]
                 [--sbx-dialog-plus-value {0..100}]

SoundBlaster X G6 CLI

options:
  -h, --help            show this help message and exit

General options:
  --dry-run             Used to verify the available hex_line files, without making any calls against the G6 device.
  --debug               Print communication data with the G6 device to the console.
  --no-persist          Disables reading and writing of the current G6 state in file '~/.soundblaster-x-g6/g6.json'.
  --version             show program's version number and exit
  --claim-and-release   Let the application exclusively claim the G6's USB AudioControl interface from the kernel and release it afterwards. 
                        This will disconnect the G6 device from the kernel sound driver "snd-usb-audio" leading the system not having any audio output. 
                        Use `--reload-audio-services` to reload it and make the audio output available again.
  --reload-audio-services
                        Let the system reset the G6 USB device and restart user PipeWire services.

Playback [HID]:
  Control basic features using the G6's USB HID interface.

  --toggle-output       Toggles the sound output between Speakers and Headphones.
  --set-output {Speakers|Headphones}
                        Sets the sound output to the specified option.
  --playback-direct-mode {Enabled|Disabled}
                        Enable/disable Direct Mode.
  --playback-spdif-out-direct-mode {Enabled|Disabled}
                        Enable/disable SPDIF-Out Direct Mode.
  --playback-filter {FAST_ROLL_OFF_MINIMUM_PHASE|SLOW_ROLL_OFF_MINIMUM_PHASE|FAST_ROLL_OFF_LINEAR_PHASE|SLOW_ROLL_OFF_LINEAR_PHASE}
                        Set playback filter by enum name.

Playback [Audio]:
  Control advanced features using the G6's USB AudioControl interface. See `--claim-and-release` how to use these features.

  --playback-mute {Enabled|Disabled}
                        Mute/unmute playback.
  --playback-volume {0..100}
                        Set playback volume as integer.
  --playback-volume-channels {Both|Left|Right}
                        Set playback volume channels for --playback-volume.
  --playback-speakers-to-stereo
                        Switch speakers output to stereo.
  --playback-speakers-to-5-1
                        Switch speakers output to 5.1.
  --playback-speakers-to-7-1
                        Switch speakers output to 7.1.
  --playback-headphones-to-stereo
                        Switch headphones output to stereo.
  --playback-headphones-to-5-1
                        Switch headphones output to 5.1.
  --playback-headphones-to-7-1
                        Switch headphones output to 7.1.

Decoder [HID]:
  Control decoder features using the G6's USB HID interface.

  --decoder-mode {Normal|Full|Night}
                        Set decoder mode.

Lighting [HID]:
  Control lighting features using the G6's USB HID interface.

  --lighting-disable    Disable device lighting.
  --lighting-rgb {0..255} {0..255} {0..255}
                        Enable lighting and set RGB.

Mixer [Audio]:
  Control mixer features using the G6's USB AudioControl interface. See `--claim-and-release` how to use these features.

  --mixer-playback-mute {Enabled|Disabled}
                        Mute/unmute mixer playback.
  --mixer-monitoring-line-in-mute {Enabled|Disabled}
                        Mute/unmute line-in monitoring.
  --mixer-monitoring-line-in-volume {0|10|20|..|100}
                        Set line-in monitoring volume as integer.
  --mixer-monitoring-line-in-volume-channels {Both|Left|Right}
                        Define channels for --mixer-monitoring-line-in-volume.
  --mixer-monitoring-external-mic-mute {Enabled|Disabled}
                        Mute/unmute external mic monitoring.
  --mixer-monitoring-external-mic-volume {0|10|20|..|100}
                        Set external mic monitoring volume as integer.
  --mixer-monitoring-external-mic-volume-channels {Both|Left|Right}
                        Define channels for --mixer-monitoring-external-mic-volume.
  --mixer-monitoring-spdif-in-mute {Enabled|Disabled}
                        Mute/unmute spdif-in monitoring.
  --mixer-monitoring-spdif-in-volume {0|10|20|..|100}
                        Set spdif-in monitoring volume as integer.
  --mixer-monitoring-spdif-in-volume-channels {Both|Left|Right}
                        Define channels for --mixer-monitoring-spdif-in-volume.
  --mixer-recording-line-in-mute {Enabled|Disabled}
                        Mute/unmute line-in recording.
  --mixer-recording-line-in-volume {0|10|20|..|100}
                        Set line-in recording volume as integer.
  --mixer-recording-line-in-volume-channels {Both|Left|Right}
                        Define channels for --mixer-recording-line-in-volume.
  --mixer-recording-external-mic-mute {Enabled|Disabled}
                        Mute/unmute external mic recording.
  --mixer-recording-external-mic-volume {0|10|20|..|100}
                        Set external mic recording volume as integer.
  --mixer-recording-external-mic-volume-channels {Both|Left|Right}
                        Define channels for --mixer-recording-external-mic-volume.
  --mixer-recording-spdif-in-mute {Enabled|Disabled}
                        Mute/unmute spdif-in recording.
  --mixer-recording-spdif-in-volume {0|10|20|..|100}
                        Set spdif-in recording volume as integer.
  --mixer-recording-spdif-in-volume-channels {Both|Left|Right}
                        Define channels for --mixer-recording-spdif-in-volume.
  --mixer-recording-what-u-hear-mute {Enabled|Disabled}
                        Mute/unmute what-u-hear recording.
  --mixer-recording-what-u-hear-volume {0|10|20|..|100}
                        Set what-u-hear recording volume as integer.
  --mixer-recording-what-u-hear-volume-channels {Both|Left|Right}
                        Define channels for --mixer-recording-what-u-hear-volume.

Recording [HID]:
  Control recording features using the G6's USB HID interface.

  --recording-mic-boost-db {0|10|20|30}
                        Set mic boost in dB as integer.
  --recording-voice-clarity-noise-reduction {Enabled|Disabled}
                        Enable/disable noise reduction.
  --recording-voice-clarity-noise-reduction-level {0|20|40|..|100}
                        Set noise reduction level as integer.
  --recording-voice-clarity-aec {Enabled|Disabled}
                        Enable/disable acoustic echo cancellation (AEC).
  --recording-voice-clarity-smart-volume {Enabled|Disabled}
                        Enable/disable smart volume.
  --recording-voice-clarity-mic-eq {Enabled|Disabled}
                        Enable/disable mic equalizer.
  --recording-voice-clarity-mic-eq-preset {PRESET_1|PRESET_2|PRESET_3|PRESET_4|PRESET_5|PRESET_6|PRESET_7|PRESET_8|PRESET_9|PRESET_10|PRESET_DM_1}
                        Set mic equalizer preset by enum name.

Recording [Audio]:
  Control recording features using the G6's USB AudioControl interface. See `--claim-and-release` how to use these features.

  --recording-mute {Enabled|Disabled}
                        Mute/unmute recording.
  --recording-mic-recording-volume {0|10|20|..|100}
                        Set mic recording volume as integer.
  --recording-mic-recording-volume-channels {Both|Left|Right}
                        Define channels --recording-mic-recording-volume.
  --recording-mic-monitoring-mute {Enabled|Disabled}
                        Enable/disable mic monitoring.
  --recording-mic-monitoring-volume {0|10|20|..|100}
                        Set mic monitoring volume as integer.
  --recording-mic-monitoring-volume-channels {Both|Left|Right}
                        Define channels for --recording-mic-monitoring-volume.

SBX [HID]:
  Control SBX effects using the G6's USB HID interface.

  --sbx-profile {Gaming,Music,Cinema,Special}
                        Defines the SBX profile to use for updating single SBX effects. May not be used together with --sbx-profile-switch.
  --sbx-profile-switch {Gaming,Music,Cinema,Special}
                        Switch to the specified SBX profile. May not be used together with --sbx-profile.
  --sbx-profile-print   Prints the name of the current active SBX profile to console.
  --sbx-surround {Enabled|Disabled}
                        Enables or disables the Surround sound effect. Specify the SBX profile to update with --sbx-profile.
  --sbx-surround-value {0..100}
                        Set the value for the Surround sound effect as integer. Specify the SBX profile to update with --sbx-profile.
  --sbx-crystalizer {Enabled|Disabled}
                        Enables or disables the Crystalizer sound effect. Specify the SBX profile to update with --sbx-profile.
  --sbx-crystalizer-value {0..100}
                        Set the value for the Crystalizer sound effect as integer. Specify the SBX profile to update with --sbx-profile.
  --sbx-bass {Enabled|Disabled}
                        Enables or disables the Bass sound effect. Specify the SBX profile to update with --sbx-profile.
  --sbx-bass-value {0..100}
                        Set the value for the Bass sound effect as integer. Specify the SBX profile to update with --sbx-profile.
  --sbx-smart-volume {Enabled|Disabled}
                        Enables or disables the Smart-Volume sound effect. Specify the SBX profile to update with --sbx-profile.
  --sbx-smart-volume-value {0..100}
                        Set the value for the Smart-Volume sound effect as value. Specify the SBX profile to update with --sbx-profile.
  --sbx-smart-volume-special-value {Night|Loud}
                        Set the value for the Smart-Volume sound effect as string (supersedes --set-smart-volume-value). Specify the SBX profile to update with --sbx-profile.
  --sbx-dialog-plus {Enabled|Disabled}
                        Enables or disables the Dialog-Plus sound effect. Specify the SBX profile to update with --sbx-profile.
  --sbx-dialog-plus-value {0..100}
                        Set the value for the Dialog-Plus sound effect as integer. Specify the SBX profile to update with --sbx-profile.
```

## Development

Before continuing this section, see the section **System Requirements** and install the required system dependencies.

### Building the application

To build the application, run the following commands:

```shell
# builds the application into the dist/ directory
python -m build

# verifies the build
python -m twine check dist/*
```

### Testing the application

You can test the application with multiple python versions using pyenv and tox.

#### Pyenv

Use pyenv to manage multiple Python versions.

##### Install pyenv

```shell
curl -fsSL https://pyenv.run | bash
```

##### Append pyenv to ~/.bashrc

Append the following lines to `~/.bashrc` to make `pyenv` available in your shell.

```shell
cat >> ~/.bashrc << EOF
#
# pyenv:
#
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - bash)"

EOF
```

Restart the shell afterwards, or run`source ~/.bashrc`.

##### Install required dependencies

The following dependencies were required for LinuxMint 22.1:

```shell
sudo apt install libreadline-dev libssl-dev libsqlite3-dev
```

There may be other dependencies required for your Linux distribution. Maybe these commands help:

```shell
sudo apt update
sudo apt install -y \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    curl \
    git \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libffi-dev \
    liblzma-dev
```

##### Test your pyenv setup

Run the following command to verify your pyenv setup:

```shell
pyenv doctor
```

##### Install supported Python versions

Install the supported python versions using pyenv:

```shell
# 3.12
pyenv install 3.12.3

# rehash pyenv shims (run this after installing executables)
pyenv rehash
```

#### tox

Test all python environments defined in pyproject.toml using tox.

```shell
tox
```

Test a single python environment using tox:

```shell
tox -e py312
```

### Deploying the application

Create a .pypirc file in your home directory with the following content:

```text
[testpypi]
  username = __token__
  password = <api-token>
```

Deploy the application on testpypi.org:

```shell
python -m twine upload --repository testpypi dist/* 
```

Download the application from testpypi.org and test it:

```shell
pipx install --pip-args="--index-url https://test.pypi.org/simple --extra-index-url https://pypi.org/simple" soundblaster-x-g6-cli
```

# SoundBlaster X G6 USB specification

I reverse-engineered the USB specification by recording the USB communication using
[Wireshark USBPCAP](https://wiki.wireshark.org/CaptureSetup/USB) and making conclusions of the HEX codes being
transmitted from
[SoundBlaster Command](https://support.creative.com/Products/ProductDetails.aspx?prodID=21383&prodName=Sound%20Blaster)
(Application version: `3.4.98.0`; Driver version: `1.16.4.26`) to the device.

See: [usb-spec.md](https://github.com/nils-skowasch/soundblaster-x-g6-cli/blob/main/doc/usb-spec.md)

# USB protocol

The following file contains some basic information about the USB protocol:

See: [usb-protocol.md](https://github.com/nils-skowasch/soundblaster-x-g6-cli/blob/main/doc/usb-protocol.md)
