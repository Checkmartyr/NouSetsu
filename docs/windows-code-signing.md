# Windows Code Signing

The published `v0.4.0` installer was built unsigned. Tauri signing support is
available as an opt-in build configuration, but Windows will only trust the
result after a trusted Authenticode code-signing certificate is installed and
configured. A self-signed certificate is not suitable for public distribution.

## Provision a certificate

Obtain a code-signing certificate from a trusted certificate authority or use a
managed signing service. The certificate must be valid for Code Signing and its
private key must be available to the Windows build account. This helper expects
the certificate in `Cert:\CurrentUser\My`.

Do not commit a PFX file, private key, or certificate password. For CI, use the
signing provider's supported secret or key-vault integration. A certificate
thumbprint is not a secret, but the private key is.

## Build a signed installer

From the repository root, set the certificate thumbprint and the RFC 3161
timestamp URL supplied by the certificate provider, then build with the
signing overlay:

```powershell
$env:NOUSETSU_WINDOWS_CERT_THUMBPRINT = "<certificate-thumbprint>"
$env:NOUSETSU_WINDOWS_TIMESTAMP_URL = "<provider-rfc3161-timestamp-url>"
cargo tauri build --config src-tauri/tauri.signing.conf.json --bundles nsis
```

The configuration invokes `src-tauri/sign-windows.ps1` for Tauri's Windows
binaries and installer. It uses `signtool.exe` from `PATH`, or the path in
`TAURI_WINDOWS_SIGNTOOL_PATH`, signs with SHA-256, timestamps the signature,
and verifies it. The default build remains unsigned so contributors without a
release certificate can still build locally.

Verify the generated installer:

```powershell
Get-AuthenticodeSignature .\src-tauri\target\release\bundle\nsis\Nousetsu_0.4.3_x64-setup.exe |
  Format-List Status, StatusMessage, SignerCertificate
```

`Status` should be `Valid` and `SignerCertificate` should identify the intended
publisher. SmartScreen reputation can still take time to build for a newly
signed publisher or file; signing removes the “Unknown publisher” state but
cannot guarantee that every first download is warning-free.

## Published installers

The `v0.4.0` and `v0.4.1` installers were built unsigned because no trusted
code-signing certificate was available for the release builds. Signing cannot
be applied retroactively to an uploaded installer. After provisioning a trusted
certificate, publish a newly built signed installer as a later patch release;
users must download that new installer.
