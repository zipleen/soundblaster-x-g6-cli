# Handoff — SoundBlaster X G6 GUI

Working notes for picking this up in a fresh session. Committed deliberately, so
the constraints and the hard-won gotchas survive a change of machine or context.
Delete it whenever it stops being useful.

Written 2026-09-16. Last updated 2026-09-17 (g6-re findings pass — §12, §13).

---

## 1. What this is

A Toga GUI for the Sound Blaster X G6, added to a fork of Nils Skowasch's CLI,
plus a self-contained macOS `.app`/`.dmg` build and a release workflow.

- Repo: `zipleen/soundblaster-x-g6-cli` (fork of `nils-skowasch/soundblaster-x-g6-cli`)
- Upstream code under `src/g6_cli/` is **never modified** — verify with
  `git diff f0faf3a HEAD -- src/g6_cli` (must be empty). This is deliberate and
  is the strongest argument if the GUI is ever offered upstream.

### Branches

| Branch | Meaning |
|---|---|
| `main` | Pure mirror of upstream, sitting at `f0faf3a`. Never add to it. |
| `main-gui` | The distribution branch. All GUI work lands here. Releases build from here. |
| `feature/g6-re-findings` | **Current branch.** Integrates the g6-re firmware reverse-engineering findings. Uncommitted. |
| `feature/gui-toga` | Superseded by `main-gui`; safe to delete locally and on the remote. |
| `backup/pre-reauthor` | Local safety branch from the author rewrite; delete when happy. |

Git identity for this repo is set locally to `zipleen@gmail.com` with
`commit.gpgsign false` (the only GPG key on this machine has a corsearch UID, so
signing would produce "Unverified" commits).

---

## 2. Hard constraints — do not break these

1. **Never modify `src/g6_cli/`.** Upstream code. The GUI is a client of its API.
2. **Licence: GPL-2.0-only.** Every dependency must be GPL-2.0 compatible.
   **Never add PySide6, PyQt5/6, or wxPython** — LGPLv3/GPLv3 are *incompatible*
   with GPL-2.0-only, which blocks distribution in any form, source or binary.
   Toga/travertino/rubicon-objc are BSD-3, which is why they were chosen.
   Relicensing is not available: Luis is not the copyright holder.
3. **Only run `./venv/bin/pytest tests/g6_gui`.** The pre-existing
   `tests/g6_cli` suite has **241 failures / 258 errors** that have nothing to do
   with this work — Python 3.12.14 changed argparse's error text (`choose from
   'Speakers'` → unquoted). Verified identical before and after our changes.
4. **`timeout` does not exist on macOS.** Bound commands with Python's
   `subprocess.run(..., timeout=N)` instead.
5. Never launch the GUI app in a foreground shell — it blocks forever.

---

## 2b. Versioning — three separate numbers

Do not collapse these. They mean different things.

| Number | Where | Meaning |
|---|---|---|
| `g6_cli.VERSION` | `src/g6_cli/__init__.py` | **Upstream's CLI.** 1.1.0. Never touch it. |
| `g6_gui.VERSION` | `src/g6_gui/__init__.py` | **The GUI's own.** 0.1.0. Moves when the GUI changes. |
| `version` | `pyproject.toml` (`[project]` and `[tool.briefcase]`) | **The distribution.** Names the `.app`/`.dmg` and the release tag `v<version>`. Keep in step with the GUI's. |

The GUI used to report 1.1.0 purely because it inherited upstream's number; that
was never a claim about the GUI. Both pyproject entries are now 0.1.0.

**Open item:** the published `v1.1.0` GitHub release and tag still exist. Luis
asked for them to be deleted so 0.1.0 is unambiguous, but this was deferred until
after local testing:

```bash
gh release delete v1.1.0 --cleanup-tag --yes
```

Until that runs, pushing `main-gui` publishes `v0.1.0` *alongside* `v1.1.0`.

## 3. Environment

- `venv/` — runtime venv: project installed editable (`pip install -e .`) plus
  `toga`, `pytest`, `pytest-asyncio`, `pyyaml`.
- `.build-venv/` — briefcase only, created by the build script. Both gitignored.
- After adding a **new package directory** under `src/`, re-run
  `./venv/bin/pip install -e .` or imports fail.

```bash
./venv/bin/pytest tests/g6_gui -q     # 132 tests, all passing
```

---

## 4. Architecture

```
src/g6_gui/
  __init__.py     VERSION (the GUI's own, 0.1.0), main() entry point
  help.py         every control's (i) help text — shared source with docs/
  __main__.py     entry point when running as a packaged .app
  app.py          G6App, device gate, tab assembly, parse_args/build_api/visible_pages/build_pages
  controller.py   G6Controller — all device I/O goes through this
  convert.py      label <-> enum mappings (single source of UI wording)
  native.py       finds the bundled libusb inside a .app
  platform.py     AUDIO_INTERFACE_SUPPORTED, DIRECT_MODE_SUPPORTED,
                  IS_MACOS, open_audio_midi_setup()
  coreaudio.py    macOS Core Audio HAL bindings (ctypes) + ClockController --
                  reads/sets the G6's Clock Source and stream Format directly.
                  See "macOS Audio tab" below.
  widgets.py      page/section/switch_row/slider_row/select_row/button_row/note/warning/set_enabled/
                  dynamic_note_block/dynamic_warning_block
  pages/          playback, macos_audio, mixer, recording, sbx, lighting, system
tests/g6_gui/     mirrors it; fake_api.py is the recording double for G6Api,
                  fake_coreaudio.py (FakeHal) is the recording double for coreaudio.Hal
```

### macOS Audio tab (`coreaudio.py` + `pages/macos_audio.py`)

Reads and writes the G6's Clock Source and stream Format directly through
Core Audio's public HAL (`AudioObjectGetPropertyData`/`SetPropertyData` on
`kAudioDevicePropertyClockSource` / `kAudioStreamPropertyPhysicalFormat`) --
the same API Audio MIDI Setup itself uses. This is the *actual* Direct Mode
control on macOS; the Playback tab's switch is inert there (see §6 and
docs/settings-reference.md).

- **Identifies the G6 by capability fingerprint, not by name.** No G6 was
  attached while this was built, so what Core Audio calls the device was
  never confirmed. `coreaudio.find_g6()` scans every audio device and picks
  the one whose Clock Source options are exactly `{"DSP Clock", "Stereo
  Direct"}`. Anything else is treated as not-found -- deliberately: this app
  should support exactly the G6's two documented modes, nothing more
  elaborate, per the request this was built for.
- **Automates the switch-back handoff.** Switching to DSP Clock from above
  48kHz drops the format first (prefers 48kHz at whatever bit depth is
  offered, not hard-coded to 24-bit -- see gotcha 19). Without this, switching
  back from Stereo Direct at 384kHz wedges the device, exactly as found by
  hand before this was built.
- **`ClockController.set_clock_source()`/`set_format()` raise on an
  unverified change** (`_require()` polls, then raises `TimeoutError`) rather
  than trusting that a call not raising means it worked -- Core Audio can
  accept a set() and silently not apply it (reproduced live against
  BlackHole; see gotcha 20).
- **All ctypes plumbing was validated live**, against real Core Audio devices
  on the machine this was built on (BlackHole 2ch -- a virtual driver that
  genuinely implements multiple clock sources, not just an absence check --
  plus the built-in speakers/mic), including full write/readback round trips
  and the nested `AudioStreamRangedDescription` array. **Never against a real
  G6.** See docs/settings-reference.md's "What validated means here,
  precisely" for the exact boundary of what that does and does not cover.
- Testable without any Core Audio device via `tests/g6_gui/fake_coreaudio.py`
  (`FakeHal`) -- all the decision logic (`classify_clock_sources`,
  `filter_stereo_pcm_formats`, `needs_safe_handoff`, the handoff format
  selection) is pure and tested against it in `coreaudio_test.py`.

### Contracts other code depends on

Every page module exports exactly:

```python
TITLE: str
def is_available() -> bool
def build(controller) -> toga.Widget
```

`system.build()` additionally takes `*, on_claim_changed=None` and must still
work when called as plain `build(controller)` (the contract test does that).

`widgets.*_row()` return the row **box**, with the live widget attached as an
attribute: `.switch`, `.slider` + `.readout`, `.selection`, `.buttons`.

Passing `help="..."` wraps the row in a **column** carrying an ⓘ button and a
collapsible help block. Those same attributes are copied onto the wrapper, so
callers and tests are unaffected; the inner row is `.control_row`, and the block
is `.help`. For multi-row controls use `widgets.help_for(container, anchor=...,
text=...)` so the button sits by the label while the text expands below the
group. Widgets marked `always_enabled` are skipped by `set_enabled` — that is how
ⓘ buttons stay clickable on a disabled row.

`G6Controller`:

```python
G6Controller(api, *, on_error=None, on_device_lost=None)
.model                                        # G6Model
await .call(method, **kwargs)
.submit(method, *, revert=None, on_success=None, **kwargs)
.debounced(key, method, *, delay=0.15, revert=None, **kwargs)
await .flush()                                # tests await this
.shutdown()
```

Rules: pages never touch `controller.api` directly, and slider values are always
`int(...)` before reaching the API.

---

## 5. Gotchas discovered the hard way

Every one of these cost real debugging time. They are not hypothetical.

| # | Gotcha |
|---|---|
| 1 | **`tests/__init__.py` must exist.** Without it pytest puts `tests/` on `sys.path` and `tests/g6_gui/` **shadows** `src/g6_gui`, so `from g6_gui import x` imports the test package. |
| 2 | **Toga auto-binds the widget to handlers.** Call `widget.on_press()` with **no** arguments in tests; `on_press(widget)` passes it twice → `TypeError`. |
| 3 | **Never name a box attribute `enabled`.** `toga.Widget.enabled` is a real property, so `box.enabled = row` silently stores `True` and loses the row. The lighting page uses `lighting_enabled`. |
| 4 | **`widgets.page()` returns a `_Page` whose `add()` targets the scroll column.** Plain `.add()` on the outer box would put rows *beside* a `flex=1` ScrollContainer, which expands and shoves content to the bottom behind a huge empty gap. |
| 5 | **`ScrollContainer.children` is always `[]`** — it holds a single `.content`. `set_enabled` must descend into `.content`, or disabling a whole page silently does nothing. |
| 6 | **Toga sliders return floats** (`50.0`). Cast with `int()` before any API call. |
| 7 | **Colours stringify as `rgb(255 0 0 / 1.0)`** in travertino 0.5.6 — never compare against `#ff0000`; compare to `travertino.colors.rgb(r,g,b)` by value. |
| 8 | **`slider_row`'s snap handler reassigns `slider.value`,** which re-fires `on_change`. There is a re-entry guard; keep it. |
| 9 | **`controller._spawn` falls back to `asyncio.run`** when no event loop is running. Without it, synchronous callers hit `RuntimeError`, Toga swallows the traceback, and the device write is silently dropped. |
| 10 | **`G6Api()` raises `IOError` when no device is attached — even with `--dry-run`.** Hence the device gate. |
| 11 | **GitHub Actions resolves unknown `${{ }}` to an empty string, silently.** `id: outputs` means the reference is `steps.outputs.outputs.x`. This produced a release attempt with no tag and no asset. Prefer distinct step ids and guard for empty values. |
| 12 | **Toga's Cocoa backend fires `on_change` for a *programmatic* `widget.value = x`** (`toga_cocoa/widgets/switch.py` calls `self.interface.on_change()` when the value actually changes). Repopulating controls therefore writes to the device. The SBX page guards this with `state["repopulating"]`. |
| 13 | **A test that repopulates with *identical* values proves nothing** — gotcha 12 only fires when the value differs, and the default model makes all four SBX profiles identical. A regression test must build genuinely differing profiles, or it passes whether or not the bug exists. This bit once already. |
| 14 | **`toga.Label` does not wrap.** Long text runs off the window. Pre-wrap with `textwrap` and emit one label per line — that is what `widgets.help_block` / `note_block` / `warning_block` do. |
| 15 | **Never hard-code a grey for text.** macOS dark mode inverts the background and a "muted" grey becomes unreadable. Omit `color` so the system label colour applies, as `_HELP_STYLE` does. |
| 16 | **`~/Desktop` and `~/Documents` are blocked by macOS TCC** for this process — reads fail with `EPERM` even with the sandbox disabled. Ask for files to be moved into the repo instead. |
| 17 | **No `pdftoppm`/`pypdf` on this machine.** To read a PDF, make a throwaway venv in the scratchpad and `pip install pymupdf`; `qlmanage -t` only ever renders page 1. |
| 18 | **Verify FourCC/struct constants against the actual SDK headers on disk, not memory.** `find "$(xcrun --show-sdk-path)" -iname AudioHardware*.h` locates them. Caught a real error this way: `kAudioObjectPropertyName` is `'lnam'`, not `'name'` as a first guess produced. |
| 19 | **A "safe fallback" format must not just pick the lowest available rate.** The safe-handoff logic originally hard-required 24-bit at 48kHz and fell back to the *lowest rate offered* when that exact combination wasn't available. Against BlackHole (32-bit only, no 24-bit at all) that picked **8kHz**, not 48kHz -- reproduced live before being caught. Fixed to prefer 48kHz at whatever bit depth is actually offered. See `coreaudio_test.py::test_handoff_prefers_48khz_at_whatever_bit_depth_is_actually_offered`. |
| 20 | **`AudioObjectSetPropertyData` can return success and still not apply the change.** Confirmed live: a clock-source set silently failed to take on BlackHole once (a driver quirk, not necessarily reproducible on the G6, but the underlying risk -- trusting a call that didn't raise -- is universal). `ClockController` polls and raises `TimeoutError` rather than reporting success on faith; never assume this can't happen elsewhere too. |
| 21 | **`render()`-style refresh functions must not overwrite an error message they just set.** An early version of the macOS Audio page's error handler set `status` to the failure text, then unconditionally called the normal re-render, which immediately overwrote it back to "Current: ...". Caught by a test asserting the error text was still visible after the call returned. |
| 22 | **Sample-rate/format changes in Core Audio are asynchronous; clock-source changes are not.** Confirmed by polling with a delay live: a `kAudioDevicePropertyNominalSampleRate`/physical-format set typically settles within ~100-200ms, while a clock-source set was immediate. `ClockController` polls (`SETTLE_POLL_INTERVAL`/`_ATTEMPTS`) rather than assuming either is instant. |
| 23 | **A page-to-page import (`recording.py` importing from `pages/macos_audio.py`) only worked by accident of `pages/__init__.py`'s import order** -- fragile, not caught until reasoned through carefully. Shared text belongs in `help.py`, the actual intended single source; moved there instead. |
| 24 | **A real G6 offers two variants of every format** -- ordinary and `kAudioFormatFlagIsNonMixable` (exclusive/hog mode). `Format` originally compared only (rate, bits, channels), so the two collapsed to identical dropdown entries and selecting the second of a pair silently re-applied the first. Only found once real hardware was attached; nothing in the BlackHole-based testing surfaced it, since BlackHole does not offer this. Fixed by adding `non_mixable: bool` to `Format` and labelling it `(Exclusive)`. |
| 25 | **`current_clock_source` and the stream's available-format list update on different schedules.** Confirmed live: the clock source read flips in ~20ms; the format list kept reporting the *previous* clock source's list for another 100-200ms. `set_clock_source()` must explicitly wait for the format list to change, not just for the clock source to flip, or it returns with a stale list. |
| 26 | **Real USB hardware settle timing is genuinely inconsistent, not just "slower than software."** The identical clock-source switch, run repeatedly with nothing else different, was twice observed to take over a second when it usually takes under 300ms -- no reproducible pattern found (not direction, not preceding operations). Budgeted for with a generous timeout rather than chased further; documented as real variance in `coreaudio.py`, not swept under a "should be fine" assumption. |

---

## 6. Device behaviour (documented in `docs/device-state.md`)

- Settings live **in the G6's firmware**, not in a file. They survive reboots and
  OS changes.
- `~/.soundblaster-x-g6/g6.json` is a **log of what was last sent**, never applied.
  `load_model()` runs once in `G6Api.__init__` and only fills memory.
- **~~There is no readback.~~ CORRECTED 2026-09-17 — readback exists and is
  decoded.** Every *write* is `bmRequestType=0x21` (host-to-device) and the
  single `h.read(64)` discards what comes back — but what comes back is real
  data, not just an acknowledgement. See §13. The rest of this section still
  holds: this app does not currently *use* readback, so `g6.json` can still
  silently disagree with the hardware.
- A fresh `g6.json` holds **assumed defaults**, so it can silently disagree with
  the hardware. When they differ, the device is right.
- `sbx_profile_switch()` is the **only** bulk replay in the codebase.
- **SBX trap:** `sbx_toggle`/`sbx_slider` send identical bytes regardless of the
  `profile_name` argument — the device has one live SBX state, and the profile
  only picks which row of the log is updated. So editing a non-active profile is
  audible immediately but gets overwritten on the next switch. The SBX tab warns
  about this.

### macOS platform gating — measured, not assumed

With the device attached: HID interface **available**; AudioControl reports
**"kernel is attached"**. Everything on the AudioControl interface needs the
kernel audio driver detached (`--claim-and-release`), which macOS forbids. So on
macOS the Mixer tab is hidden entirely and Playback/Recording lose their
volume/mute rows. One flag drives it: `platform.AUDIO_INTERFACE_SUPPORTED`.

---

### Settings semantics — the short version

Full detail and evidence in `docs/settings-reference.md`. The four that matter
most because they look broken but are not:

| Setting | Reality |
|---|---|
| **Direct Mode** | **Inert on macOS.** macOS asserts the USB clock selector continuously and overwrites the device. The real control is Audio MIDI Setup → Clock Source (`DSP Clock` vs `Stereo Direct`). Creative documents this (SID 200071 Q19), and Luis confirmed it by ear. The GUI disables the switch and offers an *Open Audio MIDI Setup* button. |
| **SPDIF-Out Direct** | **Unknown on macOS** — macOS's Clock Source has no third position, so it may still work. Left *enabled* deliberately: untested ≠ broken. |
| **Decoder mode** | Dolby Digital dynamic-range control. Only acts while decoding a Dolby bitstream from the **optical input** (specs say "Yes (via Optical In)"). Does nothing for PCM over USB on any OS. |
| **SBX profiles** | Slots in `g6.json`, not device presets. `profile_name` never reaches the wire; the G6 has one live SBX state. |

On the device, Direct and SPDIF-Out Direct are two positions of a **three-way**
Output Mode radio (`Audio Effects` / `Direct` / `SPDIF-Out Direct`), which is why
they are mutually exclusive. This GUI still models them as two booleans with an
exclusivity guard — the honest fix is a redesign, noted in the doc.

---

## 7. Packaging and CI

- `packaging/build-macos.sh` — `[--skip-dmg] [--identity "<ID>"] [--no-notarize]`,
  honours `PYTHON=`. Order matters: **create → build → inject libusb → package**,
  so briefcase signs the injected dylib.
- `packaging/verify-macos-app.sh` — `[--no-runtime]`. Exists because the first
  bundle ran perfectly here while quietly loading **Homebrew's** libusb; it would
  have failed on any Mac without Homebrew. It `lsof`s the running app and fails
  unless libusb came from inside the bundle. **Do not weaken this check.**
- `packaging/notarize-macos.sh` + `packaging/NOTARIZING.md` — signed build. An
  ad-hoc signature cannot be notarised after the fact, so it always rebuilds.
- `.github/workflows/macos-release.yml` — on push to `main-gui`: tests → build →
  artifact → release when `version` in `pyproject.toml` is not yet tagged.
  Notarised if `MACOS_CERTIFICATE_P12` and friends are set, otherwise unsigned;
  the mode is in the `.dmg` filename.
- Native deps: **hidapi needs nothing** (its wheel statically embeds libhidapi and
  links only system frameworks). **libusb must be injected** — pyusb loads it via
  `ctypes.util.find_library` at runtime; `g6_gui/native.py` points pyusb at the
  bundled copy.
- The macOS runner **can** launch the GUI — the runtime verification passes in CI,
  so `--no-runtime` is not needed there.

---

## 8. Verification status

| Thing | Status |
|---|---|
| GUI test suite | 176 passing |
| Real hardware (serial E5004E4F57X) | Playback, Recording, Lighting, SBX all exercised and restored; `g6.json` byte-identical to backup afterwards |
| `.app` from `/Applications` | Reached the device; loaded the **bundled** libusb; read real profile `Music`; built the 5 macOS tabs |
| CI | Green; v1.1.0 published; re-run correctly skipped re-releasing. **Not re-run since the 0.1.0 version change**, and not run at all since the macOS Audio tab was added. |
| Settings research | `docs/settings-reference.md` written from Creative KB PDFs, the packet bytes, ASR measurements, and Luis's own listening tests |
| UI help pass | ⓘ help on every control; SBX reordering; profile-switch bug fixed with a regression test verified to fail without the fix |
| Recording controls | Mic boost, noise reduction (+level), AEC, mic EQ + presets all confirmed working by ear. **Recording Smart Volume produced no audible effect** — open question, not diagnosed |
| macOS Audio tab (Core Audio mechanism) | Every operation live-tested against real Core Audio devices (BlackHole, built-in speakers/mic) with full write/readback round trips, including the `ClockController` orchestration end-to-end via a relabelled BlackHole. Two real bugs found and fixed this way (gotchas 19, 20). |
| macOS Audio tab (against a real G6) | **Confirmed working.** Core Audio calls the device `Sound BlasterX G6`; the fingerprint-based identification found it correctly anyway. Read/switch Clock Source and Format, cross-tab Recording/SBX gating, and picking up an external change made in Apple's own Audio MIDI Setup all verified live. Two real bugs found and fixed this way: duplicate "Exclusive"/ordinary format entries that were previously indistinguishable (see gotcha 24), and a stale Format list right after a clock-source switch (gotcha 25). Settle timing is real and occasionally slow (gotcha 26) -- budget increased, not chased further. |
| Released `.dmg` | Downloaded, checksum verified, mounts, signature verifies |
| **Not verified** | Mixer tab (cannot exist on macOS — needs a Linux machine), Recording/System tabs never *visually* reviewed, notarisation (needs the Developer ID Mac), Intel/universal build |

---

## 9. Seeing the UI (important for UI work)

`screencapture` is blocked by macOS screen-recording permission in this
environment. The way around it is to render the window from **inside** the app
via Cocoa. This found several layout bugs that tests could not. Save as
`/tmp/shot.py` and run with `./venv/bin/python /tmp/shot.py /tmp/out.png <tab#>`:

```python
import asyncio, sys
sys.path.insert(0, "/Users/luisf/dev/luis/soundblaster-x-g6-cli")
import toga
from g6_gui import app as app_module
from g6_gui.controller import G6Controller
from tests.g6_gui.fake_api import FakeG6Api

OUT = sys.argv[1]
TAB = int(sys.argv[2]) if len(sys.argv) > 2 else 0

class Shot(toga.App):
    def startup(self):
        self.controller = G6Controller(FakeG6Api())
        tabs, _ = app_module.build_pages(self.controller)
        self.container = toga.OptionContainer(content=list(tabs))
        self.container.style.flex = 1
        root = toga.Box(); root.style.direction = "column"; root.style.flex = 1
        root.add(self.container)
        self.main_window = toga.MainWindow(title="G6", size=(880, 640))
        self.main_window.content = root
        self.main_window.show()
        print("TABS:", [t for t, _ in tabs])
        asyncio.create_task(self.grab())

    async def grab(self):
        await asyncio.sleep(0.8)
        self.container.current_tab = TAB
        await asyncio.sleep(0.8)
        v = self.main_window._impl.native.contentView
        rep = v.bitmapImageRepForCachingDisplayInRect(v.bounds)
        v.cacheDisplayInRect(v.bounds, toBitmapImageRep=rep)
        rep.representationUsingType(4, properties={}).writeToFile(OUT, atomically=True)
        self.controller.shutdown(); self.exit()

Shot("G6", "dev.g6cli.shot").main_loop()
```

Using `FakeG6Api` means no device is needed. Swap in `app_module.G6App` with real
args to exercise the true device path (see `docs/device-state.md` for why the
device must be attached even for `--dry-run`).

Caveat: the tab strip renders oddly in these offscreen captures (unselected tabs
appear as a white block). Believed to be a `cacheDisplayInRect` artifact, not a
real defect — unconfirmed on a real screen.

---

## 10. Known open items

1. **GitHub default branch is still `main`**, so the repo landing page shows
   upstream's README with no mention of the GUI:
   `gh repo edit zipleen/soundblaster-x-g6-cli --default-branch main-gui`
2. **The published `.dmg` is unsigned** — trips Gatekeeper on download. Either add
   the CI secrets or run `packaging/notarize-macos.sh` on the Mac with the
   Developer ID.
3. **arm64 only.** Intel needs `universal_build = true` in `pyproject.toml`,
   untested.
4. **`feature/gui-toga` is redundant** — delete local and remote.
5. **Upstream contribution** was discussed but not started. The pitch: purely
   additive, zero changes to `src/g6_cli`, optional extra. Suggested approach is
   an issue first rather than a large surprise PR, given the maintainer's caution
   about USB/bricking.
6. **"Apply all saved settings" was explicitly declined** — do not build it
   without being asked again.
7. **`docs/pdfs/` is gitignored** — Creative KB articles (SID 128701, 200065,
   200066, 200071, 200074) saved as PDFs while researching. They are Creative's
   copyright, so they are deliberately not redistributed. They are the primary
   source for most of `docs/settings-reference.md`.
8. **Not yet committed.** The settings-research + UI help pass + macOS Audio
   tab are all uncommitted on `main-gui` at Luis's request, pending his own
   testing.
9. **Known-unresolved device questions** are listed in
   `docs/settings-reference.md` under *Open questions* — chiefly: does recording
   Smart Volume do anything; does SPDIF-Out Direct work on macOS; are sidetone
   and mic recording volume linked; why does a clock-source switch
   occasionally take over a second (real, reproduced, cause not found). Each
   says what would settle it.
10. **The macOS Audio tab was confirmed working against a real G6** on
    2026-09-16 -- device found, Clock Source and Format read and switched
    correctly, Recording/SBX gating confirmed live, external changes made in
    Audio MIDI Setup picked up correctly. `docs/settings-reference.md`'s
    "Confirmed against the real G6" section has the details.
11. UI polish never reviewed on a real screen: Mixer (Linux only), Recording,
    System tabs. macOS Audio *has* now been reviewed live.
12. **macOS Audio is now the first tab**, not tucked after Playback -- it is
    the actual Direct Mode control on macOS and the most consequential
    setting on the device.

---

## 11. Docs map

| File | Contents |
|---|---|
| `docs/settings-reference.md` | **What every setting does**, with confidence markers, the packet-level evidence, and the open questions. The source for the ⓘ help text. |
| `docs/gui.md` | Using the GUI, running the dev version, tab map, why macOS shows less |
| `docs/device-state.md` | `g6.json`, no readback, SBX semantics |
| `docs/macos-cli.md` | Terminal-only setup (no Cython/CFLAGS needed any more) |
| `packaging/README.md` | Build, verify, signing overview |
| `packaging/NOTARIZING.md` | Developer ID steps + CI secrets |
| `docs/superpowers/specs/2026-09-15-gui-toga-design.md` | Original design + licence reasoning |
| `docs/superpowers/plans/2026-09-15-gui-toga.md` | Implementation plan (13 tasks) |



---

## 12. The g6-re findings pass — branch `feature/g6-re-findings`

Integrates <https://github.com/HyperRamzey/g6-re> (firmware + Windows-app
reverse engineering). Its clone at `docs/g6-re/` is **excluded via
`.git/info/exclude`**: it has its own `.git`, it is someone else's work, and
nothing of theirs is redistributed — the docs cite it by URL with credit.

Evidence convention used throughout `docs/`: **[TESTED]** = observed on real
hardware by this project, dated. **[INFERRED]** = everything else, including
firmware disassembly, third-party measurements and USB captures recorded by
others. Only two buckets, deliberately.

### What shipped in the GUI

Modest, and worth being honest about — 263 lines across three pages:

| Tab | Change |
|---|---|
| macOS Audio | Output Volume and Output Channels rows; full-scale distortion warning |
| Playback | NOS filter (5th, hidden by Creative) + warning when selected; 7.1 explanation on the channel rows |
| System | "Device information" section — USB descriptor revision, product, serial |

Plus `src/g6_device/` (passive descriptor reads), `src/g6_gui/filters.py`, help
text rewrites, and `experimental/` (diagnostic scripts, not part of the app).

Tests: 176 -> **272**. `src/g6_cli` still byte-identical to upstream.
`src/g6_device/` is a new package, so **re-run `./venv/bin/pip install -e .`**
after checkout or imports fail.

### The findings

| Finding | Status |
|---|---|
| Full-scale distortion (~1% THD at 20 Hz at 0 dBFS, fixed by -2 dB) is real and permanent — every firmware gain constant is byte-identical 2019-2025 | [INFERRED] — ASR measured it, g6-re disassembled it |
| Direct Mode is firmware-enforced: the MCU stops writing effect registers; only master volume survives | [INFERRED] — disassembly |
| Virtual 7.1 renders **inside the device**, which is why Direct Mode kills it | [INFERRED] — disassembly |
| A hidden 5th DAC filter (NOS) exists; Creative's app skips it by name | [INFERRED] — wire payload `0003` never sent by us |
| macOS: G6 offers **2 channels, 8 formats, zero non-stereo** — 7.1 genuinely unavailable | **[TESTED]** 2026-09-17 |
| macOS: volume is exposed **per-channel only** (`'volm'` elements 1/2; no `'vmvc'`, no master) | **[TESTED]** 2026-09-17 |
| Firmware version cannot be read — the device refused all nine probe frames | **[TESTED]** 2026-09-17 |

Detail lives in `docs/settings-reference.md`, `docs/firmware-findings.md`,
`docs/device-state.md` and `docs/hid-probe-findings.md`.

### Gotchas that cost real time

| # | Gotcha |
|---|---|
| 27 | **`PlaybackFilter` cannot be extended, even dynamically.** `Playback.from_dict` does `PlaybackFilter[name]` and raises on an unknown name, and `g6.json` is **shared with the upstream CLI** — persisting `NON_OVERSAMPLING` would crash the plain CLI on `load_model()`. The NOS shim in `filters.py` deliberately never reaches the model. |
| 28 | **`G6Model.set_filter()` isinstance-checks the enum** and raises *after* the HID write has gone out. Hence `G6Controller.submit(..., tolerate=(ValueError,))`, used **only** for the NOS shim and scoped by identity, never by exception type alone. |
| 29 | **`xcrun --show-sdk-path` may point at the Command Line Tools SDK, which has no `AudioHardware*.h` at all.** Verify Core Audio constants against Xcode's SDK. Extends gotcha 18. |
| 30 | **`_DynamicTextBlock.set_text()` clears all its own children.** Anchoring an (i) button on a dynamic block deletes it on first update — anchor on a wrapping row. |
| 31 | **The Filter row had no `revert`**, so a device failure silently left the dropdown lying. Adding one needed the gotcha-12 re-entry guard. |
| 32 | **`DataFragmentMode.COMMIT = '1103'` is misnamed upstream — it is a READ REQUEST.** The write's real acknowledgement is a separate `02 0A` frame. Do not "fix" it: `src/g6_cli` is frozen and SBX works. |
| 33 | **Trust `payloads/raw/*.pcapng` over `doc/usb-spec.md`.** The spec's HID rows have no direction column, which is how read and write roles got muddled. `doc/usb-protocol.md` is generic ChatGPT-written USB background — nothing G6-specific. |

### Two beliefs this pass corrected

1. **7.1 on macOS is not blocked by the AudioControl claim gate.** That gate is
   real and is why the Mixer tab is hidden, but it is not what stops 7.1.
   Nobody has a working channel-count command on *any* OS: this project's
   `speakers_to_7_1()` literally returns `speakers_to_stereo()`, and on Windows
   the count is a driver registry property.
2. **Readback exists.** §6's old "there is no readback" was wrong — see §13.

### Firmware version: cannot be read

`tools/G6HidProbe` is Windows-only; `GetFirmwareVersionString` is a call into
Creative's proprietary COM DLL, **not a wire frame**, so the request was never
captured. `src/g6_device/` therefore ships only passive descriptor reads,
labelled **USB device revision** — a 16-bit BCD field that cannot hold
`2.1.250903.1324`. The device **[TESTED]** refuses command `0xE0`.

---

## 13. The control protocol, and why readback was not built

Decoded from `payloads/raw/*.pcapng` **[INFERRED]** — real captured traffic,
but recorded by upstream, not reproduced by us against the device.

Mechanics: host frames are HID `SET_REPORT` control transfers whose captured
payload *includes* the 8-byte setup (`21 09 ...`), so the 64-byte report starts
at **offset 8** — scanning for `0x5A` at offset 0 finds nothing. Device frames
arrive as 64-byte **interrupt** transfers on endpoint **0x85**. Direction is in
the USBPcap header's `info` bit 0. There is no tshark or scapy here; parsers
were written from the pcapng/USBPcap specs.

Frame: `5A | mode(2) | intermediate(2) | audio_feature(1) | value(4) | padding`

| mode | Direction | Meaning |
|---|---|---|
| `12 07` | host -> device | WRITE a DSP register |
| `11 03` | host -> device | READ REQUEST |
| `11 08` | device -> host | READ RESPONSE, carries the value |
| `02 0A` | device -> host | ACK: `5A 02 0A <cmd> <status>` |

`intermediate` is `01 <family>`; families `0x95`/`0x96`/`0x97` are the
firmware's op-149/150/151 register engines, matching g6-re's disassembly.
`audio_feature` is the register index. Status `0x00` = OK in all 31 captured
ACKs; `0x81` = rejection is **[INFERRED] from contrast — no capture contains a
failure**.

Proof, from `g6-recording-acoustic-echo-cancellation.pcapng`:

```
HOST -> DEV   5a 12 07 01 95 00 | 00 00 80 3f    write family 0x95 idx 0 = 1.0f
DEV  -> HOST  5a 02 0a 12 00 ...                 ACK, status 0x00
HOST -> DEV   5a 11 03 01 95 00 | 00 00 00 00    read request
DEV  -> HOST  5a 11 08 01 00 95 00 | 00 00 80 3f read response = 1.0f
```

This app already sends `1103` read requests constantly — `sbx.py`,
`recording.py` and `decoder.py` follow every DATA frame with a COMMIT carrying
the same family and index — and discards the answers in `h.read(64)`.

### The decision: not built

A readback feature was designed (read device state to `current.json`, diff it
against `g6.json` in the System tab, Apply only the differences, limited to
readable families, paced ~0.3 s) and then **deliberately not built**.

Luis's reasoning, 2026-09-17: adding unknown USB code is not obviously right for
an app that already fulfils its purpose at 0.2.1, particularly when upstream
does not track this protocol and there is exactly one G6 with no replacement.

**This is a closed decision, not a backlog item.** Do not start it without being
asked again. The design notes above are kept so the reasoning is not lost, and
`experimental/probe-g6-hid.py` remains as the read-only way to explore further.

Also declined earlier and still declined: "apply all saved settings" (§10.6).
