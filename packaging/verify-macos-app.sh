#!/usr/bin/env bash
#
# Verify that a built .app is genuinely self-contained.
#
# It is easy to build a bundle that works on the build machine and fails
# everywhere else, because it quietly loads a library from Homebrew. These
# checks are written to catch exactly that.
#
# Usage:  packaging/verify-macos-app.sh "path/to/Sound Blaster X G6.app"
#
set -uo pipefail

APP="${1:?usage: verify-macos-app.sh <path to .app>}"
FAILED=0

pass() { printf '  \033[1;32mPASS\033[0m %s\n' "$*"; }
fail() { printf '  \033[1;31mFAIL\033[0m %s\n' "$*"; FAILED=1; }
head_() { printf '\033[1;34m--\033[0m %s\n' "$*"; }

[[ -d "$APP" ]] || { echo "No such app bundle: $APP" >&2; exit 1; }
# Absolute path, because install names inside the bundle are absolute — and the
# bundle name contains spaces, so every parse below must be space-safe.
APP_ABS="$(cd "$APP" && pwd)"

# ── 1. Structure ─────────────────────────────────────────────────────────────
head_ "Bundle structure"
for rel in \
    "Contents/MacOS" \
    "Contents/Frameworks/Python.framework" \
    "Contents/Resources/app/g6_gui" \
    "Contents/Resources/app/g6_cli" \
    "Contents/Resources/app_packages" \
    "Contents/Resources/lib/libusb-1.0.dylib"
do
    if [[ -e "$APP/$rel" ]]; then pass "$rel"; else fail "missing $rel"; fi
done

for rel in \
    "Contents/Resources/app/g6_gui/native.py" \
    "Contents/Resources/app_packages/hid.cpython-312-darwin.so" \
    "Contents/Resources/app_packages/usb/backend/libusb1.py" \
    "Contents/Resources/app_packages/toga_cocoa"
do
    if [[ -e "$APP/$rel" ]]; then pass "$(basename "$rel")"; else fail "missing $rel"; fi
done

# ── 2. No references to libraries outside the bundle ─────────────────────────
# This is the check that catches "works on my machine": a binary that links
# against /opt/homebrew or /usr/local will not resolve on a clean Mac.
head_ "Native binaries reference only system libraries"
OFFENDERS=""
while IFS= read -r bin; do
    # Strip the leading tab and the trailing " (compatibility version ...)" —
    # never split on spaces: install names here are absolute paths that contain
    # them, and awk '{print $1}' silently truncates every one of them.
    # Keep only the INDENTED lines: otool prints unindented header lines for the
    # file itself and for each architecture slice, and 'tail -n +2' only skips
    # the first of them.
    refs="$(otool -L "$bin" 2>/dev/null | grep '^[[:space:]]' \
        | sed -E 's/^[[:space:]]*//; s/ \(compatibility version .*\)$//' \
        | grep -vE '^(/usr/lib/|/System/|@loader_path|@rpath|@executable_path)' \
        | grep -vF "$APP_ABS" || true)"
    if [[ -n "$refs" ]]; then
        OFFENDERS+="$bin:
$refs
"
    fi
done < <(find "$APP" \( -name '*.so' -o -name '*.dylib' \) -type f)

if [[ -z "$OFFENDERS" ]]; then
    pass "every .so/.dylib resolves inside the bundle or to the system"
else
    fail "binaries reference libraries outside the bundle:"
    printf '%s\n' "$OFFENDERS" | sed 's/^/        /'
fi

# ── 3. Code signature ────────────────────────────────────────────────────────
head_ "Code signature"
if codesign --verify --deep "$APP" 2>/dev/null; then
    pass "signature valid"
else
    fail "codesign --verify failed"
fi

# ── 4. It runs, and loads the BUNDLED libusb ─────────────────────────────────
# The decisive check. Everything above can pass while the running app still
# quietly picks up Homebrew's copy.
head_ "Runtime behaviour"
BIN="$APP/Contents/MacOS/$(basename "$APP" .app)"
if [[ ! -x "$BIN" ]]; then
    fail "no executable at $BIN"
else
    LOG="$(mktemp)"
    "$BIN" >"$LOG" 2>&1 &
    PID=$!
    sleep 10
    if ! ps -p "$PID" >/dev/null 2>&1; then
        fail "app exited within 10s; output:"
        sed 's/^/        /' "$LOG" | tail -20
    else
        pass "app launched and stayed running"
        # -F n prints one field per line prefixed with 'n', so paths containing
        # spaces survive intact. Column-splitting lsof output does not.
        LOADED="$(lsof -p "$PID" -F n 2>/dev/null | sed -n 's/^n//p' \
            | grep -i 'libusb' | head -1)"
        if [[ -z "$LOADED" ]]; then
            fail "no libusb loaded at all (device lookup would fail)"
        elif [[ "$LOADED" == "$APP_ABS"* ]]; then
            pass "loaded the BUNDLED libusb"
        else
            fail "loaded libusb from OUTSIDE the bundle: $LOADED
        The app would not work on a Mac without that library installed."
        fi
        kill "$PID" 2>/dev/null
        wait "$PID" 2>/dev/null
    fi
    rm -f "$LOG"
fi

echo
if [[ "$FAILED" -eq 0 ]]; then
    printf '\033[1;32mBundle verified: self-contained.\033[0m\n'
else
    printf '\033[1;31mBundle verification FAILED.\033[0m\n'
fi
exit "$FAILED"
