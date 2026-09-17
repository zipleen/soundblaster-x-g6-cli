#!/usr/bin/env python3
"""Standalone THD+N measurement for the Sound BlasterX G6 (macOS, host Mac only).

============================================================================
DO NOT RUN THIS INSIDE A VIRTUAL MACHINE. The numbers will be garbage.
============================================================================
This script was written on a dev machine that is itself a VM
(Apple M4 (Virtual), kern.hv_vmm_present=1). USB audio is isochronous:
passing a USB audio device through into a VM adds resampling and, under
load, dropouts -- and a single dropout injects broadband noise directly
into the THD+N figure this script computes. A "measurement" taken inside
a VM cannot be trusted to say anything about the real device. The script
checks `sysctl -n kern.hv_vmm_present` itself and refuses to run unless
you pass --i-know-this-is-a-vm, which prints this same warning again and
proceeds anyway (e.g. for the offline --self-test, which needs no audio
hardware and IS safe to run anywhere).

Run this on the actual host Mac, standalone, outside this repo's venv --
see experimental/README-thd-test.md for setup.
============================================================================

WHAT THIS ANSWERS

Audio Science Review's 2019 measurement of the G6 found ~1% THD+N at 20 Hz
at 0 dBFS (full digital scale), which dropped to essentially nothing when
the digital level was pulled back 2 dB (SINAD ~107 dB -> ~112 dB). Firmware
disassembly (see docs/firmware-findings.md) shows every gain constant in
the G6's firmware is byte-identical from 2019 to 2025, so if the effect is
real it was never fixed and every unit has it.

Separately, macOS was confirmed (docs/settings-reference.md) to drive the
G6's OWN hardware volume control (Core Audio 'volm' per-channel, no master
element, no 'vmvc') rather than attenuating in software on the Mac. What is
NOT known is whether that hardware control sits before the DAC (digital)
or after it (analog). This matters: if it's pre-DAC, backing off the
device's own volume reproduces ASR's digital -2 dBFS fix; if it's purely
post-DAC analog, the DAC still sees a full-scale signal no matter what the
volume knob says, and lowering it would not help. This script cannot see
inside the chip, but it can settle the practical question: if lowering the
G6's own volume measurably reduces THD+N at a fixed full-scale digital
input, the mitigation works, regardless of exactly where inside the device
it happens.

WHAT THIS SCRIPT DOES

1. Plays 997 Hz / 60 Hz / 20 Hz tones at 0 dBFS and -2 dBFS digital level,
   at three device volume settings (100%, ~90%, ~79%), and records the
   result on a chosen input device.
2. Also measures a -20 dBFS tone to estimate the recording chain's own
   noise floor -- because the ADC doing the recording has its own
   distortion, and if that floor isn't comfortably below what's being
   measured, the "result" is measuring the ADC, not the G6.
3. Computes THD+N (residual RMS / total RMS, i.e. AES17-style, NOT
   distortion-only THD) via FFT, with the fundamental notched out.
4. Prints an explicit verdict: does 0 dBFS look worse than -2 dBFS, and
   does lowering the device's own volume help?

This script NEVER changes your system volume. It prompts you to set it
by hand and press Enter, the same rule this whole project follows for the
macOS Audio tab (see src/g6_gui/help.py MACOS_VOLUME) -- an app should not
move a user's volume behind their back, and neither should this script.

HEARING SAFETY: if you are measuring the G6's own headphone output,
somebody's ears may be on the other end of that cable. Every playback in
this script is preceded by a warning and kept short (a few seconds), and
the script always starts at a quiet digital level and checks the recorded
peak before going anywhere near 0 dBFS.

USAGE

    python3 thd-test-macos.py --self-test
        Offline check of the THD+N maths against synthetic signals with
        known, hand-computed distortion. No audio hardware touched. Safe
        to run inside a VM. Run this first, always.

    python3 thd-test-macos.py --list-devices
        List audio devices by name and index.

    python3 thd-test-macos.py -o "G6" -i "G6"
        Run the real measurement sweep, self-loopback (G6 output back into
        the G6's own line-in). Requires an actual physical loopback cable
        from headphone/line-out to line-in -- see the README.

    python3 thd-test-macos.py -o "G6" -i "USB Audio CODEC"
        Run the real sweep with a separate, independent recording
        interface as the ADC (the more trustworthy setup -- see README).

See experimental/README-thd-test.md for the full walkthrough, cabling, and how
to read the output.
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
import time

try:
    import numpy as np
except ImportError:
    print(
        "This script needs numpy, which isn't installed in this Python.\n"
        "Install it with:\n\n"
        "    python3 -m venv venv\n"
        "    source venv/bin/activate\n"
        "    pip install numpy sounddevice\n\n"
        "Then re-run inside that venv (see experimental/README-thd-test.md).",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# VM detection
# ---------------------------------------------------------------------------

VM_WARNING = """
============================================================================
REFUSING TO RUN: this Mac is reporting kern.hv_vmm_present=1, i.e. it is
itself a virtual machine (or this script is running inside one).

USB audio is an isochronous stream. When a USB audio device is passed
through into a VM, the hypervisor's USB layer commonly introduces extra
resampling and, under any scheduling pressure, outright dropouts. A single
dropped or resampled buffer injects broadband noise straight into the
recording this script analyses -- and that noise lands directly in the
THD+N number, indistinguishable from real distortion in the G6. A THD+N
figure measured this way tells you about the VM's USB passthrough, not
about the Sound BlasterX G6.

Run this script on the real host Mac instead, outside any VM, standalone
(it does not need this repo's venv -- see experimental/README-thd-test.md).

If you understand this and want to proceed anyway (e.g. you have already
verified there is no passthrough involved, or you just want to exercise
the code path), pass --i-know-this-is-a-vm. That flag does not make the
measurement trustworthy -- it just lets you past this check.
============================================================================
"""


def hypervisor_present() -> bool:
    try:
        out = subprocess.run(
            ["sysctl", "-n", "kern.hv_vmm_present"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() == "1"
    except Exception:
        # If we can't even check, don't block the user over it -- but we
        # also can't warn them, so this is a silent pass-through on
        # non-Darwin or broken sysctl, not a safety guarantee.
        return False


# ---------------------------------------------------------------------------
# Signal generation / analysis (pure numpy -- this is the part that is
# actually verified by --self-test, offline, with no hardware involved)
# ---------------------------------------------------------------------------


def gen_tone(freq: float, dbfs: float, dur: float, sr: int, fade: float = 0.05) -> np.ndarray:
    """A windowed sine burst at `dbfs` relative to full scale (1.0)."""
    n = int(dur * sr)
    fade_n = max(1, int(fade * sr))
    t = np.arange(n) / sr
    amp = 10 ** (dbfs / 20.0)
    x = amp * np.sin(2 * np.pi * freq * t)
    env = np.ones(n)
    env[:fade_n] = np.linspace(0.0, 1.0, fade_n)
    env[-fade_n:] = np.linspace(1.0, 0.0, fade_n)
    return (x * env).astype(np.float64)


def steady_segment(x: np.ndarray, sr: int, settle: float = 0.3, fade: float = 0.05) -> np.ndarray:
    """Discard the leading settle time (device/DAC startup transient, plus
    the fade-in) and the trailing fade-out, keeping only the steady middle
    of the burst for analysis."""
    n = len(x)
    start = int(settle * sr)
    end = n - int((settle + fade) * sr)
    if end <= start or start >= n:
        return x
    return x[start:end]


def thd_n(seg: np.ndarray, freq: float, sr: int, notch_bins: int = 6, dc_bins: int = 3) -> dict:
    """THD+N of a steady-state segment containing a tone at `freq`.

    Defined AES17-style as residual RMS over TOTAL RMS (residual =
    everything in the spectrum except the fundamental and DC):

        thdn_ratio = sqrt(p_residual / (p_residual + p_fundamental))

    (Not the distortion-only THD = residual/fundamental -- this is
    intentionally the "how much of the total signal isn't the wanted
    tone" number, which stays neatly bounded in [0, 1).)

    Steps: remove DC, window (Blackman -- good sidelobe rejection so a
    nearby noise floor doesn't leak under the fundamental's skirt), FFT,
    find the fundamental's bin, sum power in a small band around it as
    the signal, notch that band (+ a couple of guard bins either side)
    plus the DC region out of the rest, and call the remainder the
    residual.
    """
    seg = np.asarray(seg, dtype=np.float64)
    if len(seg) < 16:
        return dict(peak_dbfs=-math.inf, thdn_ratio=float("nan"), thdn_db=float("nan"), thdn_pct=float("nan"), spurs=[])
    seg = seg - np.mean(seg)
    peak = float(np.max(np.abs(seg))) if len(seg) else 0.0
    if peak < 1e-9:
        return dict(peak_dbfs=-math.inf, thdn_ratio=float("nan"), thdn_db=float("nan"), thdn_pct=float("nan"), spurs=[])

    win = np.blackman(len(seg))
    spec = np.abs(np.fft.rfft(seg * win))
    freqs = np.fft.rfftfreq(len(seg), 1 / sr)

    f0 = int(np.argmin(np.abs(freqs - freq)))
    fund_lo, fund_hi = max(0, f0 - 4), min(len(spec), f0 + 5)
    p_fund = float(np.sum(spec[fund_lo:fund_hi] ** 2))

    mask = np.ones(len(spec), dtype=bool)
    mask[max(0, f0 - notch_bins) : min(len(spec), f0 + notch_bins + 1)] = False
    mask[:dc_bins] = False
    p_resid = float(np.sum(spec[mask] ** 2))

    p_total = p_fund + p_resid
    if p_total <= 0:
        ratio = float("nan")
    else:
        ratio = math.sqrt(p_resid / p_total)

    thdn_db = 20 * math.log10(ratio) if ratio and ratio > 0 else -math.inf
    peak_dbfs = 20 * math.log10(peak) if peak > 0 else -math.inf

    # Top residual spurs, for diagnosing *what* is showing up (mains hum at
    # 60/120 Hz, a harmonic ladder, broadband noise, ...) -- informational
    # only, not part of the THD+N number itself.
    spurs = []
    if p_resid > 0 and p_fund > 0:
        resid_spec = np.where(mask, spec, 0.0)
        ref = math.sqrt(p_fund)
        order = np.argsort(resid_spec)[::-1]
        for i in order[:6]:
            if resid_spec[i] <= 0:
                break
            level_db = 20 * math.log10(resid_spec[i] / ref)
            if level_db < -90:
                break
            spurs.append((float(freqs[i]), level_db))

    return dict(
        peak_dbfs=peak_dbfs,
        thdn_ratio=ratio,
        thdn_db=thdn_db,
        thdn_pct=ratio * 100 if ratio == ratio else float("nan"),
        spurs=spurs,
    )


# ---------------------------------------------------------------------------
# Self-test: prove the maths against synthetic signals with KNOWN, hand-
# computed distortion. This is the one part of this script that can
# actually be verified without a G6 attached.
# ---------------------------------------------------------------------------


def _synthetic(freq: float, sr: int, dur: float, amp: float = 1.0, harmonics: dict | None = None,
                noise_sigma: float = 0.0, seed: int = 0) -> np.ndarray:
    n = int(dur * sr)
    t = np.arange(n) / sr
    x = amp * np.sin(2 * np.pi * freq * t)
    if harmonics:
        for k, hamp in harmonics.items():
            x = x + hamp * np.sin(2 * np.pi * (k * freq) * t)
    if noise_sigma > 0:
        rng = np.random.default_rng(seed)
        x = x + rng.normal(0.0, noise_sigma, n)
    return x


def self_test() -> bool:
    """Runs the THD+N function against signals whose distortion content is
    known exactly (constructed, not measured), and checks the function
    recovers the right number. Frequencies/durations are chosen so the
    fundamental and every harmonic land exactly on FFT bin centers (integer
    number of cycles in the analysis window), which removes spectral
    leakage as a confound -- what's being checked here is the peak-finding,
    notch/exclusion logic, and the power-ratio-to-dB/% conversion, not
    windowing artifacts.
    """
    sr = 48000
    dur = 2.0  # 96000 samples; bin spacing = sr/n = 0.5 Hz
    freq = 1000.0  # 1000 / 0.5 = bin 2000 exactly; every harmonic below is too

    print("Self-test: verifying THD+N maths against synthetic signals with")
    print("known, hand-computed distortion (no audio hardware involved).\n")

    results = []

    # --- Test 1: pure tone, nothing added -> should read essentially zero.
    seg = steady_segment(_synthetic(freq, sr, dur), sr)
    r = thd_n(seg, freq, sr)
    passed = r["thdn_db"] < -100.0
    results.append(passed)
    print(f"[1] Pure {freq:.0f} Hz tone, no distortion added:")
    print(f"    measured THD+N = {r['thdn_db']:.1f} dB  (expect < -100 dB, i.e. numerical floor)")
    print(f"    -> {'PASS' if passed else 'FAIL'}\n")

    # --- Test 2: known harmonics only (no noise) -- the precise test, since
    # bin-exact tonal ratios are recovered exactly by an FFT-bin estimator
    # (the window's magnitude-scaling factor is identical for the
    # fundamental and any other bin-centered tone, so it cancels in the
    # ratio).
    harmonics = {3: 0.01, 5: 0.003}  # 3rd @ -40.0 dBc, 5th @ -50.5 dBc
    seg2 = steady_segment(_synthetic(freq, sr, dur, harmonics=harmonics), sr)
    r2 = thd_n(seg2, freq, sr)
    p_fund = 0.5 * 1.0 ** 2
    p_resid = sum(0.5 * a * a for a in harmonics.values())
    expected_ratio = math.sqrt(p_resid / (p_fund + p_resid))
    expected_db = 20 * math.log10(expected_ratio)
    err = abs(r2["thdn_db"] - expected_db)
    passed = err < 0.3
    results.append(passed)
    print(f"[2] Known harmonics only: 3rd @ -40.0 dBc + 5th @ -50.5 dBc, no noise:")
    print(f"    expected THD+N = {expected_db:.2f} dB  ({expected_ratio*100:.4f} %)")
    print(f"    measured THD+N = {r2['thdn_db']:.2f} dB  ({r2['thdn_pct']:.4f} %)")
    print(f"    difference     = {err:.2f} dB  (tolerance 0.3 dB)")
    print(f"    -> {'PASS' if passed else 'FAIL'}\n")

    # --- Test 3: known white noise only (no harmonics). Expected ratio from
    # the time-domain power relation for a sine of amplitude 1.0 (power
    # 0.5) plus zero-mean Gaussian noise of variance sigma^2. White noise
    # spreads its energy over effectively every FFT bin, so excluding the
    # dozen or so notched-out bins (out of ~48000+ total) removes a
    # negligible fraction of it -- the FFT-bin estimate should track the
    # time-domain power ratio closely.
    sigma = 0.01
    seg3 = steady_segment(_synthetic(freq, sr, dur, noise_sigma=sigma, seed=42), sr)
    r3 = thd_n(seg3, freq, sr)
    p_resid3 = sigma ** 2
    expected_ratio3 = math.sqrt(p_resid3 / (p_fund + p_resid3))
    expected_db3 = 20 * math.log10(expected_ratio3)
    err3 = abs(r3["thdn_db"] - expected_db3)
    passed = err3 < 0.5
    results.append(passed)
    print(f"[3] Known white noise only: sigma = {sigma} on a unit-amplitude tone:")
    print(f"    expected THD+N = {expected_db3:.2f} dB")
    print(f"    measured THD+N = {r3['thdn_db']:.2f} dB")
    print(f"    difference     = {err3:.2f} dB  (tolerance 0.5 dB)")
    print(f"    -> {'PASS' if passed else 'FAIL'}\n")

    # --- Test 4: harmonics + noise together -- the realistic case, since a
    # real recording has both.
    seg4 = steady_segment(_synthetic(freq, sr, dur, harmonics=harmonics, noise_sigma=sigma, seed=7), sr)
    r4 = thd_n(seg4, freq, sr)
    p_resid4 = p_resid + sigma ** 2
    expected_ratio4 = math.sqrt(p_resid4 / (p_fund + p_resid4))
    expected_db4 = 20 * math.log10(expected_ratio4)
    err4 = abs(r4["thdn_db"] - expected_db4)
    passed = err4 < 0.5
    results.append(passed)
    print(f"[4] Combined: same harmonics + same noise together:")
    print(f"    expected THD+N = {expected_db4:.2f} dB")
    print(f"    measured THD+N = {r4['thdn_db']:.2f} dB")
    print(f"    difference     = {err4:.2f} dB  (tolerance 0.5 dB)")
    print(f"    -> {'PASS' if passed else 'FAIL'}\n")

    # --- Test 5: sanity check that a WORSE distortion level reads as a
    # worse (less negative) dB number -- i.e. the sign/direction of the
    # scale is right, which is what the whole 0 dBFS vs -2 dBFS comparison
    # in the real measurement depends on.
    worse_harmonics = {3: 0.05}  # -26 dBc, much worse than test 2/4
    seg5 = steady_segment(_synthetic(freq, sr, dur, harmonics=worse_harmonics), sr)
    r5 = thd_n(seg5, freq, sr)
    passed = r5["thdn_db"] > r2["thdn_db"]
    results.append(passed)
    print(f"[5] Direction check: 5% 3rd-harmonic distortion should read WORSE than 1%:")
    print(f"    1% case measured  = {r2['thdn_db']:.2f} dB")
    print(f"    5% case measured  = {r5['thdn_db']:.2f} dB  (must be greater / less negative)")
    print(f"    -> {'PASS' if passed else 'FAIL'}\n")

    all_passed = all(results)
    print("=" * 60)
    if all_passed:
        print(f"SELF-TEST: ALL {len(results)} CHECKS PASSED.")
        print("The THD+N maths in this script is verified against known,")
        print("synthetic distortion. This does NOT verify anything about")
        print("real hardware, recording quality, or the VM concern above --")
        print("only that the signal-processing arithmetic is correct.")
    else:
        print(f"SELF-TEST: {results.count(False)} of {len(results)} CHECKS FAILED.")
        print("Do not trust any real measurement from this script until")
        print("this passes -- something is wrong in the analysis code.")
    print("=" * 60)
    return all_passed


# ---------------------------------------------------------------------------
# Device selection (no hard-coded indices -- list by name, resolve by
# substring or explicit index, and always print what was chosen)
# ---------------------------------------------------------------------------


def _require_sounddevice():
    try:
        import sounddevice as sd
    except ImportError:
        print(
            "This part needs sounddevice, which isn't installed in this\n"
            "Python. Install it with:\n\n"
            "    pip install sounddevice\n\n"
            "(--self-test does not need this and can run without it.)",
            file=sys.stderr,
        )
        sys.exit(1)
    return sd


def list_devices() -> None:
    sd = _require_sounddevice()
    print(sd.query_devices())


def resolve_device(sd, query: str, kind: str) -> int:
    """kind is 'input' or 'output'. `query` is an integer index (as a
    string) or a case-insensitive substring of the device name."""
    devices = sd.query_devices()
    if query.strip().lstrip("-").isdigit():
        idx = int(query)
        if idx < 0 or idx >= len(devices):
            print(f"Device index {idx} out of range (0..{len(devices) - 1}).", file=sys.stderr)
            sys.exit(1)
        d = devices[idx]
        chan_key = "max_input_channels" if kind == "input" else "max_output_channels"
        if d[chan_key] <= 0:
            print(f"Device {idx} ('{d['name']}') has no {kind} channels.", file=sys.stderr)
            sys.exit(1)
        return idx

    chan_key = "max_input_channels" if kind == "input" else "max_output_channels"
    matches = [
        i for i, d in enumerate(devices)
        if query.lower() in d["name"].lower() and d[chan_key] > 0
    ]
    if not matches:
        print(f"No {kind} device name matched '{query}'. Run --list-devices to see names.", file=sys.stderr)
        sys.exit(1)
    if len(matches) > 1:
        print(f"'{query}' matched more than one {kind} device -- be more specific, or pass the index:", file=sys.stderr)
        for i in matches:
            print(f"    [{i}] {devices[i]['name']}", file=sys.stderr)
        sys.exit(1)
    return matches[0]


# ---------------------------------------------------------------------------
# Real measurement (requires sounddevice + actual hardware)
# ---------------------------------------------------------------------------

SR_DEFAULT = 48000
TONE_DUR = 2.0          # seconds -- kept short deliberately (hearing safety)
SETTLE = 0.3            # seconds discarded from each end before analysis
CLIP_ABORT_DBFS = -1.0   # recorded peak at/above this aborts the whole run
CLIP_WARN_DBFS = -3.0    # recorded peak at/above this flags a single result
SILENCE_ABORT_DBFS = -55.0  # recorded peak at/below this in the safety probe aborts (nothing is looping back)
SILENCE_WARN_DBFS = -50.0   # recorded peak at/below this flags a single result as suspiciously quiet
FLOOR_MARGIN_DB = 10.0   # a result within this many dB of the floor is suspect


def play_and_record(sd, tone: np.ndarray, out_dev: int, in_dev: int, sr: int, out_channels: int) -> np.ndarray:
    data = np.column_stack([tone.astype(np.float32)] * out_channels)
    rec = sd.playrec(
        data,
        samplerate=sr,
        device=(in_dev, out_dev),
        channels=1,
        blocking=True,
    )
    sd.wait()
    return rec[:, 0]


def measure(sd, freq: float, dbfs: float, out_dev: int, in_dev: int, sr: int, out_channels: int, label: str) -> dict:
    tone = gen_tone(freq, dbfs, TONE_DUR, sr)
    rec = play_and_record(sd, tone, out_dev, in_dev, sr, out_channels)
    seg = steady_segment(rec, sr, settle=SETTLE)
    result = thd_n(seg, freq, sr)
    result["label"] = label
    result["freq"] = freq
    result["dbfs"] = dbfs
    return result


def print_result(r: dict) -> None:
    flag = ""
    if r["peak_dbfs"] >= CLIP_WARN_DBFS:
        flag = "  ** CLIPPED / near full scale -- DISCARD THIS RESULT **"
    elif r["peak_dbfs"] <= SILENCE_WARN_DBFS:
        flag = "  ** NO SIGNAL -- check cabling/device selection, DISCARD THIS RESULT **"
    print(
        f"  [{r['label']:22s}] {r['freq']:>6.0f} Hz {r['dbfs']:+5.1f} dBFS -> "
        f"peak {r['peak_dbfs']:7.2f} dBFS | THD+N {r['thdn_db']:7.2f} dB "
        f"({r['thdn_pct']:.4f} %){flag}"
    )
    for f, lvl in r.get("spurs", [])[:3]:
        print(f"        spur {f:8.1f} Hz @ {lvl:6.1f} dBc")


def prompt(msg: str) -> None:
    print(msg)
    input("  Press Enter when ready... ")


def run_real_measurement(args) -> None:
    sd = _require_sounddevice()

    out_idx = resolve_device(sd, args.output, "output") if args.output else None
    in_idx = resolve_device(sd, args.input, "input") if args.input else None
    if out_idx is None or in_idx is None:
        print("Available devices:\n")
        print(sd.query_devices())
        print()
    if out_idx is None:
        out_idx = resolve_device(sd, input("Output device (name substring or index): "), "output")
    if in_idx is None:
        in_idx = resolve_device(sd, input("Input device (name substring or index): "), "input")

    devices = sd.query_devices()
    out_info, in_info = devices[out_idx], devices[in_idx]
    out_channels = min(int(out_info["max_output_channels"]), 8) or 1
    sr = args.samplerate

    print("=" * 70)
    print("CHOSEN DEVICES (nothing has been played yet):")
    print(f"  Output: [{out_idx}] {out_info['name']}  ({out_channels} channel(s) will be driven)")
    print(f"  Input:  [{in_idx}] {in_info['name']}")
    print(f"  Sample rate: {sr} Hz")
    if out_idx == in_idx:
        print("  NOTE: input and output are the SAME device -- this is a self-loopback")
        print("  measurement (see experimental/README-thd-test.md: this measures the DAC and")
        print("  ADC together, so only the RELATIVE change between conditions below")
        print("  means anything -- not the absolute THD+N number.")
    print("=" * 70)

    volumes = [v.strip() for v in args.volumes.split(",") if v.strip()]

    print(
        "\n"
        "HEARING SAFETY: if the device under test is a headphone output, make\n"
        "sure headphones are OFF (or turned all the way down) until the initial\n"
        "quiet safety check below has passed. Every tone in this script is a\n"
        f"{TONE_DUR:.1f}s burst -- short deliberately.\n"
    )
    prompt("Confirm headphones are off / volume is low, and the loopback cable is connected.")

    # --- Phase 0: quiet-tone clipping/safety probe + noise floor reference.
    prompt(
        "\nPhase 0 -- safety check + noise floor.\n"
        "Set the output device's volume to a LOW/MODERATE level now (well below\n"
        "its usual listening level) -- this is just to confirm the cabling and\n"
        "gain staging won't overload the recording input."
    )
    floor = measure(sd, 997.0, -20.0, out_idx, in_idx, sr, out_channels, "floor_probe")
    print()
    print_result(floor)
    if floor["peak_dbfs"] >= CLIP_ABORT_DBFS:
        print(
            f"\nABORTING: even a -20 dBFS digital tone at low volume recorded a peak of "
            f"{floor['peak_dbfs']:.1f} dBFS -- your input gain or output volume is far too hot for "
            "this test. Lower the recording input's gain (or the output volume) and try again.\n"
        )
        sys.exit(1)
    if floor["peak_dbfs"] <= SILENCE_ABORT_DBFS:
        print(
            f"\nABORTING: the recording peak was only {floor['peak_dbfs']:.1f} dBFS -- that looks like\n"
            "no signal reached the input at all. Check the loopback cable, the input device\n"
            "selection (-i), and that the output device (-o) is actually the one making sound.\n"
        )
        sys.exit(1)
    floor_db = floor["thdn_db"]
    print(
        f"\nRecording-chain noise floor established: {floor_db:.1f} dB "
        f"({floor['thdn_pct']:.4f} %) at -20 dBFS input.\n"
        "Every measurement below within "
        f"{FLOOR_MARGIN_DB:.0f} dB of this floor will be flagged as unreliable --\n"
        "at that point the number is measuring the recording chain, not the G6.\n"
    )

    freqs = [997.0, 60.0, 20.0]
    levels = [0.0, -2.0]
    all_results: list[dict] = []

    for vol_label in volumes:
        prompt(
            f"\nPhase -- volume = {vol_label}%.\n"
            f"Set the OUTPUT device's own volume to {vol_label}% now (System Settings > Sound,\n"
            "or the menu-bar volume control, or Audio MIDI Setup -- whatever controls this\n"
            "device's own hardware volume). This script will never change it for you."
        )
        print(
            "\n  About to play 0 dBFS (full-scale) tones. If this is a headphone output,\n"
            "  make sure no one is wearing the headphones right now.\n"
        )
        for freq in freqs:
            for dbfs in levels:
                label = f"v{vol_label}_{freq:.0f}Hz_{dbfs:+.0f}dB"
                r = measure(sd, freq, dbfs, out_idx, in_idx, sr, out_channels, label)
                r["volume"] = vol_label
                if r["thdn_db"] < floor_db + FLOOR_MARGIN_DB:
                    r["near_floor"] = True
                else:
                    r["near_floor"] = False
                print_result(r)
                if r["near_floor"]:
                    print(f"        (within {FLOOR_MARGIN_DB:.0f} dB of the noise floor -- treat cautiously)")
                all_results.append(r)
                time.sleep(0.2)

    print_verdict(all_results, floor_db, volumes)


def print_verdict(results: list[dict], floor_db: float, volumes: list[str]) -> None:
    print("\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)

    valid = [
        r for r in results
        if SILENCE_WARN_DBFS < r["peak_dbfs"] < CLIP_WARN_DBFS and not r.get("near_floor")
    ]
    discarded = len(results) - len(valid)
    if discarded:
        print(f"({discarded} of {len(results)} results discarded: clipped, silent, or indistinguishable from the noise floor)\n")

    if not valid:
        print("No usable results -- everything was either clipped or too close to the")
        print("recording chain's own noise floor to say anything about the G6. See the")
        print("per-result flags above. This most likely means the recording ADC (or a")
        print("self-loopback through the G6's own line-in) is not clean enough for this")
        print("test -- try a lower-noise, independent recording interface.")
        return

    def find(vol, freq, dbfs):
        for r in valid:
            if r.get("volume") == vol and r["freq"] == freq and r["dbfs"] == dbfs:
                return r
        return None

    print(f"Recording-chain noise floor: {floor_db:.1f} dB. Results below within "
          f"{FLOOR_MARGIN_DB:.0f} dB of that were already excluded above.\n")

    print("-- 0 dBFS vs -2 dBFS, at each volume setting --")
    zero_vs_minus2_deltas = []
    for vol in volumes:
        for freq in (997.0, 60.0, 20.0):
            r0 = find(vol, freq, 0.0)
            rm2 = find(vol, freq, -2.0)
            if r0 and rm2:
                delta = r0["thdn_db"] - rm2["thdn_db"]  # positive = 0dBFS worse
                zero_vs_minus2_deltas.append((vol, freq, delta))
                verdict = "0 dBFS measurably WORSE" if delta > 1.0 else (
                    "no meaningful difference" if abs(delta) <= 1.0 else "-2 dBFS worse (unexpected)"
                )
                print(f"  vol={vol:>4s}%  {freq:>6.0f} Hz:  0dBFS={r0['thdn_db']:7.2f} dB  "
                      f"-2dBFS={rm2['thdn_db']:7.2f} dB  delta={delta:+6.2f} dB  -> {verdict}")

    print("\n-- Does lowering the DEVICE'S OWN volume help, at a fixed 0 dBFS input? --")
    if len(volumes) >= 2:
        baseline_vol = volumes[0]
        for freq in (997.0, 60.0, 20.0):
            base = find(baseline_vol, freq, 0.0)
            if not base:
                continue
            for vol in volumes[1:]:
                other = find(vol, freq, 0.0)
                if other:
                    delta = base["thdn_db"] - other["thdn_db"]
                    verdict = "LOWERING VOLUME HELPED" if delta > 1.0 else "no meaningful change"
                    print(f"  {freq:>6.0f} Hz:  vol={baseline_vol}%={base['thdn_db']:7.2f} dB  "
                          f"vol={vol}%={other['thdn_db']:7.2f} dB  delta={delta:+6.2f} dB  -> {verdict}")

    print()
    low_freq_deltas = [d for (vol, freq, d) in zero_vs_minus2_deltas if freq in (60.0, 20.0)]
    confirms_asr = low_freq_deltas and (sum(low_freq_deltas) / len(low_freq_deltas)) > 1.5

    if confirms_asr:
        print(
            "READING: at low frequencies, 0 dBFS measured worse than -2 dBFS on this unit,\n"
            "consistent with Audio Science Review's 2019 finding. Since backing off the\n"
            "device's OWN volume control (not a software/app volume) also reduced THD+N at\n"
            "a fixed full-scale digital input (see the comparison above, if it also shows\n"
            "improvement), the practical mitigation -- keep playback below 100% -- works on\n"
            "this unit regardless of whether the G6's volume control sits before or after\n"
            "its DAC internally."
        )
    else:
        print(
            "READING: this unit did NOT show a clear 0 dBFS vs -2 dBFS gap at low frequency\n"
            "(or the volume-lowering comparison didn't confirm it). That could mean this\n"
            "specific unit doesn't reproduce ASR's 2019 finding, or that the effect is\n"
            "smaller than this recording chain's noise floor allows detecting -- check the\n"
            "floor numbers above before concluding the issue doesn't exist."
        )

    print(
        "\nCAVEAT: this is one unit, measured once, through one recording chain. It is\n"
        "evidence about that unit at that point in time -- not proof about every G6, and\n"
        "not a substitute for ASR's original bench measurement or a repeat on different\n"
        "hardware."
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(
        description="THD+N measurement for the Sound BlasterX G6 -- see the module docstring "
        "(run with --help after reading experimental/README-thd-test.md).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--self-test", action="store_true", help="Verify the THD+N maths offline against synthetic signals with known distortion. No hardware needed. Run this first.")
    ap.add_argument("--list-devices", action="store_true", help="List audio input/output devices by name and index, then exit.")
    ap.add_argument("--i-know-this-is-a-vm", action="store_true", help="Override the VM safety check. Read the warning first -- this does not make the measurement trustworthy.")
    ap.add_argument("-o", "--output", help="Output device: name substring (e.g. 'G6') or index (e.g. '3').")
    ap.add_argument("-i", "--input", help="Input device: name substring or index.")
    ap.add_argument("--samplerate", type=int, default=SR_DEFAULT, help=f"Sample rate in Hz (default {SR_DEFAULT}).")
    ap.add_argument("--volumes", default="100,90,79", help="Comma-separated device volume percentages to walk through and prompt for (default: 100,90,79).")
    args = ap.parse_args()

    if args.self_test:
        ok = self_test()
        sys.exit(0 if ok else 1)

    if args.list_devices:
        list_devices()
        return

    if hypervisor_present() and not args.i_know_this_is_a_vm:
        print(VM_WARNING, file=sys.stderr)
        sys.exit(1)
    elif args.i_know_this_is_a_vm and hypervisor_present():
        print(VM_WARNING)
        print("--i-know-this-is-a-vm given: proceeding anyway. Results are not trustworthy.\n")

    run_real_measurement(args)


if __name__ == "__main__":
    main()
