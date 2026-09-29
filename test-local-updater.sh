#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
update_version="${1:-0.4.9}"

printf 'Building the base local-updater installer...\n'
uv run python -m nousetsu.cli.local_updater_build

printf '\nInstall the base installer in your disposable Windows test environment.\n'
printf 'Installer directory: src-tauri/target/release/bundle/nsis/\n'
read -r -p 'After installing it and closing the app, press Enter to build the update: ' _

printf '\nBuilding local updater version %s...\n' "$update_version"
uv run python -m nousetsu.cli.local_updater_build --version "$update_version"

printf '\nCopy the newer installer and matching .sig into your update feed.\n'
printf 'Update latest.json with version %s, the matching signature, and installer URL.\n' "$update_version"
