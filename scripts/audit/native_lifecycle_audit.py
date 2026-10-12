"""Audit-owned process lifecycle checks; no Windows UI automation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import time

from settings_runtime_audit import ROOT, WORK, EVIDENCE, request, write_json, clean_environment


def stop(mode):
    profile = "release" if mode == "release" else "debug"
    marker = json.loads((WORK / f"native-{mode}-process.json").read_text(encoding="utf-8"))
    exe = Path(marker.get("executable", WORK / f"workspace/src-tauri/target/{profile}/nousetsu-desktop.exe"))
    assert exe.resolve().is_relative_to(WORK.resolve()) and exe.name == "nousetsu-desktop.exe"
    env = os.environ.copy()
    env["AUDIT_NATIVE_EXE"] = str(exe.resolve())
    script = r'''
$auditApps = @(Get-CimInstance Win32_Process -Filter "Name='nousetsu-desktop.exe'" | Where-Object { $_.ExecutablePath -eq $env:AUDIT_NATIVE_EXE })
if ($auditApps.Count -gt 1) { throw 'Ambiguous audit process; refusing shutdown' }
foreach ($auditApp in $auditApps) {
  $auditChildren = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($auditApp.ProcessId)" | Where-Object { $_.CommandLine -match '--port\s+15474' -and $_.Name -in @('python.exe','nousetsu-backend.exe') })
  foreach ($auditChild in $auditChildren) { Stop-Process -Id $auditChild.ProcessId -ErrorAction SilentlyContinue }
  Stop-Process -Id $auditApp.ProcessId -ErrorAction SilentlyContinue
}
Write-Output 'Stopped verified audit application and its own backend'
'''
    subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, check=True)


def verify_restart():
    path = EVIDENCE / "native-release-lifecycle.json"
    evidence = json.loads(path.read_text(encoding="utf-8"))
    env_file = Path(evidence["env_file_path"])
    config = Path(evidence["config_path"])
    assert "com.nousetsu.settingsaudit" in str(env_file)
    deadline = time.monotonic() + 100
    while time.monotonic() < deadline:
        try:
            status, response = request("http://127.0.0.1:15474", "/api/environment")
            if status == 200:
                break
        except OSError:
            time.sleep(.3)
    else:
        raise TimeoutError("Native restart API unavailable")
    evidence["env_sha256_after_restart"] = hashlib.sha256(env_file.read_bytes()).hexdigest()
    evidence["config_sha256_after_restart"] = hashlib.sha256(config.read_bytes()).hexdigest()
    evidence["observations"] = [{"case": "Packaged app restart preserves settings bytes and selected storage", "status": "pass" if evidence["env_sha256_before_restart"] == evidence["env_sha256_after_restart"] and evidence["config_sha256_before_restart"] == evidence["config_sha256_after_restart"] and Path(response["env_file_path"]).resolve() == env_file.resolve() else "fail", "setting_ids": []}]
    write_json(path, evidence)
    print(evidence["observations"][0]["status"])


def seed(action):
    path = EVIDENCE / "native-release-lifecycle.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    env_file = Path(data["env_file_path"])
    backup = WORK / "native-release-preserved.env"
    template = WORK / "workspace/src-tauri/target/release/defaults/.env.example"
    assert env_file.parent.name == "com.nousetsu.settingsaudit" and env_file.name == ".env"
    assert backup.resolve().is_relative_to(WORK.resolve())
    if action == "prepare-seed":
        assert not backup.exists(), "Do not overwrite a preserved audit settings file"
        shutil.move(str(env_file), str(backup))
    elif action == "verify-seed":
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                if request("http://127.0.0.1:15474", "/api/environment")[0] == 200:
                    break
            except OSError:
                time.sleep(.3)
        equal = hashlib.sha256(env_file.read_bytes()).digest() == hashlib.sha256(template.read_bytes()).digest()
        assert equal, "First-launch settings must match the shipped template"
        data["observations"].append({"case": "Missing audit .env seeded byte-for-byte from bundled template", "setting_ids": [], "status": "pass"})
        write_json(path, data)
        print("Fresh seeding passed")
    else:
        assert hashlib.sha256(env_file.read_bytes()).digest() == hashlib.sha256(template.read_bytes()).digest(), "Do not replace changed settings"
        env_file.unlink()
        shutil.move(str(backup), str(env_file))
        assert hashlib.sha256(env_file.read_bytes()).hexdigest() == data["env_sha256_after_restart"]
        print("Original audited settings restored")


def prepare_fallback():
    install = WORK / "blocked-install"
    install.mkdir(exist_ok=True)
    release = WORK / "workspace/src-tauri/target/release"
    shutil.copy2(release / "nousetsu-desktop.exe", install / "nousetsu-desktop.exe")
    shutil.copytree(release / "defaults", install / "defaults", dirs_exist_ok=True)
    for name in ("project", "logs"):
        assert not (install / name).is_dir()
        (install / name).write_text("Audit fixture blocks directory creation", encoding="utf-8")
    if not (install / "binaries").exists():
        env = os.environ.copy()
        env.update({"AUDIT_LINK": str(install / "binaries"), "AUDIT_TARGET": str(release / "binaries")})
        subprocess.run(["powershell", "-NoProfile", "-Command", "New-Item -ItemType Junction -Path $env:AUDIT_LINK -Target $env:AUDIT_TARGET | Out-Null"], env=env, check=True)
    print(str(install / "nousetsu-desktop.exe"))


def verify_fallback():
    path = EVIDENCE / "native-release-lifecycle.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    expected = Path(data["env_file_path"]).parent / "project"
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            status, projects = request("http://127.0.0.1:15474", "/api/projects")
            if status == 200:
                break
        except OSError:
            time.sleep(.3)
    assert Path(projects["projects_dir"]).resolve() == expected.resolve()
    assert (expected.parent / "logs").is_dir()
    data["observations"].append({"case": "Install directories blocked by owned regular files fall back to app data", "setting_ids": ["env.NOVEL_PROJECTS_DIR"], "status": "pass", "actual": str(expected), "limitation": "Filesystem creation failure tested; OS ACL/permission denial not simulated"})
    write_json(path, data)
    print("App-data fallback passed")


def verify_reuse():
    """Observe product startup reusing our deliberately incompatible storage context."""
    import socket
    import sys
    with socket.socket() as probe:
        assert probe.connect_ex(("127.0.0.1", 15474)) != 0, "Refuse an unrelated existing listener"
    fixture = WORK / "cross-mode-reuse"
    fixture.mkdir(exist_ok=True)
    source_env = fixture / "source.env"
    source_env.write_text("NOVEL_MODEL=mock-reuse-source\n", encoding="utf-8")
    env = clean_environment()
    import tomllib
    desktop_version = tomllib.loads((WORK / "workspace/src-tauri/Cargo.toml").read_text(encoding="utf-8"))["package"]["version"]
    env.update({"NOUSETSU_ENV_FILE": str(source_env), "NOUSETSU_LOGS_DIR": str(fixture / "logs"), "NOVEL_REGISTRY_DIR": str(WORK / "native-release/registry"), "NOUSETSU_DESKTOP_VERSION": desktop_version})
    log = (fixture / "source.log").open("w", encoding="utf-8")
    backend = subprocess.Popen([sys.executable, "-m", "nousetsu.desktop_backend", "--port", "15474"], cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    desktop = None
    try:
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            assert backend.poll() is None, "Owned source backend exited"
            try:
                if request("http://127.0.0.1:15474", "/api/desktop-info")[0] == 200:
                    break
            except OSError:
                time.sleep(.3)
        exe = WORK / "workspace/src-tauri/target/release/nousetsu-desktop.exe"
        desktop = subprocess.Popen([str(exe)], cwd=exe.parent, env=clean_environment(), stdout=log, stderr=log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        desktop_log = exe.parent / "logs/desktop.log"
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if "Reusing existing compatible backend" in desktop_log.read_text(encoding="utf-8").split("initializing")[-1]:
                break
            time.sleep(.2)
        else:
            raise AssertionError("Packaged app did not confirm owned backend reuse")
        status, actual = request("http://127.0.0.1:15474", "/api/environment")
        assert status == 200 and Path(actual["env_file_path"]).resolve() == source_env.resolve()
        write_json(EVIDENCE / "native-backend-reuse.json", {"case": "Packaged app reuses source backend by version despite different settings file", "status": "pass", "classification": "Observed sharing behavior; installation-affinity policy is not established", "advertised_fixture_version": desktop_version, "actual_settings_path": str(source_env), "packaged_default_settings_context": "App-data .env and bundled sidecar when a new backend is spawned", "owned_source_pid": backend.pid, "desktop_pid": desktop.pid, "recommendation": "Show backend mode, owner and storage context; validate installation identity if per-install defaults are intended"})
        print("Reproduced compatible-version backend storage-context mismatch")
    finally:
        for process in (desktop, backend):
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=15)
        log.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("stop-dev", "stop-release", "verify-restart", "prepare-seed", "verify-seed", "restore-seed", "prepare-fallback", "verify-fallback", "verify-reuse"))
    args = parser.parse_args()
    if args.action == "verify-restart":
        verify_restart()
    elif args.action.endswith("seed"):
        seed(args.action)
    elif args.action == "prepare-fallback":
        prepare_fallback()
    elif args.action == "verify-fallback":
        verify_fallback()
    elif args.action == "verify-reuse":
        verify_reuse()
    else:
        stop(args.action.removeprefix("stop-"))
