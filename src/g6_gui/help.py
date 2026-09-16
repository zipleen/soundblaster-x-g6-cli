"""Help text for every control, shown by the (i) button next to each row.

Single source of the wording, so the UI and ``docs/settings-reference.md`` do
not drift. Keep entries short — a few sentences. Anything longer belongs in the
document, which each entry implicitly summarises.

Text is plain: it gets wrapped and rendered as a stack of labels, so no Markdown.
"""

from __future__ import annotations

from g6_gui.platform import IS_MACOS

# ── Playback ────────────────────────────────────────────────────────────────

OUTPUT = (
    "Picks which physical jack the G6 drives. Headphones is the front 3.5 mm "
    "socket, driven by the Xamp. Speakers is the rear socket, which is a combo "
    "jack carrying both Line Out and the optical (mini-TOSLINK) output.\n"
    "\n"
    "The 5.1 and 7.1 variants in the CLI send identical bytes to stereo — the "
    "channel count is decided by the operating system, not the device, and "
    "Creative's own software describes 5.1 and 7.1 as virtual outputs."
)

_DIRECT_MODE_COMMON = (
    "Direct Mode shuts down the G6's entire DSP so the signal reaches the DAC "
    "untouched, and unlocks sample rates above 96 kHz (up to 32-bit/384 kHz).\n"
    "\n"
    "It disables SBX, Scout Mode, the equalizer, What-U-Hear and — confirmed on "
    "this hardware — microphone recording. Sidetone (hearing yourself) keeps "
    "working, so hearing your own voice is not proof the mic is being recorded.\n"
    "\n"
    "It is not a sound-quality upgrade over simply turning the effects off: "
    "Audio Science Review measured no difference between the two. It matters "
    "for high sample rates and for bit-perfect playback.\n"
    "\n"
    "Note that on the device this is one position of a three-way Output Mode "
    "setting (Audio Effects / Direct / SPDIF-Out Direct), so turning this on "
    "automatically turns SPDIF-Out Direct off."
)

DIRECT_MODE_MACOS = (
    "Direct Mode does not work on macOS. macOS controls the device's mode "
    "itself, so this switch is ignored — set it in Audio MIDI Setup instead.\n"
    "\n"
    "Select the G6 there and set Clock Source:\n"
    "  - DSP Clock — SBX and the other effects work. Capped at 32-bit/48 kHz.\n"
    "  - Stereo Direct — Direct Mode. Bit-perfect up to 32-bit/384 kHz, but no "
    "SBX and no microphone.\n"
    "\n"
    "Switching back from 384 kHz: DSP Clock cannot do that rate. Set the format "
    "to 2 ch 24-bit 48 kHz first, then switch to DSP Clock, or audio breaks."
)

DIRECT_MODE = _DIRECT_MODE_COMMON

SPDIF_OUT_DIRECT_MACOS = (
    "Sends bit-perfect PCM (up to 24-bit/96 kHz, the limit of S/PDIF) straight "
    "to the optical output with no processing. It affects the optical output "
    "only — the analog outputs keep their effects.\n"
    "\n"
    "Whether this works on macOS is unknown and untested. Unlike Direct Mode, "
    "macOS has no equivalent setting: Audio MIDI Setup's Clock Source offers "
    "only DSP Clock and Stereo Direct, so it may well leave this one alone and "
    "let the switch through. It is left enabled so it can be tried, rather than "
    "disabled on an assumption.\n"
    "\n"
    "If you can test it with something plugged into the optical out, the result "
    "is worth recording in docs/settings-reference.md.\n"
    "\n"
    "Two things to expect if it does work: the G6 can no longer control the "
    "volume of the optical stream, because bit-perfect means no digital volume "
    "scaling; and on the device this and Direct Mode are mutually exclusive."
)

SPDIF_OUT_DIRECT = (
    "Sends bit-perfect PCM (up to 24-bit/96 kHz, the limit of S/PDIF) straight "
    "to the optical output with no processing.\n"
    "\n"
    "It affects the optical output only — the analog Line Out and headphone "
    "output keep their effects. Two consequences worth knowing: the G6 can no "
    "longer control the volume of the optical stream, because bit-perfect means "
    "no digital volume scaling; and conversely, turning Direct Mode on silences "
    "the optical output entirely.\n"
    "\n"
    "Direct Mode and SPDIF-Out Direct are mutually exclusive on the device, so "
    "switching one on switches the other off.\n"
    "\n"
    "Only useful if something is actually plugged into the optical out."
)

FILTER = (
    "Selects the reconstruction filter inside the DAC (a Cirrus Logic CS43131). "
    "Roll-off sets how sharply the filter cuts near 20 kHz; phase sets where "
    "its ringing goes — linear phase rings symmetrically (a little before each "
    "transient), minimum phase puts all of it after.\n"
    "\n"
    "Honestly: the differences live above about 18 kHz and in impulse ringing "
    "far below the signal. On any headphone this is inaudible — your "
    "headphone's own response varies by ten times as much.\n"
    "\n"
    "If you want a rule: Slow Roll Off / Minimum Phase rings least, Fast Roll "
    "Off / Linear Phase measures flattest. The device default is Fast Roll Off "
    "/ Minimum Phase."
)

DECODER = (
    "Dynamic range control for the built-in Dolby Digital decoder. Full leaves "
    "the dynamics as mastered, Normal compresses moderately, Night heavily "
    "compresses so quiet dialogue comes up and loud peaks come down.\n"
    "\n"
    "This only does anything while the G6 is actually decoding a Dolby Digital "
    "bitstream, which on this device means one arriving at the optical input. "
    "Over USB the computer sends plain PCM, there is no decoder in the path, "
    "and this setting has nothing to act on.\n"
    "\n"
    "To use it, feed the optical input from a console or player set to bitstream "
    "output — for a PlayStation, set its audio output to digital/optical."
)

# ── Playback / audio interface ──────────────────────────────────────────────

PLAYBACK_MUTE = "Mutes the playback stream through the USB audio interface."

PLAYBACK_VOLUME = (
    "Playback level, sent as a USB Audio Class volume in 1/256 dB steps. "
    "100% is 0 dB (no attenuation), 50% is about -10 dB and 0% is -64 dB, so "
    "the scale is logarithmic rather than linear. Adjustable in steps of 10."
)

CHANNELS = (
    "Which channels the level applies to. Both is the normal choice; Left or "
    "Right alone lets you correct an imbalance."
)

# ── SBX ─────────────────────────────────────────────────────────────────────

SBX_PROFILE = (
    "Profiles are slots in this app's own settings file, not presets stored on "
    "the device. The G6 has exactly one live SBX state.\n"
    "\n"
    "Choosing a profile here only repoints the controls below at that slot — it "
    "sends nothing. Use 'Switch to this profile' to actually apply the slot's "
    "saved values to the device.\n"
    "\n"
    "The four slots start empty (every effect off, every slider at 50). "
    "Creative's own tuned profiles live in their Windows software and were "
    "never captured by this project."
)

SBX_SWITCH_BUTTON = (
    "Sends every value saved under the selected profile to the device, and "
    "records it as the active profile.\n"
    "\n"
    "This is the only bulk write in the whole application. Because the G6 has "
    "one live SBX state, it overwrites whatever is currently playing — "
    "including any edits you made while a different profile was active."
)

SBX_SURROUND = (
    "Virtual surround. Widens the stage and places sounds around you from a "
    "multichannel source, using head-related transfer functions.\n"
    "\n"
    "Effective for games and films with real surround content; less useful on "
    "stereo music. Creative's own software offers this as three positions — "
    "Normal, Wide and Ultra Wide — which correspond roughly to 0, 50 and 100 "
    "on this slider."
)

SBX_CRYSTALIZER = (
    "Re-expands dynamics and sharpens transients, intended to counter what "
    "lossy compression removes. In practice an expander with a treble tilt.\n"
    "\n"
    "Audible immediately, and easy to overdo — on an already-bright headphone a "
    "high setting gets harsh quickly."
)

SBX_BASS = (
    "Bass enhancement. Adds depth and harmonic weight to the low end rather "
    "than simply raising the level."
)

SBX_SMART_VOLUME = (
    "Evens out volume differences between quiet and loud passages, and between "
    "tracks, by continuously applying gain and attenuation.\n"
    "\n"
    "Note this slider is ignored whenever 'Smart Volume special' is set to "
    "anything other than None — the two are mutually exclusive in the protocol, "
    "and the special mode wins."
)

SBX_SMART_VOLUME_SPECIAL = (
    "Replaces the Smart Volume slider with a fixed levelling mode. Setting "
    "anything other than None disables the slider above.\n"
    "\n"
    "Night adds equal-loudness compensation — a gentle curve that keeps bass "
    "and treble audible at low listening levels.\n"
    "\n"
    "'Loud' is this project's name for the other mode, inherited from older "
    "Creative software; Creative's current software labels the same setting "
    "'Auto', meaning ordinary automatic levelling rather than anything louder."
)

SBX_DIALOG_PLUS = (
    "Lifts voices and dialogue above the rest of the mix. It analyses centre-"
    "channel and vocal content and raises just that, rather than turning "
    "everything up.\n"
    "\n"
    "Useful for films with buried dialogue. Creative's software offers this as "
    "Off / Normal / Balanced / Dialog Focus, roughly 0, 33, 66 and 100 here."
)

# ── Recording ───────────────────────────────────────────────────────────────

REC_NOISE_REDUCTION = (
    "Analyses the microphone signal, identifies steady background noise — fans, "
    "air conditioning, hum — and suppresses it so your voice carries over it.\n"
    "\n"
    "The toggle alone already does a lot; it audibly reduces the noise floor "
    "even with the level at 0.\n"
    "\n"
    "It will not remove keyboard clatter or mouse clicks. Those are short "
    "transients, not steady noise, and nothing on this device removes them — "
    "that needs a transient/gate-style suppressor on the computer instead."
)

REC_NOISE_REDUCTION_LEVEL = (
    "How aggressively noise reduction works, in steps of 20.\n"
    "\n"
    "At 100 the noise floor is very heavily suppressed, and it starts taking "
    "parts of your voice with it. Somewhere in the middle is usually the better "
    "trade.\n"
    "\n"
    "Worth knowing: 100 here sends half of the device's full-scale value, so "
    "the maximum is the middle of the underlying range rather than as much as "
    "the hardware can do."
)

REC_AEC = (
    "Acoustic Echo Cancellation removes your own speakers' output being picked "
    "up by the microphone and sent back to the far end of a call.\n"
    "\n"
    "It is only meaningful when you are using speakers — on headphones there is "
    "no acoustic path from output to microphone. It can still colour your voice "
    "either way, because it runs an adaptive filter on the mic signal: it "
    "audibly costs some clarity, which is a fair trade on a call and a poor one "
    "for recording."
)

REC_SMART_VOLUME = (
    "Intended to keep your voice at a consistent level to the other party "
    "whether you lean into the microphone or sit back.\n"
    "\n"
    "In testing on macOS this one produced no audible effect, unlike every "
    "other control on this tab. It may need a larger swing in your distance "
    "from the mic than normal speech produces, or it may simply not be active "
    "over USB here. Treat it as unproven rather than broken.\n"
    "\n"
    "If it does work, it is good for calls and bad for anything you intend to "
    "edit afterwards, since it removes the original dynamics."
)

REC_MIC_EQ = (
    "An eight-band equalizer on the microphone path, applied before the signal "
    "reaches the computer."
)

REC_MIC_EQ_PRESET = (
    "The presets are voicings rather than scenarios. Most cut low-frequency "
    "rumble and proximity boom in the bottom two bands, then lift the presence "
    "and air bands for intelligibility.\n"
    "\n"
    "Rough guide: Preset 4 is the gentlest cleanup; Preset 6 and Preset 10 are "
    "the most aggressive for intelligibility on calls; Preset 7 gives a fuller "
    "'radio' voice.\n"
    "\n"
    "'Dynamic Mic 1' applies 8 to 12 dB of broadband lift and exists for an "
    "actual dynamic microphone, which puts out far less signal than a condenser. "
    "On a condenser or electret — a headset mic, a ModMic — it clips and "
    "distorts. Confirmed in testing.\n"
    "\n"
    "Known quirk: band 4 of Preset 1 and Preset 2 is flat because of a bad byte "
    "value in the captured protocol; it was probably meant to be +2 dB."
)

REC_MUTE = "Mutes the microphone input at the USB audio interface."

REC_MIC_BOOST = (
    "Analog preamp gain ahead of the converter, in 10 dB steps up to 30 dB.\n"
    "\n"
    "This raises the noise floor along with your voice, so use the least that "
    "gets you a healthy level, and prefer it over pushing the recording volume "
    "to the top."
)

REC_VOLUME = (
    "The level sent to the computer, from -48 dB at 0% to +9 dB at 100%. Note "
    "the top of the range is amplification, not merely the absence of "
    "attenuation."
)

REC_MONITORING = (
    "Sidetone: how loudly you hear your own voice in your headphones.\n"
    "\n"
    "Creative documents the G6's hardware sidetone control as sharing its level "
    "with the microphone recording volume, so it is worth checking with another "
    "person whether raising this also makes you louder to them.\n"
    "\n"
    "Sidetone can also be toggled on the device by holding the volume knob for "
    "two seconds; the knob's LED turns red."
)

# ── Lighting ────────────────────────────────────────────────────────────────

LIGHTING_ENABLED = (
    "Turns the illuminated logo on the G6 on or off. Purely cosmetic — it has "
    "no effect on audio."
)

LIGHTING_COLOUR = (
    "Sets the logo colour as 24-bit RGB.\n"
    "\n"
    "Creative's Windows software also offers Pulsate, Music Reactive and Cycle "
    "animation modes; only the fixed colour was captured by this project."
)

# ── macOS Audio (Audio MIDI Setup, controlled directly) ─────────────────────

MACOS_CLOCK_SOURCE = (
    "This is the actual Direct Mode switch on macOS -- the one on the "
    "Playback tab does nothing here, because macOS controls this itself.\n"
    "\n"
    "DSP Clock keeps SBX, the equalizer and the microphone working, capped at "
    "48 kHz. Stereo Direct is Direct Mode: bit-perfect up to 384 kHz, but SBX, "
    "Scout Mode and the microphone all stop working.\n"
    "\n"
    "Switching from Stereo Direct back to DSP Clock automatically drops the "
    "format to something DSP Clock supports first. Without that, the switch "
    "can silently fail and leave audio broken -- confirmed by hand before "
    "this was automated."
)

RECORDING_SBX_DISABLED_BY_CLOCK_SOURCE = (
    "Disabled: macOS's Clock Source is set to Stereo Direct, which bypasses "
    "the G6's entire DSP. These controls would do nothing right now. See the "
    "macOS Audio tab."
)

MACOS_FORMAT = (
    "The sample rate and bit depth Core Audio sends to the G6. Only the "
    "formats the current Clock Source actually offers are listed -- DSP "
    "Clock's list tops out at 48 kHz, Stereo Direct's goes to 384 kHz.\n"
    "\n"
    "Higher is not better here: 24-bit/48 kHz already covers essentially all "
    "source material and the G6's own dynamic range. Prefer it unless you "
    "specifically have hi-res files or need DSD, and DSD needs Windows -- "
    "Creative say macOS does not support DSD playback at all."
)

# ── Mixer ───────────────────────────────────────────────────────────────────

MIXER_SOURCE = (
    "Each source has two independent levels. The Recording level is what the "
    "computer captures from that input. The Monitoring level is what gets mixed "
    "straight into your own output so you can hear it live.\n"
    "\n"
    "These are USB Audio Class controls, which is why this whole tab is absent "
    "on macOS — the operating system will not release that interface."
)

MIXER_PLAYBACK_MUTE = "Mutes the main playback stream at the USB audio interface."

# ── System ──────────────────────────────────────────────────────────────────

SYSTEM_CLAIM = (
    "Detaches the kernel audio driver so this application can use the G6's USB "
    "AudioControl interface, which is what the volume and mute controls need.\n"
    "\n"
    "While claimed, your system has no audio output through the G6. The "
    "interface is released again when you turn this off or quit."
)


def direct_mode() -> str:
    """Direct Mode help. On macOS the switch is inert, so lead with that."""
    return DIRECT_MODE_MACOS if IS_MACOS else DIRECT_MODE


def spdif_out_direct() -> str:
    """SPDIF-Out Direct help.

    On macOS this is *unverified* rather than known-broken, which is a different
    claim from Direct Mode's and deserves different wording.
    """
    return SPDIF_OUT_DIRECT_MACOS if IS_MACOS else SPDIF_OUT_DIRECT
