# The G6 on Linux — what this fork offers, and where it sits

This app started life as, and still primarily is, a Linux tool — the GUI and
the macOS packaging are additions on top of Nils Skowasch's original CLI,
which was written for Linux and remains upstream (`src/g6_cli/`, never
modified here — see `HANDOFF.md` §2). This page is for Linux users
specifically: what you get here that macOS users don't, and how this project
compares to the other tools already controlling the G6 on Linux.

**Nothing in this page has been re-verified against a Linux machine in this
round of work** — there wasn't one available. See `LINUX-TESTING.md` at the
repository root for the checklist a future session should run against real
hardware; treat the claims below as "should work, per the code and the
protocol evidence," not "confirmed this week."

## What Linux gets that macOS doesn't

The dividing line is one USB interface: the G6's **AudioControl** interface,
which carries volume, mute, channel-config and the mixer's per-input
controls. Using it requires detaching the kernel's own audio driver first —
`--claim-and-release` — and macOS refuses to let any application do that to
its own USB Audio Class driver. Linux has no such restriction. So, only on
Linux:

- **The Mixer tab** — per-source mute and volume, split into recording and
  monitoring levels, for Line In, External Mic, S/PDIF In and What-U-Hear.
  Does not exist on macOS at all (see `docs/settings-reference.md`'s Mixer
  section).
- **Playback volume and mute**, and the equivalent recording-side rows on the
  Recording tab.
- **Claim/Release** and **Reload audio** on the System tab — the switch that
  makes the above possible, and the button that puts your kernel audio driver
  back afterwards. Claiming genuinely takes your system's audio away until
  you release it; the GUI releases automatically on quit, but a crash could
  in principle leave it claimed (untested).
- **Speaker/headphone Stereo·5.1·7.1 switching**, in the sense that the
  commands can actually be *sent* — the AudioControl interface is available
  to claim. Whether they do anything is a separate question, addressed
  honestly below; don't take "the flag exists and runs" as proof it works.

Two things that are **not** gated behind claim/release, because they run over
the G6's separate vendor **HID** interface rather than AudioControl, and so
are not blocked by anything OS-specific the way the above are on macOS:

- **Direct Mode and SPDIF-Out Direct.** On macOS these are overridden because
  macOS itself continuously re-asserts the device's mode through Core Audio's
  clock selector (see `settings-reference.md`'s Direct Mode section) — a
  macOS-specific interference that has nothing to do with claim/release.
  **[INFERRED]** (protocol + platform mechanics: Linux has no equivalent
  mechanism standing in the way) these commands should reach the device and
  take effect the way Creative's own Windows software achieves the same
  thing — but nobody has watched it happen on a Linux box in this project.
  `LINUX-TESTING.md` has the verification steps.
- **Output switching, the DAC filter (including the hidden fifth,
  Non-Over-Sampling — see below), the decoder mode, lighting, mic boost,
  Voice Clarity, and all of SBX** — everything on the HID interface works
  identically on Linux and macOS, no claim/release needed either way.

### Be honest about 5.1/7.1: what's confirmed and what isn't

`settings-reference.md` has the full writeup
([Virtual 7.1](settings-reference.md#virtual-71)), but
the short version matters here specifically because Linux is the platform
where these flags can actually run: **[INFERRED]** (source:
`src/g6_cli/g6_spec/playback.py`) `speakers_to_7_1()` / `speakers_to_5_1()`
(and the headphone equivalents) send **byte-identical packets** to the plain
stereo command — upstream's own docstring speculates the real channel switch
happens through the OS rather than through this packet. So running
`--playback-speakers-to-7-1` on Linux is expected to succeed (the command is
well-formed and the interface is claimable) without there being good evidence
it changes the channel count by itself — **this is genuinely doubtful, not
just unconfirmed**. If genuine 7.1 output matters to you, the more promising
route is likely to open the G6 as an 8-channel sink directly in
PipeWire/ALSA and use this app only for Direct Mode / SBX / filter alongside
that — see `LINUX-TESTING.md`'s checklist for how to actually determine which
is true.

### The new fifth DAC filter — Non-Over-Sampling (NOS)

**[INFERRED]** (g6-re firmware disassembly, credited in full in
[firmware-findings.md](firmware-findings.md)): the G6's DAC supports a fifth
reconstruction filter, Non-Over-Sampling, that Creative's own Windows app
deliberately hides. This app now offers it — see
`settings-reference.md`'s filter section for the tradeoffs (measurably worse
on paper, a legitimate taste preference, less bad at higher sample rates) and
a known rough edge in how it's wired into this codebase (a model-persistence
error fires right after the device write succeeds, so the UI reverts and
`g6.json` doesn't record the change unless you pass `--no-persist`). This is
pure HID protocol, so it applies identically on Linux and macOS; nobody has
tried it on real Linux hardware yet.

## Where this fits among other G6 tools on Linux

There is an active, independently-developed ecosystem of G6 controllers for
Linux — this is not the only option, and it's worth being direct about that.
The vendored research at
[`docs/g6-re/docs/LINUX-ECOSYSTEM.md`](g6-re/docs/LINUX-ECOSYSTEM.md)
surveyed four of them (credit: `HyperRamzey/g6-re`):

| Project | Language/UI | Notes |
|---|---|---|
| [`linuxblaster_control`](https://github.com/RizeCrime/linuxblaster_control) (RizeCrime) | Rust, GTK | Deepest USB protocol documentation of the group; Direct Mode documented but listed "not planned" in their own UI |
| **`soundblaster-x-g6-cli`** (Nils Skowasch) | Python, CLI | **This project's upstream.** The most feature-complete controller of the four — Direct Mode, SPDIF-Out Direct, filters, full SBX, mixer, lighting, decoder modes. Installable via `pipx` or from PyPI |
| [`soundblaster-g6x-linux-controller`](https://github.com/dreamzone-cc/soundblaster-g6x-linux-controller) (dreamzone-cc) | Rust (wry+tao) + SvelteKit | Polished desktop app with tray/autostart; packages as **.deb, AppImage, and Flatpak**; claims support for both the G6 (`041e:3256`) and a second device it calls "G6X" (`041e:3263`) — see [firmware-findings.md](firmware-findings.md#7-sound-blasterx-g6-versus-g6x--what-the-evidence-actually-shows) for why that identification is not fully settled |
| [`Sound-BlasterX-G6-Control`](https://github.com/xuda-ye-math/Sound-BlasterX-G6-Control) (xuda-ye-math) | Rust (CLI + egui) | Arch-focused, AUR packaged; roadmap includes a Direct Mode toggle it doesn't have yet |

**None of the four target macOS.** They are all Linux-only (one Windows-Rust
port aside, none ship a macOS build). That makes the GUI in this repository
the first graphical G6 controller for macOS, as far as this survey found —
worth stating plainly, and worth being equally plain that it does not make
this project's *Linux* support more mature than the others'. On Linux, this
fork inherits upstream's CLI feature set (the most complete of the four per
the table in `LINUX-ECOSYSTEM.md`) and adds the Toga GUI on top of it; it
does not currently implement anything the others don't already have on
Linux, and RizeCrime's project in particular has more detailed low-level USB
protocol documentation than this repository does.

Two things the g6-re research flagged as low-hanging fruit for *any* of these
projects, including this one, if someone wants to pick them up:

- **`SpeakersHRTFMode`** — a real, live-confirmed, firmware-enabled feature
  (`SET 30`, one byte) that none of the five projects surveyed (the four
  above, plus this one) currently expose. See
  [firmware-findings.md §6](firmware-findings.md#6-hrtf-mode--what-it-is-and-why-this-app-doesnt-touch-it)
  for why it's parked here specifically (headphone-only development setup,
  can't evaluate a speaker-oriented feature).
- The **NOS filter** payload (`0003`) — one enum value away from working in
  upstream's own `PlaybackFilter`, and already added in this fork as a
  non-upstream shim (see `settings-reference.md`).

## Setting up

See the main [readme.md](../readme.md) for udev rules, `libusb`/`hidapi`
system packages, and the ALSA `asound.conf` snippet, and
[gui.md](gui.md#install) for the additional GTK packages the GUI needs
(`python3-gi`, `gir1.2-gtk-3.0` on Debian/Ubuntu; equivalents for
Fedora/Arch listed there).
