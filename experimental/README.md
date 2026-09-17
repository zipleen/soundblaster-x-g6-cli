# experimental/

Diagnostic and research scripts for **this fork only**. Nothing here is part of
the application, nothing imports from here, and nothing here runs as part of the
build or the test suite. The directory exists so this fork's exploratory work
stays clearly separated from upstream's tree.

Everything here is standalone and safe to delete.

| Script | What it does | Writes to the device? |
|---|---|---|
| `verify-coreaudio-volume.py` | Dumps every Core Audio device, its volume properties and its full format list. Read-only. | No |
| `probe-g6-hid.py` | Sends HID **read** requests and reports the replies. Dry-run unless `--send`. | No (unless `--baseline`) |
| `thd-test-macos.py` | THD+N loopback measurement. Needs `numpy`, `sounddevice`, a cable and a separate recording input. | No |

See `README-thd-test.md` for the measurement setup, and
`../docs/hid-probe-findings.md` for what the HID probe found.

## Safety

`probe-g6-hid.py --baseline` performs a real **write**: it re-selects a DAC
filter. Because the filter cannot be read back, it sets whatever
`--baseline-filter` says regardless of what was there. Reversible from the
Playback tab, but it changes a setting — so it is opt-in, never a default.

Run the read-only form first:

```bash
./venv/bin/python experimental/probe-g6-hid.py --send
```
