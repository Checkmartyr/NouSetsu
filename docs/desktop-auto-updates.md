# Desktop Auto-Updates

NouSetsu's Tauri desktop app uses the Tauri updater to check, download, verify,
and install Windows NSIS updates from inside **Settings → App Updates**. The
installer updates the desktop frontend and bundled Python backend together; the
user does not need to open GitHub or manually download a setup file.

## Update signing

Tauri updater signatures are separate from Windows Authenticode code signing.
The updater verifies every downloaded installer against the public key in
`src-tauri/tauri.conf.json`; it will not install unsigned or incorrectly signed
updates. Authenticode signing can additionally establish a Windows publisher
identity, but is not required for updater signature verification.

The updater keypair for this checkout was generated with:

```powershell
cargo tauri signer generate --write-keys "$env:USERPROFILE\.tauri\nousetsu-updater.key" --ci
```

The private key is stored outside the repository at
`%USERPROFILE%\.tauri\nousetsu-updater.key`. It was generated without a
password; restrict access to this file and keep a secure backup. **Never commit
or share the private key.** The corresponding public key is safe to commit and
is embedded in the Tauri configuration.

Before publishing, add a repository Actions secret named
`TAURI_SIGNING_PRIVATE_KEY` containing the private key file's contents. The
workflow also references `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`; leave that
secret unset for this unencrypted key. If the key is lost, existing installations
that trust its public key cannot receive signed updates. Do not rotate it without
a migration plan.

## Release workflow

Pushing a version tag such as `v0.4.5` runs
`.github/workflows/desktop-release.yml`. The tag must match the versions in
`pyproject.toml`, `src-tauri/Cargo.toml`, and `src-tauri/tauri.conf.json`. The
workflow installs build dependencies, runs the Python tests, builds the NSIS
installer with updater artifacts enabled, and publishes the signed installer
and Tauri `latest.json` manifest to the GitHub Release. The manifest is the
HTTPS update feed configured in `tauri.conf.json`.

Regular local development builds do not require the private updater key. To
build updater artifacts manually, set `TAURI_SIGNING_PRIVATE_KEY` to the key
path outside the repository and use the updater config overlay:

```powershell
$env:TAURI_SIGNING_PRIVATE_KEY = "$env:USERPROFILE\.tauri\nousetsu-updater.key"
cargo tauri build --bundles nsis --config src-tauri/tauri.updater.conf.json
```

The manual build creates a `.sig` file next to the installer. A release must
also publish a compatible `latest.json`; prefer the configured GitHub Actions
workflow, which creates that manifest and attaches it to the release.

## Local updater testing

Local updater tests use a separate Tauri config overlay that points to
`http://127.0.0.1:8765/latest.json` and enables HTTP only for that loopback feed.
The local build also disables the Settings screen fallback to the GitHub release
API. The production endpoint and fallback are unchanged.

Put the **path** to the existing private key in the root `.env`; do not put the
key contents there:

```dotenv
TAURI_SIGNING_PRIVATE_KEY=C:/Users/<user>/.tauri/nousetsu-updater.key
```

Build and install a local-test version, then build a newer signed update without
editing the project version files:

```powershell
uv run python -m nousetsu.cli.local_updater_build
uv run python -m nousetsu.cli.local_updater_build --version 0.4.9
```

The first command uses the configured app version; `--version` sets the Tauri
app version for the update build. Each build creates the signed NSIS installer
and its `.sig` file under `src-tauri/target/release/bundle/nsis/`.

Copy the newer installer and its matching `.sig` file into a local feed directory
alongside a Tauri updater manifest, for example:

```json
{
  "version": "0.4.9",
  "notes": "Local updater test",
  "pub_date": "2026-09-29T00:00:00Z",
  "platforms": {
    "windows-x86_64": {
      "signature": "<contents of the matching installer .sig file>",
      "url": "http://127.0.0.1:8765/Nousetsu_0.4.9_x64-setup.exe"
    }
  }
}
```

Serve that directory in a separate terminal:

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory path\to\update-feed
```

Install the older local-test build in a disposable Windows environment, start
the local server, then use **Settings → App Updates**. Verify the newer version
and release notes, start the install, observe download progress, and confirm the
app relaunches into the newer version. The local-test Settings flow reports
no-update and feed-error states without calling the GitHub release API. The
update installer still requires a valid signature matching the configured
updater public key. Use a VM or disposable installation: the NSIS installer may
update an existing NouSetsu installation.

For a signature-rejection check, temporarily change one character in the
manifest signature and attempt installation in the disposable environment. The
installer should fail verification without installing or relaunching; restore
the matching signature before testing a successful update.

Do not use the local updater overlay for releases. Its insecure HTTP allowance
is restricted to the loopback test endpoint and must not be shipped.

## First updater-enabled version

NouSetsu `0.4.1` predates the updater plugin and cannot update itself. Users
already on `0.4.1` must install the first updater-enabled release once using its
setup installer. Subsequent signed releases can be installed from inside the
app. Because the current updater key is not a Windows Authenticode certificate,
SmartScreen may still warn that an installer has an unknown publisher.
