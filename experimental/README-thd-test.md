# `thd-test-macos.py` — does the G6 actually distort worse at 100% volume?

See [`README.md`](README.md) for what else lives in this directory.

A standalone script (`experimental/thd-test-macos.py`, no dependency on this
repo's `g6_cli`/`g6_gui`/`g6_device` code) that plays tones through the G6,
records the result, and computes THD+N, to answer: **does the G6's distortion
get measurably worse at full digital volume, and does turning the device's
own volume down fix it?** Background: `docs/firmware-findings.md` §1 and
`docs/settings-reference.md`'s "Full-scale volume" section — Audio Science
Review measured ~1% THD+N at 20 Hz at 0 dBFS in 2019, dropping to nothing at
-2 dBFS; firmware disassembly shows the relevant gain constants unchanged
since. Unknown: whether the G6's own volume control (a real hardware control,
not host-side gain) sits before or after its DAC.

## The measurement could not be performed

This measurement was attempted and could not be completed. The owner's setup
has no separate recording input — all inputs are combined — so a clean
loopback (Option A or B below) was not achievable. This is a closed outcome,
not a pending task: the script and its self-test-verified maths
(`--self-test`, below) remain in the repository for whenever a separate ADC
becomes available, but there is no expectation of that happening soon.

---

## READ THIS FIRST: do not run this inside a VM

If the Mac running this script is itself a virtual machine (or the audio
device is passed through into one), **do not trust any number this script
prints.** USB audio is an isochronous stream; a hypervisor commonly adds
resampling and, under scheduling pressure, dropouts — a single dropout
injects broadband noise into the recording, indistinguishable in the
resulting THD+N figure from real distortion in the G6. You'd be measuring the
VM's USB layer, not the sound card.

The script checks this itself (`sysctl -n kern.hv_vmm_present`) and refuses
the real measurement unless you pass `--i-know-this-is-a-vm` — which doesn't
make the result trustworthy, it just lets you past the guard (useful for
exercising the code, not for conclusions). **Run the actual measurement on
the real host Mac, not inside any VM or remote-desktop session.**

`--self-test` (below) needs no audio hardware and is safe anywhere, including
inside a VM.

---

## What hardware you need

**The G6 itself**, over USB.

**Something to record with** — playing a tone out of the G6 and recording it
needs the analog signal back into the Mac as digital audio:

### Option A — a separate recording interface (better)

A second, independent audio interface with its own line-in/mic-in, wired from
the G6's headphone or line output to that interface's input (headphone-to-
1/4" TS/TRS, or 3.5mm-to-3.5mm if both ends are minijack). Better because the
recording chain's own distortion is independent of the device under test.

### Option B — self-loopback through the G6's own line-in

Cable from the G6's own headphone/line-out back into its own line-in. Works,
but the G6's ADC and DAC are both in the signal path now — a measured THD+N
number is the combination of the G6's output distortion **and** its own
input distortion, and you cannot separate them. **In this mode, trust only
the *relative* change between conditions** (is 0 dBFS worse than -2 dBFS,
does 90% volume read better than 100%), not the absolute numbers — the ADC's
own contribution is roughly constant across compared conditions. The script
prints a note when input and output device are the same, as a reminder.

Either way — a headphone-out-to-line-in cable can easily overload a line
input, especially at 0 dBFS full volume. The script starts quiet and checks
the recorded level before going near full scale, but you may still need to
turn the *recording* side's input gain down independent of the script or the
G6's own volume.

## Hearing safety

If measuring the G6's headphone output specifically: someone's headphones
could be plugged into that jack. **Don't wear headphones while running
this.** The script warns before every full-scale (0 dBFS) tone and keeps
every tone to about 2 seconds.

## Setup on the host Mac

Standalone — no dependency on this repo's own `venv` or `src/`. Set up a
throwaway environment anywhere convenient:

```sh
python3 -m venv venv
source venv/bin/activate
pip install numpy sounddevice
```

If you forget this, running the script tells you exactly what to install.

## Step 1 — verify the maths (always do this first)

```sh
python3 experimental/thd-test-macos.py --self-test
```

No audio hardware needed, safe anywhere including a VM — pure signal-
processing math against synthetic numpy arrays. Should print `SELF-TEST: ALL
5 CHECKS PASSED`: a pure tone reads ~zero THD+N (FFT/windowing floor check);
a tone with a hand-added 3rd harmonic at -40 dBc and 5th at -50.5 dBc reads
back the expected combined ratio within 0.3 dB; a tone with known added white
noise (no harmonics) matches within 0.5 dB; both together (the realistic
case) match within 0.5 dB; a distortion level five times worse reads
numerically worse — checking the scale's sign/direction, since the real test
is about comparing "worse" vs "better". If it doesn't pass, don't trust
anything else from this script until it does.

## Step 2 — find your devices

```sh
python3 experimental/thd-test-macos.py --list-devices
```

Lists every audio device sounddevice can see, by name and index. Find the G6
(shows as "Sound BlasterX G6" or similar) for output, and either a separate
interface or the G6 again for input (see "What hardware you need" above).

## Step 3 — run the real measurement

```sh
python3 experimental/thd-test-macos.py -o "G6" -i "G6"                 # self-loopback
python3 experimental/thd-test-macos.py -o "G6" -i "USB Audio CODEC"    # separate interface
```

`-o`/`-i` accept a name substring (case-insensitive) or numeric device index.
The script always prints which exact device it resolved to, and refuses to
guess if a substring matches more than one — never picks one for you, no
hard-coded device index anywhere.

The script then: prints the chosen devices and asks you to confirm
cabling/headphones; asks you to set the output volume low and runs a quiet
(-20 dBFS) safety probe (also the recording chain's noise-floor reference —
aborts here, before anything full-scale, if the level is too hot or
suspiciously silent); walks through three volume settings (100%, ~90%, ~79%
by default, override with `--volumes`), pausing at each for **you** to set
the output device's own system volume by hand (the script never changes your
volume for you — same rule the macOS Audio tab follows, see
`src/g6_gui/help.py`'s `MACOS_VOLUME`); measures 997 Hz, 60 Hz and 20 Hz at
each setting, at 0 dBFS and -2 dBFS (low frequencies are where Audio Science
Review found the problem); and prints an explicit verdict at the end —
whether 0 dBFS measured worse than -2 dBFS, whether lowering the device's own
volume helped at a fixed 0 dBFS input, plus a reminder that this is one unit,
measured once, through one recording chain: evidence, not proof.
