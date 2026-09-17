# SoundBlaster X G6 — Cross-platform GUI (Toga)

**Date:** 2026-09-15
**Branch:** `feature/gui-toga`
**Status:** Approved design

## Goal

A desktop GUI exposing every option of `soundblaster-x-g6-cli`, running on both
macOS and Linux, using the toolkit's native controls. Linux-only capabilities are
hidden on macOS rather than shown broken.

## Non-goals

- No change to `src/g6_cli/` — the existing CLI and API stay byte-for-byte intact.
- No reimplementation of the USB protocol. The GUI is a client of `G6Api`.
- No visual clone of Creative's Windows software. We borrow its *concepts*
  (tabbed sections, profile carousel → profile selector) and use native widgets.

## Toolkit decision: Toga (BeeWare)

`toga` / `toga-core` / `toga-cocoa` / `travertino` / `rubicon-objc` are all
**BSD-3-Clause**, which is compatible with this project's **GPL-2.0-only** licence.

This constraint is real and drove the choice. Qt bindings were rejected:
PySide6 is LGPLv3 and PyQt6 is GPLv3, and **both are incompatible with
GPL-2.0-only** — LGPLv3/GPLv3 add terms (patent grant, anti-tivoization) that
GPLv2 does not permit adding to a combined work. That blocks distribution in
*any* form, source or binary; shipping source instead of a binary does not cure
it. This repository is a fork (`zipleen/soundblaster-x-g6-cli`) of
Nils Skowasch's project and all existing commits are his, so relicensing to
GPL-2.0-or-later is not unilaterally available to us.

Validated on macOS 15 / arm64 with toga 0.5.6: widgets are genuinely native
AppKit — `TogaSwitch`/`TogaButton` (NSButton), `TogaSlider` (NSSlider),
`TogaPopupButton` (NSPopUpButton), `TogaTabView` (NSTabView), `NSTextField`,
`NSBox`, `NSProgressIndicator`. Values round-trip through `.value` correctly.

**Linux caveat to document:** `toga-gtk` needs system GTK — `python3-gi`,
`gir1.2-gtk-3.0` (Debian/Ubuntu) or `python3-gobject gtk3` (Fedora/Arch).
`pip install` alone is not sufficient on Linux.

## Architecture

```
src/g6_gui/
  __init__.py       main() entry point
  app.py            toga.App subclass; device gate; tab assembly; clean shutdown
  controller.py     async wrapper over G6Api: thread pool, debounce, errors
  platform.py       AUDIO_INTERFACE_SUPPORTED and related capability flags
  widgets.py        reusable rows: switch_row, slider_row, select_row, section
  pages/
    __init__.py
    playback.py     Playback [HID] + [Audio] + Decoder [HID]
    mixer.py        Mixer [Audio]              (Linux only)
    recording.py    Recording [HID] + [Audio]
    sbx.py          SBX [HID]
    lighting.py     Lighting [HID]
    system.py       General options + claim/release + reload (partly Linux only)
tests/g6_gui/
  fake_api.py       FakeG6Api recording double
  *_test.py         per-page and controller tests
```

`src/g6_cli/` is untouched. `pyproject.toml` gains only:
- `[project.optional-dependencies] gui = ["toga>=0.5.6"]`
- `[project.scripts] soundblaster-x-g6-gui = "g6_gui:main"`

### Controller

`G6Api` methods are blocking USB I/O and must never run on the UI thread.

- One `ThreadPoolExecutor(max_workers=1)`. A single worker is deliberate: it
  serializes device access so two writes can never interleave on the wire.
- Calls are dispatched with `loop.run_in_executor` and awaited.
- `call(fn, **kwargs)` is the single choke point for error handling. `IOError`
  from a vanished device returns the app to the device gate; any other exception
  surfaces in a status bar without killing the app.
- `debounced(key, delay, fn, **kwargs)` — schedules after `delay` (default
  150 ms); a later call with the same `key` cancels the pending one. Sliders use
  it so one drag produces one USB write. Switches and dropdowns bypass it.

### Device gate

`G6Api(...)` raises `IOError` in its constructor when no G6 is present — this is
true **even with `--dry-run`**, which was verified. Therefore:

- The app opens on a "Connect your Sound Blaster X G6" screen with a **Retry**
  button and the underlying error text.
- Only on successful construction are the tabs built and shown.
- If a call later raises `IOError`, the app returns to this screen.

### Platform gating

`platform.py` exposes `AUDIO_INTERFACE_SUPPORTED = sys.platform.startswith("linux")`.

Everything reached through the USB **AudioControl** interface requires detaching
the kernel audio driver (`--claim-and-release`), which cannot work against
macOS's class driver. So on macOS these are hidden entirely:

- the whole **Mixer** tab,
- Playback: mute, volume (+channels), speakers/headphones stereo·5.1·7.1,
- Recording: mute, mic recording volume (+ch), mic monitoring mute/volume (+ch),
- System: `--claim-and-release`, `--reload-audio-services`.

On **Linux** these controls exist but stay **disabled** until the user turns on
"Claim audio interface" in the System tab. Claiming detaches the kernel driver
and leaves the system with no audio output until released, so:

- the switch carries a prominent inline warning,
- the app releases the interface on shutdown (`on_exit`), unconditionally.

### State

The G6 cannot be read back. **Correction, 2026-09-17:** this was wrong —
register-value readback is real and decoded; the app deliberately doesn't use
it. See `docs/device-state.md`. Initial widget values come from `api.get_model()`,
i.e. the persisted `~/.soundblaster-x-g6/g6.json`. With no file present,
`G6Model()` defaults apply. The UI labels this honestly as last-known state
rather than implying it queried the hardware. Writes go through `G6Api`, which
updates and saves the model itself — the GUI never writes that file directly.

## Pages

### Playback
HID (all platforms): Output `Speakers|Headphones` (`playback_toggle_to_*`),
Direct Mode, SPDIF-Out Direct Mode, Filter (4 `PlaybackFilter` values),
Decoder mode (`Normal|Full|Night`).
Audio (Linux, claimed): Mute; Volume 0–100 + channel selector `Both|Left|Right`;
Speakers → Stereo/5.1/7.1; Headphones → Stereo/5.1/7.1 (buttons, they are actions).

### Mixer — Linux only
Playback mute. Then Monitoring and Recording groups, each a mute switch +
volume slider (0–100 step 10) + channel selector:
Monitoring: Line In, External Mic, SPDIF In.
Recording: Line In, External Mic, SPDIF In, What U Hear.

### Recording
HID: Mic boost dB (0/10/20/30); Voice Clarity — Noise Reduction + level
(0–100 step 20), AEC, Smart Volume, Mic EQ + preset (`PRESET_1..PRESET_10`,
`PRESET_DM_1`).
Audio (Linux, claimed): Mute; Mic recording volume (+ch); Mic monitoring
mute/volume (+ch).

Mirror the CLI's own correction: "Voice Clarity" and "Noise Reduction" are
separate controls; do not re-merge them.

### SBX
Controls: **Editing profile** dropdown (`Gaming|Music|Cinema|Special`), an
**Active profile** banner, and a **Switch to this profile** button.
Five effects, each a switch + slider 0–100 + numeric readout: Surround,
Crystalizer, Bass, Smart Volume, Dialog+. Smart Volume additionally has a
`None|Night|Loud` selector (`sbx_smart_volume_special`).

**Critical semantics — verified by reading `G6Api`:**
`sbx_toggle()` and `sbx_slider()` send **identical hex to the device regardless
of `profile_name`**. The device holds one live SBX state. The `profile_name`
argument only chooses which profile's entry is updated in the JSON model.
`sbx_profile_switch()` replays all ten stored values of a profile to the device
and sets it active.

Consequence the UI must communicate: editing profile M while profile G is active
*is* audible immediately, but is stored under M, and switching profiles later
replays the stored set and overwrites it.

Behaviour: the editing selector defaults to the active profile. When they
diverge, the banner becomes a warning stating exactly the above. "Switch to this
profile" calls `sbx_profile_switch` and re-syncs the banner.

### Lighting
Enable switch (off → `lighting_disable()`), R/G/B 0–255 each as slider +
number input, and a colour swatch preview. On → `lighting_enable_set_rgb()`.
Debounced; one write per drag.

### System
`--dry-run`, `--debug`, persist (`--no-persist` inverted) — these are
constructor arguments to `G6Api`, so changing one rebuilds the API and returns
through the device gate. Version string. Linux only: Claim audio interface
switch (with warning), Reload audio services button.

## Error handling

- `IOError` → device gate (device gone).
- Any other exception → status bar message, app stays usable, full traceback to
  stderr. A failed write must not leave the widget showing a value the device
  never received: on failure the widget reverts to its previous value.
- `reload_audio()` shells out to `/usr/bin/usbreset` and `systemctl --user`;
  a `CalledProcessError` reports the captured stderr rather than a bare code.

## Testing

`FakeG6Api` implements the same method names and records `(method, kwargs)`
calls, letting every page be built and driven headlessly with no device. Tests:

- Each page: changing each control produces the expected API call with the
  expected arguments — including SBX passing the *editing* profile.
- Controller: debounce coalesces rapid slider changes into a single call;
  `IOError` triggers the gate callback; failures revert widget values.
- Platform gating: with `AUDIO_INTERFACE_SUPPORTED = False`, the Mixer tab is
  absent and the Audio-only rows are not built.
- Initial state: widgets populate from a supplied `G6Model`.

Tests run under the existing pytest setup, named `*_test.py` to match the
repository's convention.

## Risks

- **Toga maturity.** Spike confirmed the needed widget set exists and is native,
  but Toga 0.5.x moves fast. Pinned lower bound `>=0.5.6`.
- **No device attached during development.** The app's launch, gating and full
  test suite are verifiable without hardware; the populated tabs are not. Final
  visual confirmation requires the user to attach the G6.
- **Linux GTK dependency** is a documented install step, not a pip dependency.
