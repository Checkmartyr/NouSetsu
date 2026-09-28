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

Pushing a version tag such as `v0.4.2` runs
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

## First updater-enabled version

NouSetsu `0.4.1` predates the updater plugin and cannot update itself. Users
already on `0.4.1` must install the first updater-enabled release once using its
setup installer. Subsequent signed releases can be installed from inside the
app. Because the current updater key is not a Windows Authenticode certificate,
SmartScreen may still warn that an installer has an unknown publisher.
