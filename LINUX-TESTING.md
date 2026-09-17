# Linux verification handoff

**Read this if you are picking up this project on an actual Linux machine.**
It was written by a documentation-only session with no Linux hardware, no
Linux environment, and no G6 device available. Everything Linux-specific in
this repo's docs (`docs/linux.md`, parts of `docs/settings-reference.md` and
`docs/firmware-findings.md`) is **[INFERRED]** — reasoned from source code and
protocol evidence, never verified against real hardware. This checklist
closes that gap. You have no memory of the session that wrote this;
everything you need is below or linked from here.

**Untracked on purpose** (same reasoning as `HANDOFF.md` §2): delete this file
once its checklist has been run and the docs updated with real **[TESTED]**
results, or once it's otherwise stale.

**Goal, in one sentence:** confirm or refute this project's claims about
**Linux-only functionality** — Mixer tab, playback volume/mute, claim/release,
Direct Mode, SPDIF-Out Direct, 5.1/7.1 channel switching, the NOS filter —
against a real Sound BlasterX G6 on real Linux.

---

## 0. Setup

- [ ] Linux machine (any modern distro; upstream tested on LinuxMint 22.1) +
      real Sound BlasterX G6 (USB PID `0x3256` — see
      `docs/firmware-findings.md` §7 if it's a USB-C revision or labelled
      "G6X", it may not be recognized) + a headphone/speaker on it.
- [ ] System deps:
  ```bash
  sudo apt-get install libusb-1.0-0-dev libusb-1.0-0 python3-gi gir1.2-gtk-3.0
  # Fedora: python3-gobject gtk3 — Arch: python-gobject gtk3 — see docs/gui.md
  ```
- [ ] udev rule:
  ```bash
  sudo tee /etc/udev/rules.d/50-soundblaster-x-g6.rules > /dev/null << 'EOF'
  SUBSYSTEM=="usb", ATTRS{idVendor}=="041e", ATTRS{idProduct}=="3256", TAG+="uaccess"
  EOF
  sudo udevadm control --reload-rules && sudo udevadm trigger
  ```
- [ ] Clone + venv:
  ```bash
  git clone <this-repo> && cd soundblaster-x-g6-cli
  git checkout feature/g6-re-findings   # or wherever this landed
  python3.12 -m venv venv
  ./venv/bin/pip install -e '.[gui]' pytest pytest-asyncio pyyaml
  ```
- [ ] **Plug in the G6 before doing anything else** — `G6Api()` raises
      `IOError` at construction if no device is found, **even with
      `--dry-run`** (see `docs/device-state.md`). GUI: shows a device-gate
      screen. CLI: errors out.

## 1. Run it

```bash
./venv/bin/soundblaster-x-g6-gui              # GUI
./venv/bin/soundblaster-x-g6-gui --debug      # + prints every HID/USB write
./venv/bin/pytest tests/g6_gui -q             # test suite — ONLY this path
```

- [ ] All `tests/g6_gui` pass on a clean checkout, no device needed (they run
      against the `fake_api.py` recording double, not real hardware).
- [ ] Do **not** run `tests/g6_cli` (~241 failures/258 errors on Python 3.12,
      an unrelated upstream argparse wording change) and do not "fix" it here.
- [ ] If a `g6_gui` test fails on Linux that passed on macOS: platform bug —
      Linux/macOS diverge in `platform.py` (`AUDIO_INTERFACE_SUPPORTED`,
      `DIRECT_MODE_SUPPORTED`); check whether the failing path was only ever
      exercised in the macOS-shaped branch.

Use `--debug` throughout §2 — compare the actual bytes against
`docs/settings-reference.md`'s `[bytes]`-tagged claims, not just pass/fail.

## 2. Verification checklist

For each item: do it, note what you saw/heard, write it down (§3).

### 2.1 Claim / Release (System tab)
- [ ] "Claim audio interface" switch + "Reload audio" button visible (Linux
      is `AUDIO_INTERFACE_SUPPORTED`).
- [ ] Turning Claim on stops system audio through the G6 immediately (play
      something first so you notice it cut out).
- [ ] Mixer tab + Playback/Recording volume/mute rows go disabled → enabled.
- [ ] Turning Claim off, or "Reload audio", restores system audio.
- [ ] Record: does audio actually stop/resume; how long release+reload takes;
      whether any other audio app needed a restart to notice the G6 again.

### 2.2 Mixer tab
- [ ] With the interface claimed: for Line In, External Mic, S/PDIF In,
      What-U-Hear — toggle mute, move recording/monitoring volume sliders.
- [ ] Expect: muting silences that input; volume changes are audible and
      monotonic. No device readback exists (`docs/device-state.md`) — the
      only check is what you hear, not what the UI claims.
- [ ] Record: which of the four sources you could actually test (don't
      guess on ones you couldn't wire up); whether mute/volume are
      independent per source or bleed across (e.g. does muting Line In
      monitoring affect its recording level?).

### 2.3 Playback / Recording volume and mute (Audio interface)
- [ ] Playback tab volume/mute; Recording tab equivalents.
- [ ] Expect: matches `docs/settings-reference.md`'s USB Audio Class scale
      (100% = 0 dB, 50% ≈ −10 dB, 0% = −64 dB playback; −48 dB to +9 dB
      recording). You can't verify exact dB by ear, but direction,
      roughly-logarithmic feel, and 10%-step granularity should be obvious.
- [ ] Record: whether the steps feel right; whether mute is instant/complete.

### 2.4 Direct Mode
- [ ] Playback tab: enable Direct Mode. Try an SBX effect (e.g. Crystalizer)
      — should be audibly disabled. Try mic recording — should not work
      (Creative's own docs: Direct Mode disables mic recording). Try
      sidetone if testable — should still work. Turn Direct Mode back off.
- [ ] Expect **zero platform interference** on Linux, unlike macOS (see
      `docs/settings-reference.md`'s macOS section for what the override
      problem looks like there, so you know what its absence should look
      like here).
- [ ] Record: does it behave as described. If effects keep working, that's a
      significant unexpected finding — first check `--debug`: is the byte
      pattern the one documented in `settings-reference.md`'s Direct Mode
      section?

### 2.5 SPDIF-Out Direct
- [ ] Needs optical output into a receiver/soundbar/anything with TOSLINK in.
      Enable it; confirm optical output is unprocessed and that Direct Mode
      / SPDIF-Out Direct are mutually exclusive (enabling one disables the
      other in the UI).
- [ ] Expect (per Creative's G5-era docs, assumed to hold for G6): bit-perfect
      PCM, no SBX, and G6-side volume control stops working once this is on.
      **Genuinely untested anywhere in this project** — closing this is one
      of the more valuable things this checklist can do.
- [ ] Record: does it work at all; does the "volume no longer controllable"
      behavior reproduce.

### 2.6 5.1 / 7.1 channel switching — the important one
Read `docs/settings-reference.md`'s
["Virtual 7.1"](docs/settings-reference.md#virtual-71)
first. Short version: **[INFERRED]** (source:
`src/g6_cli/g6_spec/playback.py`) `speakers_to_7_1()`/`speakers_to_5_1()` send
byte-identical packets to plain stereo — real reason to doubt these flags do
anything alone. This test exists to find out, not confirm the doubt.

- [ ] Stereo baseline: `pactl list sinks short` (or `pw-cli ls Node`), note
      the G6's channel count.
- [ ] Run `--playback-speakers-to-7-1 --claim-and-release` (CLI) or the GUI
      equivalent. Re-check channel count — did it change?
- [ ] Independent of step 2: route genuinely multichannel content (8-channel
      test tone, or a game/movie with a 7.1 track) to the G6 as an
      8-channel sink directly via PipeWire/ALSA. Does the OS alone open it
      as 8-channel without the command ever having been sent?
- [ ] If step 3 works alone, try with/without having sent the step-2 command,
      and listen for a difference (binaural HRTF render vs. flat downmix,
      per `firmware-findings.md`).
- [ ] Enable Direct Mode, repeat — render should collapse to a static
      downmix per `firmware-findings.md` §2/§3.
- [ ] Record `pactl`/`pw-cli` output before/after each step; anything audible
      in 8-channel mode; whether Direct Mode changed the sound as predicted.
      Three equally informative outcomes: (a) the CLI command alone changes
      channel count and gives a genuine 7.1 render → the docs' skepticism
      was wrong, update `settings-reference.md`'s Virtual 7.1 section with
      the evidence; (b) the CLI command does nothing but an 8-channel
      PipeWire/ALSA sink gives the render anyway → confirms current best
      guess, document that as the actual path to 7.1; (c) neither works →
      document exactly what was tried.

### 2.7 The NOS filter
- [ ] Playback tab → Filter → Non-Over-Sampling, with model persistence on
      (default). Per `settings-reference.md`'s filter section and
      `src/g6_gui/filters.py`'s docstring, expect: device write succeeds,
      then the app raises an error, reverts the dropdown, and does **not**
      save to `g6.json`. Confirm this happens.
- [ ] Listen: audible treble roll-off / reduced pre-ringing despite the UI
      error?
- [ ] Repeat with `--no-persist` — error should disappear (no persistence
      step to fail).
- [ ] Record: does the error/revert behavior match; is NOS audible at all;
      does `--no-persist` avoid the error as expected.

## 3. Where to record results

Update the docs directly, citing what you did, using **[TESTED]**/date for
anything you observed and **[INFERRED]** for anything you didn't:

- `docs/settings-reference.md` — resolve/update the relevant
  [Open questions](docs/settings-reference.md#open-questions) (7–12 cover
  most of this checklist).
- `docs/linux.md` — update the 5.1/7.1 "what's confirmed" framing once known.
- `docs/firmware-findings.md` — note anything that contradicts or confirms
  g6-re's firmware-level claims, clearly distinguishing your own Linux-side
  observation from their firmware disassembly.

Do **not** just narrate results in a chat session and let them evaporate —
this file exists because that already happened once (the macOS Audio tab's
confirmed-against-real-G6 work is in `docs/settings-reference.md` precisely
because someone wrote it down there instead of only saying it out loud).

## 4. Publishing Linux releases — what's actually needed

This project currently publishes **only** a signed/unsigned macOS
`.app`/`.dmg` (`.github/workflows/macos-release.yml`). No Linux build
workflow exists yet.

- [ ] **Licence constraint (read first):** GPL-2.0-only. Every dependency
      must be compatible. **PySide6, PyQt5/6, wxPython are forbidden**
      (LGPLv3/GPLv3, incompatible with GPL-2.0-only in a way that blocks
      distribution in any form) — this is why Toga (BSD-3, via Travertino
      and Rubicon-ObjC) was chosen, and it applies to a Linux package
      exactly as it did to macOS. Don't let a Linux packaging tool pull in a
      forbidden Qt binding transitively. Relicensing is not available (the
      maintainer is not the copyright holder) — not negotiable later.
- [ ] Get a Linux machine + G6 and run §2 first — no point packaging
      unconfirmed Linux-only features.
- [ ] Add `[tool.briefcase.app.g6_gui.linux]` to `pyproject.toml` (currently
      only the macOS section exists) and try `briefcase build linux
      appimage` locally — Briefcase already has first-party Linux backends
      (AppImage, Flatpak, `.deb`/`.rpm`), the natural path since the project
      is already Briefcase-structured. **Not yet attempted** — don't assume
      it "just works" by analogy with macOS (see `HANDOFF.md`'s macOS
      packaging gotchas: libusb bundling, notarization, Homebrew
      contamination — platform packaging always has its own surprises).
- [ ] If that works, add a new GitHub Actions workflow modeled on
      `macos-release.yml` (`runs-on: ubuntu-latest`, its own GTK/libusb
      install step, its own Briefcase Linux build/package steps — can share
      the version-tag-and-release logic, but that needs designing, not
      assuming).
- [ ] Only then consider AUR/Flatpak/PyPI distribution (reach, not
      correctness) — see `docs/linux.md`'s ecosystem table for what's
      already proven to work for this kind of app on Linux: plain PyPI/pipx
      (simplest; this fork's GUI needs its own PyPI name, e.g.
      `soundblaster-x-g6-gui`, since `soundblaster-x-g6-cli` is upstream's
      and this fork versions separately — `HANDOFF.md` §2b), AUR (`*-git`
      packages, two of the four other Linux G6 projects use this), or
      `.deb`/AppImage/Flatpak (broadest reach, most work —
      `soundblaster-g6x-linux-controller` ships all three).
