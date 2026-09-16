# macOS packaging

Builds a fully self-contained `Sound Blaster X G6.app` and a `.dmg` to
distribute it in. The bundle embeds its own Python, every Python dependency and
the native `libusb` library, so the target Mac needs **neither Python nor
Homebrew** — open the `.dmg`, drag the app to Applications, double-click.

## Build

```bash
packaging/build-macos.sh
```

Output:

- `build/g6_gui/macos/app/Sound Blaster X G6.app`
- `dist/Sound Blaster X G6-<version>.dmg`

Use `packaging/build-macos.sh --skip-dmg` to build only the `.app`.

### Build-machine requirements

These are needed only to *build*; users of the resulting app need none of them.

- macOS with Xcode command line tools (`xcode-select --install`)
- `python3.12` (e.g. `brew install python@3.12`)
- `libusb` (`brew install libusb`) — copied into the bundle at build time

The script creates its own `.build-venv/` for Briefcase, so it never touches the
project's runtime `venv/`.

## Verify

The build script runs this automatically; you can also run it on any bundle:

```bash
packaging/verify-macos-app.sh "build/g6_gui/macos/app/Sound Blaster X G6.app"
```

It checks that the expected files are present, that **no** binary in the bundle
references a library outside it, that the signature is valid, and — the check
that matters most — that the running app loads the `libusb` from *inside* the
bundle.

That last check exists because of a real failure: the first bundle built here
ran perfectly on the build machine while quietly loading Homebrew's `libusb`. It
would have failed on any Mac without Homebrew, and nothing would have caught it.

## How the native libraries are handled

| Library | Handling |
|---|---|
| `hidapi` | Nothing to do. Its wheel statically embeds libhidapi and links only system frameworks. |
| `libusb` | Not in any wheel — `pyusb` loads it at runtime via `ctypes.util.find_library`. The build script copies it to `Contents/Resources/lib/`, and `g6_gui/native.py` points pyusb at that copy before the first device lookup. |

## Continuous integration

`.github/workflows/macos-release.yml` builds this on every push to `main`,
running the GUI test suite first, uploading the `.dmg` as a workflow artifact,
and publishing a GitHub Release when the `version` in `pyproject.toml` is one
that has not been tagged yet. Bump that version to cut a release; pushes that
leave it unchanged build and upload, but do not re-release.

CI picks its build mode from whether the signing secrets are configured:
a notarised `...-notarized.dmg` when they are, an ad-hoc `...-unsigned.dmg`
when they are not. The mode is in the filename so the two cannot be confused.
See [NOTARIZING.md](NOTARIZING.md) for the secrets.

## Signing

The default build uses **ad-hoc signing** (`--adhoc-sign`): valid locally, but
not notarised by Apple.

- Copying the app between your own machines works.
- If the `.dmg` is *downloaded* (browser, email, AirDrop), macOS attaches a
  quarantine flag and Gatekeeper will refuse it with "cannot be opened because
  the developer cannot be verified". The recipient can clear it with:

  ```bash
  xattr -dr com.apple.quarantine "/Applications/Sound Blaster X G6.app"
  ```

  or right-click the app → Open → Open.

To distribute without that friction, notarise the build:

```bash
packaging/notarize-macos.sh --check   # verify your setup, build nothing
packaging/notarize-macos.sh           # full signed + notarised build
```

That needs a paid Apple Developer ID. **[NOTARIZING.md](NOTARIZING.md)** lists
the one-time steps only you can do (certificate, app-specific password, team ID)
and what to do when Apple rejects a submission.

The build script also takes the identity directly:

```bash
packaging/build-macos.sh --identity "Developer ID Application: Your Name (TEAMID)"
packaging/build-macos.sh --identity "..." --no-notarize   # sign, skip Apple
```

An ad-hoc signed bundle cannot be notarised after the fact — every binary has to
be re-signed with the Developer ID and the hardened runtime enabled, so
notarising always rebuilds.

## Licence note

The app bundles GPL-2.0-only code (`g6_cli`, `g6_gui`) together with
BSD/MIT/PSF-licensed dependencies and the embedded CPython. `libusb` is
LGPL-2.1-or-later, which is GPL-2.0 compatible, and it is included as an
unmodified dynamic library that can be replaced in the bundle.

Because the application derives from GPLv2 code, **any binary you distribute
must be accompanied by an offer of complete corresponding source.**
