#!/usr/bin/env bash
#
# Produce a NOTARISED, distributable macOS build.
#
# Run this on the Mac that has your Apple Developer ID certificate. It checks
# your credentials first, then does a full signed build and submits it to Apple,
# and finally proves the result would pass Gatekeeper on someone else's machine.
#
# Read packaging/NOTARIZING.md first — there are one-time setup steps that only
# you can do (they need your Apple ID and your developer account).
#
# Usage:
#   packaging/notarize-macos.sh                     pick the identity automatically
#   packaging/notarize-macos.sh --identity "<ID>"   use a specific one
#   packaging/notarize-macos.sh --check             only run the preflight checks
#
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

IDENTITY=""
CHECK_ONLY=0

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m  ok\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m  !!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --identity) IDENTITY="${2:-}"; [[ -n "$IDENTITY" ]] || die "--identity needs a value"; shift 2 ;;
        --check)    CHECK_ONLY=1; shift ;;
        -h|--help)  sed -n '2,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *)          die "Unknown option: $1 (see --help)" ;;
    esac
done

# ── Preflight ────────────────────────────────────────────────────────────────
# Notarisation fails slowly and unhelpfully when something is missing, so check
# everything up front and say exactly what to do about each problem.
info "Preflight checks"

[[ "$(uname)" == "Darwin" ]] || die "Notarisation only runs on macOS."

xcrun --find notarytool >/dev/null 2>&1 \
    || die "notarytool not found. Install Xcode (not just the command line tools),
       then run: sudo xcode-select -s /Applications/Xcode.app"
ok "notarytool available"

# 1. A Developer ID Application certificate must be in the keychain.
IDENTITIES="$(security find-identity -v -p codesigning 2>/dev/null \
    | grep "Developer ID Application" || true)"
if [[ -z "$IDENTITIES" ]]; then
    die "No 'Developer ID Application' certificate found in your keychain.

       This is the one-time step only you can do:
         1. Sign in at https://developer.apple.com/account (paid Developer Program).
         2. Xcode > Settings > Accounts > your Apple ID > Manage Certificates
            > + > Developer ID Application.
         3. Re-run this script.

       Note: an 'Apple Development' certificate is NOT enough — apps signed with
       it cannot be notarised for distribution."
fi
echo "$IDENTITIES" | sed 's/^/      /'

if [[ -z "$IDENTITY" ]]; then
    COUNT="$(echo "$IDENTITIES" | wc -l | tr -d ' ')"
    if [[ "$COUNT" -gt 1 ]]; then
        die "Several Developer ID certificates found. Choose one with:
       packaging/notarize-macos.sh --identity \"Developer ID Application: Name (TEAMID)\""
    fi
    # Anchored to the known "  N) HASH "..."" structure of a find-identity
    # line, not a greedy backward match from the end -- the certificate name
    # itself always ends in "(TEAMID)", and a trailing-anchored `.*\) "(.*)"$`
    # greedily consumes through *that* parenthesis instead of the one after
    # the index number, so the substitution silently fails to match and the
    # whole raw line (index, hash and all) is passed through unchanged as the
    # "identity" -- which is exactly the "Invalid ... signing identity"
    # briefcase error this caused. Reproduced and confirmed before fixing.
    IDENTITY="$(echo "$IDENTITIES" | sed -E 's/^[[:space:]]*[0-9]+\)[[:space:]]+[0-9A-Fa-f]+[[:space:]]+"(.*)"$/\1/')"
    # Fail loudly rather than silently handing briefcase a raw, unparsed
    # find-identity line -- exactly the failure mode above, if `security`
    # ever changes its output format again.
    [[ "$IDENTITY" == "Developer ID Application:"* ]] \
        || die "Could not parse a signing identity out of:
       $IDENTITIES
       Pass it explicitly instead: packaging/notarize-macos.sh --identity \"Developer ID Application: Name (TEAMID)\""
fi
ok "signing identity: $IDENTITY"

TEAM_ID="$(echo "$IDENTITY" | sed -nE 's/.*\(([A-Z0-9]+)\)$/\1/p')"
[[ -n "$TEAM_ID" ]] && ok "team ID: $TEAM_ID"

# 2. notarytool needs stored credentials. briefcase uses a keychain profile
#    named after the identity; if it is absent, briefcase prompts for an Apple
#    ID and an app-specific password the first time.
PROFILE="briefcase-macOS-${TEAM_ID:-unknown}"
if xcrun notarytool history --keychain-profile "$PROFILE" >/dev/null 2>&1; then
    ok "notarytool credentials found (keychain profile '$PROFILE')"
else
    warn "No stored notarytool credentials for profile '$PROFILE'."
    warn "briefcase will prompt for your Apple ID and an app-specific password."
    warn "Create one at https://account.apple.com > Sign-In and Security >"
    warn "App-Specific Passwords. Your normal Apple ID password will NOT work."
    warn "To store them yourself beforehand:"
    warn "  xcrun notarytool store-credentials \"$PROFILE\" \\"
    warn "      --apple-id \"you@example.com\" --team-id \"${TEAM_ID:-TEAMID}\" \\"
    warn "      --password \"xxxx-xxxx-xxxx-xxxx\""
fi

if [[ "$CHECK_ONLY" -eq 1 ]]; then
    echo; info "Preflight only (--check). Nothing was built."
    exit 0
fi

# ── Signed build + notarisation ──────────────────────────────────────────────
# The ad-hoc signature on an existing build cannot be notarised, so this always
# rebuilds and re-signs with the Developer ID. That also ensures the libusb the
# build script injects is signed with the same identity as everything else.
echo
info "Building and notarising (this takes several minutes)"
packaging/build-macos.sh --identity "$IDENTITY"

DMG="$(ls -t dist/*.dmg 2>/dev/null | head -1 || true)"
[[ -n "$DMG" ]] || die "No .dmg was produced."

# ── Prove it ─────────────────────────────────────────────────────────────────
# These are the checks that tell you whether it will work on someone else's Mac.
echo
info "Verifying the notarised result"
FAILED=0

if xcrun stapler validate "$DMG" >/dev/null 2>&1; then
    ok "notarisation ticket stapled to the .dmg"
else
    warn "no stapled ticket on the .dmg"; FAILED=1
fi

APP_PATH="build/g6_gui/macos/app/Sound Blaster X G6.app"
if [[ -d "$APP_PATH" ]]; then
    if codesign --verify --deep --strict --verbose=2 "$APP_PATH" 2>&1 | grep -q "satisfies its Designated Requirement"; then
        ok "app signature valid"
    else
        warn "app signature did not verify"; FAILED=1
    fi
    if codesign -d --verbose=2 "$APP_PATH" 2>&1 | grep -q "flags=.*runtime"; then
        ok "hardened runtime enabled"
    else
        warn "hardened runtime NOT enabled - Apple will reject this"; FAILED=1
    fi
    # The decisive one: this is what Gatekeeper does on the recipient's Mac.
    if spctl --assess --type execute --verbose=2 "$APP_PATH" 2>&1 | grep -qE "accepted"; then
        ok "Gatekeeper accepts the app"
    else
        warn "Gatekeeper does NOT accept the app"; FAILED=1
    fi
fi

echo
if [[ "$FAILED" -eq 0 ]]; then
    printf '\033[1;32mNotarised build ready:\033[0m %s\n' "$DMG"
    echo "  This can be downloaded and opened on any Mac with no Gatekeeper warning."
else
    printf '\033[1;31mNotarisation verification reported problems (see above).\033[0m\n'
    exit 1
fi
