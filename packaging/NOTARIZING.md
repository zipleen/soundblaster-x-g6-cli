# Notarising the macOS app

The default build is **ad-hoc signed**: it runs fine on your own Macs, but a
*downloaded* copy is quarantined by macOS and Gatekeeper refuses it with
*"cannot be opened because the developer cannot be verified"*.

Notarising removes that. It means Apple has scanned the build and issued a
ticket that macOS checks on first launch.

Everything below happens on the Mac that has your Apple Developer account.

---

## What you need (one-time)

### 1. A paid Apple Developer Program membership

$99/year, at <https://developer.apple.com/programs/>. A free Apple ID cannot
create the certificate this needs.

### 2. Full Xcode

Not just the command line tools — `notarytool` ships inside Xcode.

```bash
xcode-select -p                              # should print a path inside Xcode.app
sudo xcode-select -s /Applications/Xcode.app # if it points at CommandLineTools
```

### 3. A "Developer ID Application" certificate

In Xcode: **Settings → Accounts → (your Apple ID) → Manage Certificates → + →
Developer ID Application**.

Confirm it landed in your keychain:

```bash
security find-identity -v -p codesigning | grep "Developer ID Application"
```

You should see something like:

```
1) A1B2C3... "Developer ID Application: Your Name (ABCDE12345)"
```

The `ABCDE12345` part is your **Team ID**.

> An **Apple Development** certificate is not enough. Only a **Developer ID
> Application** certificate can be notarised for distribution outside the App
> Store.

### 4. An app-specific password

Notarisation authenticates as you, and your normal Apple ID password will not
work. Create one at <https://account.apple.com> → **Sign-In and Security → App-
Specific Passwords**. It looks like `abcd-efgh-ijkl-mnop`. Save it somewhere —
it is shown only once.

### 5. Store the credentials (optional but recommended)

If you skip this, the build prompts you for them the first time.

```bash
xcrun notarytool store-credentials "briefcase-macOS-ABCDE12345" \
    --apple-id "you@example.com" \
    --team-id "ABCDE12345" \
    --password "abcd-efgh-ijkl-mnop"
```

The profile name must be `briefcase-macOS-<TEAM_ID>` for the build to find it.

---

## Building a notarised release

```bash
git clone git@github.com:zipleen/soundblaster-x-g6-cli.git
cd soundblaster-x-g6-cli

brew install libusb python@3.12     # build-time only

packaging/notarize-macos.sh --check # verify the setup above, build nothing
packaging/notarize-macos.sh         # full signed + notarised build
```

The script picks your Developer ID automatically when there is exactly one. With
several, name it:

```bash
packaging/notarize-macos.sh --identity "Developer ID Application: Your Name (ABCDE12345)"
```

Expect it to take several minutes — most of that is Apple's scan.

The result is `dist/Sound Blaster X G6-<version>.dmg`, which anyone can download
and open with no warning.

---

## Why it rebuilds instead of notarising the existing app

An ad-hoc signature cannot be notarised. Every binary has to be re-signed with
your Developer ID and the hardened runtime enabled, so the script always does a
full signed build. That also guarantees the bundled `libusb` is signed with the
same identity as everything else — a mismatch there is a common cause of
rejection.

## What the script checks afterwards

- the notarisation ticket is **stapled** to the `.dmg` (so it works offline)
- the app signature verifies
- the **hardened runtime** is enabled — Apple rejects builds without it
- `spctl --assess` accepts the app, which is what Gatekeeper does on someone
  else's Mac

## Troubleshooting

| Symptom | Cause |
|---|---|
| `No 'Developer ID Application' certificate found` | Step 3 above, or the certificate is in a different keychain / user account. |
| `HTTP status code: 401` / invalid credentials | You used your Apple ID password. It must be an **app-specific** password (step 4). |
| `The signature does not include a secure timestamp` | Signing needs network access to Apple's timestamp server. |
| `The executable does not have the hardened runtime enabled` | Something re-signed the app after the build. Re-run the script. |
| Notarisation is rejected without a clear reason | Ask Apple for the detail: `xcrun notarytool log <submission-id> --keychain-profile "briefcase-macOS-<TEAM_ID>"` |

## Building on a different Mac later

Certificates are tied to the keychain that created them. To move one, export it
from Keychain Access (**My Certificates → right-click → Export**, giving a
`.p12` and a password) and import it on the other machine. Without the private
key, that Mac cannot sign.

## Notarising from CI

The release workflow (`.github/workflows/macos-release.yml`) builds ad-hoc,
because notarisation needs your certificate and Apple credentials as repository
secrets. To do it in CI you would export the `.p12`, add it plus the app-specific
password as encrypted secrets, import it into a temporary keychain during the
run, and pass `--identity` to `packaging/build-macos.sh`. Worth doing only if you
cut releases often; otherwise running this script locally is simpler and keeps
your signing key off GitHub.
