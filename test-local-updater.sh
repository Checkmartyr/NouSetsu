#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
update_version="${1:-0.4.9}"
if [[ ! "$update_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  printf 'Update version must use x.y.z format.\n' >&2
  exit 2
fi

printf 'Building the base local-updater installer...\n'
uv run python -m nousetsu.cli.local_updater_build

printf '\nInstall the base installer in your disposable Windows test environment.\n'
printf 'Installer directory: src-tauri/target/release/bundle/nsis/\n'
read -r -p 'After installing it and closing the app, press Enter to build the update: ' _

printf '\nBuilding local updater version %s...\n' "$update_version"
uv run python -m nousetsu.cli.local_updater_build --version "$update_version"

installer="src-tauri/target/release/bundle/nsis/Nousetsu_${update_version}_x64-setup.exe"
signature="${installer}.sig"
if [[ ! -f "$installer" || ! -f "$signature" ]]; then
  printf 'Expected installer and signature were not found for version %s.\n' "$update_version" >&2
  exit 1
fi

mkdir -p update-feed
cp -- "$installer" "$signature" update-feed/
printf '\nCopied installer and signature into update-feed/.\n'
printf 'Update latest.json with version %s, the matching signature, and installer URL.\n' "$update_version"
