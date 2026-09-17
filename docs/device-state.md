# How settings are stored: the G6, and `g6.json`

This explains where your settings actually live, what
`~/.soundblaster-x-g6/g6.json` is for, and why it can disagree with your device.

## Evidence convention

**[TESTED]** = observed on real hardware by this project, with a date.
**[INFERRED]** = everything else (captured USB traffic, reasoning) — evidence
named inline.

## The short version

| Question | Answer |
|---|---|
| Does `g6.json` get applied to the device? | **No.** Nothing ever reads it and sends it to the G6. |
| Do I need to run the app/CLI once to apply my settings? | **No.** Running it applies nothing at all. |
| Where do my settings actually live? | **In the G6 itself.** It keeps them across reboots and operating systems. |
| When are settings sent? | Only at the moment you change one option. Each change is its own packet. |
| Can current settings be read back from the device? | The protocol supports register readback (**[INFERRED]**, from captured USB traffic — see below), but this app never uses it. |

## What `g6.json` really is

A **log of what was last sent**, not a configuration that gets applied. Every
setter in `G6Api` does: send to the G6 → update the in-memory model →
`save_model()`. The file is written *after* a successful send, to record it.
`load_model()` runs once, in `G6Api.__init__`
(`src/g6_cli/g6_api/__init__.py:87`), and only populates the in-memory
object — nothing pushes it back to the hardware. Its only job is answering
"what did I set last time?", which is what lets the GUI draw sliders in
roughly the right place.

Pass `--no-persist` to skip reading/writing it entirely.

## Where settings really live, and when they're sent

In the device: the G6 keeps its own state in firmware, which is why settings
made in Creative's Windows software survive a reboot into Linux or macOS.
This app's design depends on that — it never reads the device or re-applies
anything on startup.

Settings are sent only when you change something, and only the thing you
changed — e.g. moving the bass slider sends only the bass value. The one
exception: `soundblaster-x-g6-cli --sbx-profile-switch <name>`
(`sbx_profile_switch()`, `src/g6_cli/g6_api/__init__.py:700`) reads the ten
stored SBX values for a profile and replays all of them.

**SBX consequence:** the device holds exactly one live SBX state, so
`sbx_toggle()`/`sbx_slider()` send identical data regardless of which profile
is named — the profile argument only picks which row of the *log* gets
updated. Editing profile M while profile G is active is audible immediately
but recorded under M; the next profile switch replays G's stored set and
overwrites the audible change. The GUI's SBX tab warns when the profile being
edited isn't the active one.

## The control protocol, and why readback is real but unused

Frame shape: `5A | mode(2) | intermediate(2) | audio_feature(1) | value(4) | padding`.

| mode | Direction | Meaning |
|---|---|---|
| `12 07` | host → device | WRITE a DSP register |
| `11 03` | host → device | READ REQUEST |
| `11 08` | device → host | READ RESPONSE, carries the value |
| `02 0A` | device → host | ACK: `5A 02 0A <cmd> <status>` |

**[INFERRED]** (captured USB traffic in `payloads/raw/*.pcapng`, recorded by
upstream for unrelated reasons, not reproduced by this project against the
device) — decisive example, from `g6-recording-acoustic-echo-cancellation.pcapng`:

```
HOST->DEV  5a 12 07 01 95 00 | 00 00 80 3f    write family 0x95 idx 0 = 1.0f
DEV->HOST  5a 02 0a 12 00 ...                 ACK cmd 0x12, status 0x00
HOST->DEV  5a 11 03 01 95 00 | 00 00 00 00    read request
DEV->HOST  5a 11 08 01 00 95 00 | 00 00 80 3f read response = 1.0f
```

`intermediate` is `01 <family>`: `0x95` recording, `0x96` playback, `0x97`
decoder (per `DataFragmentStatic`). Only `0x95` is seen issuing reads in this
repo's captures; `0x96`/`0x97` are documented the same way and match the
independent g6-re firmware disassembly, but no capture exercises a read on
either — whether readback covers every family is unconfirmed. Full mode
tallies and tier structure built on this are in
[`hid-probe-findings.md`](hid-probe-findings.md).

Mechanically, both WRITE and READ REQUEST are HID `SET_REPORT` control
transfers (`bmRequestType = 0x21`, `src/g6_cli/g6_spec/__init__.py:80`); the
ACK and read response arrive as 64-byte interrupt transfers on endpoint
`0x85` — exactly what the single `h.read(64)` in `src/g6_cli/g6_core.py:332`
reads. It has been receiving real data all along; **this app only ever
prints it under `--debug` and never parses it.** `DataFragmentMode.COMMIT`
(hex `1103`, sent after almost every write in `sbx.py`/`recording.py`/`decoder.py`)
is misleadingly named — it is the READ REQUEST above, not a commit step; the
write's real acknowledgement is the separate `02 0A` ACK that arrives first.

**Separately, firmware-version readback (command `0xE0`) is [TESTED] as
refused.** 2026-09-17, real G6: nine `5A E0 01 <n>` frames (n = 1..9) all
returned a byte-identical `5a 02 0a e0 81 ...`; no firmware version was
obtained. This is a different address space from the DSP-register readback
above — register readback is confirmed working; firmware-version readback is
not. Full detail in [`hid-probe-findings.md`](hid-probe-findings.md).

**This app does not use any of this, and that is a decision, not a TODO.**
Building a read path would mean sending USB codes this codebase doesn't
currently send, on top of `src/g6_cli`, which is frozen; it was considered
and deliberately not built, since this app already fulfils its purpose
without it and upstream (g6-re) doesn't track this readback either. Nothing
here compares device state to `g6.json`; a fresh `g6.json` still holds
assumed defaults, and the file and hardware can still silently disagree with
no code path to notice.

**Not an exception:** the System tab's device-info row is the USB
`bcdDevice` descriptor (cached at enumeration by hidapi/pyusb), not the audio
firmware's version — reading it sends nothing to the device and it can't
represent a version like `2.1.250903.1324`. See `src/g6_device/info.py` and
`src/g6_gui/pages/system.py`'s `DEVICE_INFO_NOTE`.

## Why the file can be wrong

A fresh `g6.json` contains assumed defaults, not observed state:

| | Fresh default | Reality on a device you've used |
|---|---|---|
| Lighting | off, RGB(0,0,0) | whatever colour it's actually showing |
| Active SBX profile | `Gaming` | whatever you last switched to |
| Playback filter | `FAST_ROLL_OFF_MINIMUM_PHASE` | whatever you last chose |

Nothing in this app can detect this drift — not because the protocol has no
way to ask (it does, see above), but because nothing here asks. This happens
whenever settings change from another machine, OS, Creative's own software,
or after the file is deleted. This is why the GUI presents values as *last
known state*, not as a live query.

**Practical consequences:**

- Deleting `g6.json` does not change your device — it only makes the UI forget.
- Copying `g6.json` between machines does not transfer settings to the device.
- If the UI disagrees with what you hear, the **device** is right; changing
  the control to the value already shown will make the file catch up.
