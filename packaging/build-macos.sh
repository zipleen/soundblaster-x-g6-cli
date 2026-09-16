#!/usr/bin/env bash
#
# Build a fully self-contained macOS .app and .dmg for the Sound Blaster X G6 GUI.
#
# The resulting bundle embeds its own Python, every Python dependency, and the
# native libusb library, so the target machine needs neither Python nor
# Homebrew. Drag the app out of the .dmg into /Applications and double-click it.
#
# Usage:
#   packaging/build-macos.sh                      ad-hoc signed (this Mac only)
#   packaging/build-macos.sh --skip-dmg           build the .app, no .dmg
#   packaging/build-macos.sh --identity "<ID>"    sign with a Developer ID and
#                                                 notarise (see NOTARIZING.md)
#   packaging/build-macos.sh --identity "<ID>" --no-notarize
#
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# CI (and anyone with a non-standard install) can point this at another 3.12.
PYTHON="${PYTHON:-python3.12}"
BUILD_VENV=".build-venv"
APP_NAME="Sound Blaster X G6"
APP_PATH="build/g6_gui/macos/app/${APP_NAME}.app"
LIB_DEST="${APP_PATH}/Contents/Resources/lib"
SKIP_DMG=0
IDENTITY=""
NOTARIZE=1

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m  ok\033[0m %s\n' "$*"; }
die()   { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-dmg)    SKIP_DMG=1; shift ;;
        --identity)    IDENTITY="${2:-}"; [[ -n "$IDENTITY" ]] || die "--identity needs a value"; shift 2 ;;
        --no-notarize) NOTARIZE=0; shift ;;
        -h|--help)     sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *)             die "Unknown option: $1 (see --help)" ;;
    esac
done

# ── 1. Prerequisites ─────────────────────────────────────────────────────────
info "Checking prerequisites"
[[ "$(uname)" == "Darwin" ]] || die "This script builds a macOS bundle; run it on macOS."
command -v "$PYTHON" >/dev/null || die "$PYTHON not found. Install Python 3.12 (e.g. 'brew install python@3.12'), or set PYTHON=/path/to/python3.12."
"$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)' \
    || die "$PYTHON is not Python 3.12."
xcode-select -p >/dev/null 2>&1 || die "Xcode command line tools missing. Run: xcode-select --install"
ok "macOS, $("$PYTHON" -V), command line tools"

# libusb is the one native library pyusb loads at runtime and that is not
# already inside a wheel. It is needed at BUILD time only, to copy into the app.
LIBUSB_SRC=""
for candidate in \
    "$(brew --prefix libusb 2>/dev/null || true)/lib/libusb-1.0.dylib" \
    "/opt/homebrew/lib/libusb-1.0.dylib" \
    "/usr/local/lib/libusb-1.0.dylib"
do
    if [[ -f "$candidate" ]]; then LIBUSB_SRC="$candidate"; break; fi
done
[[ -n "$LIBUSB_SRC" ]] || die "libusb not found. Install it to build the bundle: brew install libusb"
LIBUSB_SRC="$("$PYTHON" -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$LIBUSB_SRC")"
ok "libusb: $LIBUSB_SRC"

# ── 2. Build toolchain ───────────────────────────────────────────────────────
info "Preparing build environment ($BUILD_VENV)"
[[ -d "$BUILD_VENV" ]] || "$PYTHON" -m venv "$BUILD_VENV"
"$BUILD_VENV/bin/pip" install --quiet --upgrade pip briefcase
ok "briefcase $("$BUILD_VENV/bin/briefcase" --version)"

# ── 3. Clean build ───────────────────────────────────────────────────────────
info "Creating application scaffold (clean build)"
rm -rf build/g6_gui dist
"$BUILD_VENV/bin/briefcase" create macOS app
ok "scaffold created"

info "Building application"
"$BUILD_VENV/bin/briefcase" build macOS app
[[ -d "$APP_PATH" ]] || die "Expected app at $APP_PATH but it is missing."
ok "built $APP_PATH"

# ── 4. Embed the native library ──────────────────────────────────────────────
# Done AFTER build and BEFORE package, so briefcase's packaging step signs the
# dylib along with everything else. Injecting after signing would invalidate it.
info "Embedding libusb into the bundle"
mkdir -p "$LIB_DEST"
cp "$LIBUSB_SRC" "$LIB_DEST/libusb-1.0.dylib"
chmod u+w "$LIB_DEST/libusb-1.0.dylib"
install_name_tool -id "@loader_path/libusb-1.0.dylib" "$LIB_DEST/libusb-1.0.dylib"
codesign --force --sign - "$LIB_DEST/libusb-1.0.dylib"
ok "libusb embedded at Contents/Resources/lib/"

# Anything the copied dylib itself depends on outside the system is a problem;
# report it rather than shipping a bundle that breaks on another machine.
EXTERNAL_DEPS="$(otool -L "$LIB_DEST/libusb-1.0.dylib" | tail -n +2 \
    | awk '{print $1}' \
    | grep -vE '^(/usr/lib/|/System/|@loader_path|@rpath)' || true)"
if [[ -n "$EXTERNAL_DEPS" ]]; then
    die "Embedded libusb depends on libraries outside the bundle:
$EXTERNAL_DEPS
The app would fail on a machine without them."
fi
ok "libusb has no external dependencies"

# ── 5. Package ───────────────────────────────────────────────────────────────
if [[ "$SKIP_DMG" -eq 1 ]]; then
    info "Skipping .dmg (--skip-dmg)"
else
    PKG_ARGS=()
    if [[ -n "$IDENTITY" ]]; then
        # A real Developer ID. briefcase signs every nested binary with it,
        # enables the hardened runtime, builds the .dmg, and (unless told not
        # to) submits it to Apple for notarisation and staples the ticket.
        info "Packaging .dmg signed as: $IDENTITY"
        PKG_ARGS+=(--identity "$IDENTITY")
        if [[ "$NOTARIZE" -eq 0 ]]; then
            PKG_ARGS+=(--no-notarize)
            info "Notarisation disabled (--no-notarize)"
        else
            info "Notarising with Apple - this usually takes a few minutes"
        fi
    else
        # Ad-hoc: valid locally, but macOS quarantines a downloaded copy.
        # See packaging/NOTARIZING.md to produce a distributable build.
        info "Packaging .dmg (ad-hoc signed)"
        PKG_ARGS+=(--adhoc-sign)
    fi
    "$BUILD_VENV/bin/briefcase" package macOS app "${PKG_ARGS[@]}"
    DMG="$(ls -t dist/*.dmg 2>/dev/null | head -1 || true)"
    [[ -n "$DMG" ]] || die "briefcase package did not produce a .dmg in dist/"
    ok "created $DMG"
fi

# ── 6. Verify the bundle is actually self-contained ──────────────────────────
info "Verifying the bundle"
packaging/verify-macos-app.sh "$APP_PATH" ${VERIFY_FLAGS:-}

echo
info "Done."
echo "  App: $APP_PATH"
if [[ "$SKIP_DMG" -eq 0 ]]; then
    echo "  DMG: $(ls -t dist/*.dmg | head -1)"
    echo
    echo "  Open the .dmg and drag \"${APP_NAME}\" into Applications."
fi
