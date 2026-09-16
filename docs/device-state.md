# How settings are stored: the G6, and `g6.json`

This explains where your settings actually live, what
`~/.soundblaster-x-g6/g6.json` is for, and why it can disagree with your device.

It matters because the answers are not what most configuration files lead you to
expect.

## The short version

| Question | Answer |
|---|---|
| Does `g6.json` get applied to the device? | **No.** Nothing ever reads it and sends it to the G6. |
| Do I need to run the app/CLI once to apply my settings? | **No.** Running it applies nothing at all. |
| Where do my settings actually live? | **In the G6 itself.** It keeps them across reboots and operating systems. |
| When are settings sent? | Only at the moment you change one option. Each change is its own packet. |
| Can the current settings be read back from the device? | **No.** There is no inbound path in the protocol as implemented. |

## What `g6.json` really is

It is a **log of what was last sent**, not a configuration that gets applied.

Every setter in `G6Api` follows the same order:

```
send data to the G6  →  update the in-memory model  →  save_model()
```

The file is written *after* a successful send, to record what was sent.
`load_model()` is called in exactly one place — `G6Api.__init__`
(`src/g6_cli/g6_api/__init__.py:87`) — and all it does is populate an in-memory
object. No code path reads that object and pushes it to the hardware.

So the file exists to answer "what did I set last time?", which is what lets the
GUI draw its sliders in roughly the right places. That is its only job.

Pass `--no-persist` to skip reading and writing it entirely.

## Where the settings really live

In the device. The G6 keeps its own state in firmware, which is why settings
made in Creative's Windows software are still in effect after rebooting into
Linux or macOS without touching anything.

The tool's design depends on this being true: it never reads the device and
never re-applies anything on startup, which only works because the hardware
remembers.

## When settings are sent

Only when you change something, and only the thing you changed. Setting the bass
slider sends the bass value and nothing else.

There is exactly **one** bulk operation in the whole codebase:

```bash
soundblaster-x-g6-cli --sbx-profile-switch Music
```

`sbx_profile_switch()` (`src/g6_cli/g6_api/__init__.py:700`) reads the ten stored
SBX values for that profile out of the model and replays them all to the device.
Nothing else replays anything, and there is no "apply everything in the file"
command.

### The SBX consequence

Because the device holds exactly **one** live SBX state, `sbx_toggle()` and
`sbx_slider()` send identical data no matter which profile you name. The profile
argument only selects which row of the *log* gets updated.

So editing profile M while profile G is active **is audible immediately**, but is
recorded under M — and the next profile switch replays that profile's stored set
and overwrites it. The GUI's SBX tab warns about this when the profile you are
editing is not the active one.

## There is no readback

Verified against the implementation:

- Every USB control transfer uses `bmRequestType = 0x21`
  (`src/g6_cli/g6_spec/__init__.py:80`) — that is *host-to-device*, class
  request, interface recipient. Outbound only.
- The single `h.read(64)` after a HID write (`src/g6_cli/g6_core.py:332`) drains
  the device's acknowledgement and discards it; the value is only printed under
  `--debug` and is never parsed.

Nothing anywhere asks the G6 what its current settings are.

## Why the file can be wrong

A fresh `g6.json` contains **assumed defaults, not observed state**, because the
device was never asked. On a machine where the file has been deleted, you get:

| | Fresh default | Reality on a device you have been using |
|---|---|---|
| Lighting | off, RGB(0,0,0) | whatever colour it is actually showing |
| Active SBX profile | `Gaming` | whatever you last switched to |
| Playback filter | `FAST_ROLL_OFF_MINIMUM_PHASE` | whatever you last chose |

The file and the hardware can drift apart, and **nothing can detect it** — there
is no readback to compare against. This happens whenever settings are changed
from another machine, another OS, Creative's own software, or after the file is
deleted.

This is why the GUI presents these values as *last known state* rather than
implying it queried the device.

### Practical consequences

- Deleting `g6.json` does not change your device. It only makes the UI forget.
- Copying `g6.json` between machines does not transfer settings to the device.
- If the UI disagrees with what you hear, the **device** is right. Change the
  control to the value you want — even to the value already shown — and the file
  catches up.
