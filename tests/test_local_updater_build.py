import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import nousetsu.cli.local_updater_build as local_updater_build


def test_desktop_capability_grants_updater_to_the_loopback_backend_only():
    repo_root = Path(__file__).resolve().parents[1]
    capability = json.loads(
        (repo_root / "src-tauri" / "capabilities" / "default.json").read_text(encoding="utf-8")
    )

    assert capability["remote"]["urls"] == ["http://127.0.0.1:5174"]
    assert "updater:default" in capability["permissions"]


def test_local_updater_config_uses_loopback_without_changing_production_feed():
    repo_root = Path(__file__).resolve().parents[1]
    local_config = json.loads(
        (repo_root / "src-tauri" / "tauri.local-updater.conf.json").read_text(encoding="utf-8")
    )
    production_config = json.loads(
        (repo_root / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8")
    )

    assert local_config["plugins"]["updater"]["endpoints"] == [
        "http://127.0.0.1:8765/latest.json"
    ]
    assert local_config["plugins"]["updater"]["dangerousInsecureTransportProtocol"] is True
    assert production_config["plugins"]["updater"]["endpoints"] == [
        "https://github.com/Checkmartyr/NouSetsu/releases/latest/download/latest.json"
    ]
    assert "dangerousInsecureTransportProtocol" not in production_config["plugins"]["updater"]


def test_local_updater_build_uses_dotenv_signing_key_and_local_frontend_mode(
    tmp_path: Path, monkeypatch
):
    key_path = tmp_path / "keys" / "updater.key"
    key_path.parent.mkdir()
    key_path.write_text("test signing key", encoding="utf-8")
    (tmp_path / ".env").write_text(
        f'TAURI_SIGNING_PRIVATE_KEY="{key_path.as_posix()}"\n', encoding="utf-8"
    )
    monkeypatch.delenv("TAURI_SIGNING_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("VITE_LOCAL_UPDATER_TEST", raising=False)
    received = {}

    def fake_run(command, *, cwd, env):
        received.update(command=command, cwd=cwd, env=env)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(local_updater_build.subprocess, "run", fake_run)

    result = local_updater_build.build_local_updater(tmp_path)

    assert result == 0
    assert received["cwd"] == tmp_path
    assert received["env"]["TAURI_SIGNING_PRIVATE_KEY"] == str(key_path.resolve())
    assert received["env"]["VITE_LOCAL_UPDATER_TEST"] == "true"
    assert received["command"] == [
        "cargo",
        "tauri",
        "build",
        "--bundles",
        "nsis",
        "--config",
        "src-tauri/tauri.local-updater.conf.json",
    ]


def test_local_updater_build_can_set_a_newer_test_version(tmp_path: Path, monkeypatch):
    key_path = tmp_path / "updater.key"
    key_path.write_text("test signing key", encoding="utf-8")
    (tmp_path / ".env").write_text(
        f"TAURI_SIGNING_PRIVATE_KEY={key_path.as_posix()}\n", encoding="utf-8"
    )
    monkeypatch.delenv("TAURI_SIGNING_PRIVATE_KEY", raising=False)
    received = {}

    def fake_run(command, *, cwd, env):
        received["command"] = command
        version_config = Path(command[-1])
        received["version_config"] = json.loads(version_config.read_text(encoding="utf-8"))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(local_updater_build.subprocess, "run", fake_run)

    result = local_updater_build.build_local_updater(tmp_path, version="0.4.9")

    assert result == 0
    assert received["version_config"] == {"version": "0.4.9"}
    assert received["command"][-2] == "--config"


@pytest.mark.parametrize("configured_path", [None, "missing-updater.key"])
def test_local_updater_build_rejects_missing_or_invalid_key_without_echoing_it(
    tmp_path: Path, monkeypatch, configured_path: str | None
):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "UNRELATED_SETTING=preserved\n"
        if configured_path is None
        else f'TAURI_SIGNING_PRIVATE_KEY="{configured_path}"\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("TAURI_SIGNING_PRIVATE_KEY", raising=False)
    monkeypatch.setattr(
        local_updater_build.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("build must not run without a valid key"),
    )

    with pytest.raises(RuntimeError) as error:
        local_updater_build.build_local_updater(tmp_path)

    assert "TAURI_SIGNING_PRIVATE_KEY" in str(error.value)
    if configured_path:
        assert configured_path not in str(error.value)
