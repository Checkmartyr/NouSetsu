"""Build the Windows desktop app against a local updater feed."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import dotenv_values

from nousetsu.utils.env import find_repo_root


def build_local_updater(root: str | Path, version: str | None = None) -> int:
    project_root = Path(root).resolve()
    env_file = project_root / ".env"
    env_values = dotenv_values(env_file) if env_file.is_file() else {}
    signing_key = os.environ.get("TAURI_SIGNING_PRIVATE_KEY") or env_values.get(
        "TAURI_SIGNING_PRIVATE_KEY"
    )
    if not signing_key:
        raise RuntimeError(
            "Set TAURI_SIGNING_PRIVATE_KEY to the private-key file path in .env."
        )

    key_path = Path(signing_key).expanduser()
    if not key_path.is_absolute():
        key_path = project_root / key_path
    if not key_path.is_file():
        raise RuntimeError(
            "TAURI_SIGNING_PRIVATE_KEY must point to an existing private-key file."
        )

    build_env = os.environ.copy()
    build_env["TAURI_SIGNING_PRIVATE_KEY"] = str(key_path.resolve())
    build_env["TAURI_SIGNING_PRIVATE_KEY_PASSWORD"] = os.environ.get("TAURI_SIGNING_PRIVATE_KEY_PASSWORD") or env_values.get("TAURI_SIGNING_PRIVATE_KEY_PASSWORD")
    build_env["VITE_LOCAL_UPDATER_TEST"] = "true"
    command = [
        "cargo",
        "tauri",
        "build",
        "--bundles",
        "nsis",
        "--config",
        "src-tauri/tauri.local-updater.conf.json",
    ]
    with tempfile.TemporaryDirectory(prefix="nousetsu-local-updater-") as temp_dir:
        if version:
            version_config = Path(temp_dir) / "version.json"
            version_config.write_text(json.dumps({"version": version}), encoding="utf-8")
            command.extend(["--config", str(version_config)])
        return subprocess.run(command, cwd=project_root, env=build_env).returncode


def main(argv: list[str] | None = None) -> int:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Build NouSetsu with a local Tauri updater feed.")
    parser.add_argument("--version", help="Override the app version for the signed update build.")
    args = parser.parse_args(argv)
    try:
        return build_local_updater(find_repo_root(), version=args.version)
    except (OSError, RuntimeError) as error:
        print(f"Local updater build failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
