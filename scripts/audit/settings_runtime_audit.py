"""Isolated settings audit: snapshot preparation, local provider and frozen probes.

This script observes product behavior; it does not repair it. Synthetic credentials
are used only with loopback transports. Build files and projects stay in ignored
src-tauri/target/settings-repair; evidence excludes request headers and prompts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import tempfile
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "src-tauri" / "target" / "settings-repair"
EVIDENCE = ROOT / "audit-results" / "settings-repair"
ROLES = ("extractor", "drafter", "critic", "polisher", "chronicler", "scraper")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def clean_environment() -> dict[str, str]:
    return {
        key: value for key, value in os.environ.items()
        if not key.startswith(("NOVEL_", "NOUSETSU_", "CUSTOM_API_"))
        and key not in {"DEFAULT_MODEL", "SOURCE_LANG", "TARGET_LANG", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "PYTHON_DOTENV_DISABLED"}
    }


def request(base: str, path: str, body: object = None, method: str | None = None,
            headers: dict[str, str] | None = None) -> tuple[int, object]:
    """Use current revisions for ordinary audit saves; explicit headers test conflicts."""
    data = None if body is None else json.dumps(body).encode()
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    if method == "PUT" and path.split("?")[0] in {"/api/settings", "/api/environment"} and headers is None:
        status, current = request(base, path)
        if status != 200 or not isinstance(current, dict) or not current.get("revision"):
            raise RuntimeError("Settings snapshot unavailable before save")
        request_headers["If-Match"] = '"' + current["revision"] + '"'
    req = Request(base + path, data=data, method=method, headers=request_headers)
    try:
        with urlopen(req, timeout=25) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def prepare() -> None:
    workspace = WORK / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    for folder in ("src", "web/src", "web/public", "src-tauri/src", "src-tauri/icons", "src-tauri/capabilities", "modules/novel_scraper/src"):
        if (ROOT / folder).exists():
            shutil.copytree(ROOT / folder, workspace / folder, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))
    for file in ("pyproject.toml", "uv.lock", ".env.example", "web/package.json", "web/package-lock.json", "web/tsconfig.json", "web/vite.config.ts", "web/index.html", "src-tauri/Cargo.toml", "src-tauri/Cargo.lock", "src-tauri/build.rs", "src-tauri/tauri.conf.json", "src-tauri/build_sidecar.py"):
        if (ROOT / file).exists():
            target = workspace / file
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / file, target)
    # Read-only dependency reuse; npm build writes only this snapshot's dist/cache.
    junction = workspace / "web" / "node_modules"
    if not junction.exists():
        if os.name == "nt":
            junction_env = os.environ.copy()
            junction_env.update({"AUDIT_DEP_LINK": str(junction), "AUDIT_DEP_TARGET": str(ROOT / "web/node_modules")})
            subprocess.run(["powershell", "-NoProfile", "-Command", "New-Item -ItemType Junction -Path $env:AUDIT_DEP_LINK -Target $env:AUDIT_DEP_TARGET | Out-Null"], env=junction_env, check=True)
        else:
            junction.symlink_to(ROOT / "web/node_modules", target_is_directory=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    artifacts = {}
    for rel in ("src-tauri/target/release/nousetsu-desktop.exe", "src-tauri/binaries/nousetsu-backend/nousetsu-backend.exe", "web/dist/index.html"):
        path = ROOT / rel
        if path.is_file():
            artifacts[rel] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size": path.stat().st_size, "mtime": path.stat().st_mtime, "source_identity": "unverified existing artifact"}
    config = {
        "identifier": "com.nousetsu.settingsrepair",
        "productName": "NouSetsu Settings Audit",
        "build": {"beforeBuildCommand": "", "beforeDevCommand": "", "frontendDist": str(workspace / "web/dist"), "devUrl": "http://127.0.0.1:5187"},
        "app": {"windows": [{"title": "NouSetsu Settings Audit", "width": 1440, "height": 900, "minWidth": 1024, "minHeight": 700}]},
        "plugins": {"updater": {"endpoints": ["http://127.0.0.1:5194/audit-updates"], "dangerousInsecureTransportProtocol": True}},
    }
    write_json(WORK / "tauri-audit.json", config)
    source_hashes = {}
    for folder in ("src", "web/src", "web/public", "src-tauri/src", "modules/novel_scraper/src"):
        for source_path in sorted((workspace / folder).rglob("*")):
            if source_path.is_file() and "__pycache__" not in source_path.parts:
                source_hashes[source_path.relative_to(workspace).as_posix()] = hashlib.sha256(source_path.read_bytes()).hexdigest()
    for relative in ("pyproject.toml", "uv.lock", ".env.example", "web/package.json", "web/package-lock.json", "src-tauri/Cargo.toml", "src-tauri/Cargo.lock", "src-tauri/tauri.conf.json", "src-tauri/build_sidecar.py"):
        if (workspace / relative).is_file():
            source_hashes[relative] = hashlib.sha256((workspace / relative).read_bytes()).hexdigest()
    write_json(EVIDENCE / "provenance.json", {"source_commit": commit, "workspace": str(workspace), "audit_identifier": config["identifier"], "source_snapshot_hashes": source_hashes, "existing_artifacts": artifacts})
    print(str(workspace))


class ProviderStub(BaseHTTPRequestHandler):
    captures: list[dict] = []
    capture_lock = threading.Lock()
    evidence_file = EVIDENCE / "provider-captures.json"
    audit_gets: list[str] = []

    def log_message(self, *args: object) -> None:
        pass

    def send_json(self, value: object, status: int = 200) -> None:
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_CONNECT(self) -> None:
        self.send_error(502, "Audit refuses external tunnels")

    def do_GET(self) -> None:
        if self.server.server_port == 5194:
            self.audit_gets.append(self.path)
            write_json(EVIDENCE / "native-transport-requests.json", self.audit_gets)
        if self.path == "/audit-updates":
            self.send_response(204)
            self.end_headers()
            return
        self.send_json({"object": "list", "data": [{"id": "audit-" + role, "object": "model"} for role in ROLES]})

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        model = body.get("model", "")
        capture = {key: body.get(key) for key in ("model", "temperature", "reasoning_effort", "max_tokens", "response_format", "stream") if key in body}
        with self.capture_lock:
            self.captures.append(capture)
            write_json(self.evidence_file, self.captures)
        role = model.removeprefix("audit-")
        content = {
            "extractor": '{"new_characters": [], "new_terms": [], "active_terms_in_chapter": []}',
            "critic": '{"fidelity_score": 9.5, "style_score": 9.2, "glossary_compliance_pct": 100.0, "warnings": [], "critique_notes": "Audit fixture is faithful."}',
            "chronicler": '{"chapter_num": 1, "title": "Audit", "synopsis": "A traveler begins a journey.", "key_events": ["Departure"], "character_state_changes": [], "reconciled_characters": [], "reconciled_terms": []}',
        }.get(role, "# Chapter 1: Audit\n\nA traveler stepped forward and began a journey.")
        # Native structured-output calls can choose function calling.
        tools = body.get("tools") or []
        message = {"role": "assistant", "content": content}
        if tools and role in {"extractor", "critic", "chronicler"}:
            message = {"role": "assistant", "content": None, "tool_calls": [{"id": "audit-call", "type": "function", "function": {"name": tools[0]["function"]["name"], "arguments": content}}]}
        self.send_json({"id": "audit-response", "object": "chat.completion", "created": int(time.time()), "model": model, "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls" if message.get("tool_calls") else "stop"}], "usage": {"prompt_tokens": 40, "completion_tokens": 20, "total_tokens": 60}})


def start_stub(port: int = 5193) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), ProviderStub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def frozen_audit(binary: Path, port: int = 5191, source: bool = False) -> None:
    for owned_port in (port, 5193):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", owned_port)) == 0:
                raise RuntimeError(f"Port {owned_port} already has a listener; refusing audit writes")
    WORK.mkdir(parents=True, exist_ok=True)
    mode = "source" if source else "frozen"
    result_path = EVIDENCE / f"{mode}-results.json"
    fixture = Path(tempfile.mkdtemp(prefix=f"{mode}-{port}-", dir=WORK))
    env_file = fixture / ".env"
    env_file.write_text("NOVEL_MODEL='custom:audit-drafter'\nNOVEL_FALLBACK_MODEL='custom:audit-drafter'\nCUSTOM_API_KEY='synthetic-audit-key'\nCUSTOM_API_BASE_URL='http://127.0.0.1:5193/v1'\nNOVEL_MAX_TPM='1000000'\nNOVEL_MAX_RPM='10000'\n", encoding="utf-8")
    env = clean_environment()
    env.update({"NOUSETSU_ENV_FILE": str(env_file), "NOUSETSU_APP_DATA_DIR": str(fixture), "NOUSETSU_LOGS_DIR": str(fixture / "logs"), "NOVEL_REGISTRY_DIR": str(fixture / "registry"), "NOVEL_PROJECTS_DIR": str(fixture / "projects")})
    env.update({"HTTPS_PROXY": "http://127.0.0.1:5193", "HTTP_PROXY": "http://127.0.0.1:5193", "NO_PROXY": "127.0.0.1,localhost,::1"})
    base = f"http://127.0.0.1:{port}"
    records: list[dict] = []
    write_json(result_path, [{"case": "audit_run", "status": "blocked", "reason": "New run started; no observations completed yet"}])
    stub = start_stub()
    log = (fixture / "backend.log").open("w", encoding="utf-8")
    command = [sys.executable, "-m", "nousetsu.desktop_backend", "--port", str(port)] if source else [str(binary), "--port", str(port)]
    process = subprocess.Popen(command, cwd=fixture, env=env, stdout=log, stderr=log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        deadline = time.monotonic() + 100
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Sidecar exited {process.returncode}; inspect isolated log {log.name}")
            try:
                if request(base, "/api/desktop-info")[0] == 200:
                    break
            except (URLError, OSError):
                time.sleep(0.3)
        else:
            raise TimeoutError("Frozen backend did not become ready")
        status, settings = request(base, "/api/environment")
        assert status == 200 and Path(settings["env_file_path"]).resolve() == env_file.resolve()
        records.append({"case": "isolated_environment", "status": "pass", "path": str(env_file), "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()})
        projects = []
        for title, folder in (("Audit A", "audit-a"), ("Audit B", "audit-b")):
            status, created = request(base, "/api/projects/create", {"title": title, "folder_name": folder, "source_language": "Japanese", "target_language": "English"})
            assert status == 200, created
            projects.append(created["active_project"]["path"])
        creation_values = {"title": "Creation 日本語", "folder_name": "creation space", "source_language": "Korean", "target_language": "English", "genre": "romance", "model": "mock-audit-created"}
        status, created = request(base, "/api/projects/create", creation_values)
        assert status == 200, created
        created_path = created["active_project"]["path"]
        created_cfg = request(base, "/api/settings?" + urlencode({"project_path": created_path}))[1]["config"]
        for key, expected in creation_values.items():
            actual = Path(created_path).name if key == "folder_name" else created_cfg["model_name" if key == "model" else key]
            assert actual == expected
            records.append({"case": "project_creation_explicit", "setting_id": "creation." + key, "status": "pass", "actual": actual, "expected": expected})
        assert request(base, "/api/environment", {"values": {"SOURCE_LANG": "Chinese", "TARGET_LANG": "French"}}, "PUT")[0] == 200
        status, created = request(base, "/api/projects/create", {"title": "Inherited Creation", "folder_name": "inherited-creation"})
        assert status == 200
        inherited_cfg = request(base, "/api/settings?" + urlencode({"project_path": created["active_project"]["path"]}))[1]["config"]
        for key, expected in (("source_language", "Chinese"), ("target_language", "French")):
            assert inherited_cfg[key] == expected
            records.append({"case": "project_creation_inherited", "setting_id": "creation." + key, "status": "pass", "actual": inherited_cfg[key], "expected": expected})
        assert request(base, "/api/environment", {"values": {"SOURCE_LANG": "", "TARGET_LANG": ""}}, "PUT")[0] == 200
        logs_status, logs = request(base, "/api/logs/info")
        records.append({"case": "isolated_logs_diagnostics", "setting_id": "action.logs_refresh", "status": "pass" if logs_status == 200 else "fail"})
        query = "?" + urlencode({"project_path": projects[0]})
        initial = request(base, "/api/settings" + query)[1]
        config = initial["config"]
        readonly = request(base, "/api/settings" + query, {"created_at": "changed"}, "PUT")
        records.append({"case": "readonly_created_at", "setting_id": "project.created_at", "status": "pass" if readonly[0] == 422 and request(base, "/api/settings" + query)[1]["created_at"] == initial["created_at"] else "fail"})
        updates_status, updates = request(base, "/api/updates/latest")
        records.append({"case": "updates_controlled_external_transport_failure", "setting_id": "action.check_updates", "status": "pass" if updates_status == 502 and isinstance(updates.get("detail"), str) else "fail", "response_status": updates_status, "transport": "Loopback proxy refuses CONNECT; no external update request or installation"})
        edits = {"title": "Audit changed 日本", "project_id": "audit-project", "source_language": "Japanese", "target_language": "English", "genre": "romance", "raw_dir": "raw space", "output_dir": "translated space", "model_name": "custom:audit-drafter", "fallback_model": "custom:audit-polisher", "max_tpm": 1000000, "max_rpm": 10000, "max_review_loops": 2, "quality_threshold": 9.0, "chunk_threshold_lines": 24, "target_chunk_lines": 12, "chunk_overlap_lines": 0, "rag_top_k": 3, "rag_embedding_model": "mock-embedding", "rag_reranker_model": "custom:audit-critic", "safety_subdivision_min_lines": 4, "safety_subdivision_max_depth": 2}
        for key, value in config.items():
            if isinstance(value, bool):
                edits[key] = not value
        edits.update({f"{role}_model": "custom:audit-" + role for role in ROLES})
        edits["filter_extractor_entities"] = False
        edits.update({"use_interactions_api": False, "enable_post_polish_reconciliation": False,
                      "enable_procedural_graph_learning": False, "procedural_learning_cadence": "both",
                      "procedural_learning_interval": 4, "procedural_learning_min_failures": 2,
                      "procedural_refiner_model": "custom:audit-critic"})
        edits["generation_settings"] = {role: {"temperature": (i + 1) / 10, "thinking_level": "low", "thinking_budget": 0, "use_interactions_api": False} for i, role in enumerate(ROLES)}
        status, saved = request(base, "/api/settings" + query, edits, "PUT")
        assert status == 200, saved
        got = request(base, "/api/settings" + query)[1]["config"]
        for key, expected in edits.items():
            records.append({"case": "valid_roundtrip", "setting_id": "project." + key, "status": "pass" if got.get(key) == expected else "fail", "expected": expected, "actual": got.get(key)})
        b = request(base, "/api/settings?" + urlencode({"project_path": projects[1]}))[1]
        records.append({"case": "project_isolation", "status": "pass" if b["title"] == "Audit B" else "fail"})
        from nousetsu.utils.env import ENV_CONFIG_KEYS, ENV_SECRET_KEYS
        global_values = {}
        for key in ENV_CONFIG_KEYS:
            if key.endswith("_MODEL") or key in {"DEFAULT_MODEL", "NOVEL_MODEL"}:
                value = "mock-embedding" if "EMBEDDING" in key else "custom:audit-drafter"
                for role in ROLES:
                    if key == f"NOVEL_{role.upper()}_MODEL":
                        value = "custom:audit-" + role
            elif "TEMPERATURE" in key:
                value = "0.7"
            elif "THINKING_LEVEL" in key:
                value = "low"
            elif "THINKING_BUDGET" in key:
                value = "0"
            elif "USE_INTERACTIONS" in key or key in {"NOVEL_FILTER_EXTRACTOR_ENTITIES", "NOVEL_POST_POLISH_RECONCILIATION"}:
                value = "false"
            elif key == "NOVEL_ENABLE_PROCEDURAL_GRAPH_LEARNING":
                value = "false"
            elif key == "NOVEL_PROCEDURAL_LEARNING_CADENCE":
                value = "both"
            elif key in {"NOVEL_PROCEDURAL_LEARNING_INTERVAL", "NOVEL_PROCEDURAL_LEARNING_MIN_FAILURES"}:
                value = "2"
            elif key == "SOURCE_LANG":
                value = "Chinese"
            elif key == "TARGET_LANG":
                value = "English"
            elif key == "NOVEL_MAX_TPM":
                value = "1000000"
            elif key == "NOVEL_MAX_RPM":
                value = "10000"
            elif key == "NOVEL_MAX_REVIEW_LOOPS":
                value = "1"
            elif key == "NOVEL_QUALITY_THRESHOLD":
                value = "9.0"
            elif key == "NOVEL_PROJECTS_DIR":
                value = str(fixture / "projects")
            elif key == "CUSTOM_API_BASE_URL":
                value = "http://127.0.0.1:5193/v1"
            else:
                value = "audit-unused-path"
            global_values[key] = value
        secrets = {key: "synthetic-" + key.lower() for key in ENV_SECRET_KEYS}
        status, saved_env = request(base, "/api/environment", {"values": global_values, "api_keys": secrets}, "PUT")
        assert status == 200, saved_env
        for key, value in global_values.items():
            records.append({"case": "global_valid_roundtrip", "setting_id": "env." + key, "status": "pass" if saved_env["values"].get(key) == value else "fail"})
        response_text = json.dumps(saved_env)
        for key, value in secrets.items():
            records.append({"case": "secret_roundtrip_redaction", "setting_id": "env." + key, "status": "pass" if saved_env["api_key_status"].get(key) and value not in response_text else "fail"})
        request(base, "/api/environment", {"clear_api_keys": [key for key in ENV_SECRET_KEYS if key != "CUSTOM_API_KEY"]}, "PUT")
        catalog = request(base, "/api/model-catalog?provider=custom")
        records.append({"case": "local_provider_catalog", "status": "pass" if catalog[0] == 200 and catalog[1].get("configured") else "fail", "response": catalog})
        # A valid setting save is distinct from proving the pipeline consumes it.
        runtime_settings = {"raw_dir": "raw_chapters", "output_dir": "translated_chapters", "enable_rag": False, "enable_chunking": False, "auto_update_bible": True, "max_review_loops": 1}
        runtime_save = request(base, "/api/settings" + query, runtime_settings, "PUT")
        assert runtime_save[0] == 200, runtime_save
        upload = request(base, "/api/chapters/upload", {"project_path": projects[0], "files": [{"name": "0001.txt", "content": "第一章\n旅人は歩き始めた。"}]})
        assert upload[0] == 200, upload
        ProviderStub.captures = []
        start = request(base, "/api/translate/start", {"project_path": projects[0], "limit": 1})
        assert start[0] == 200, start
        records.append({"case": "translation_start", "response": start})
        deadline = time.monotonic() + 80
        while time.monotonic() < deadline:
            job = request(base, "/api/translate/status")[1]
            if not job.get("is_running", job.get("running", False)):
                break
            time.sleep(0.3)
        captures = ProviderStub.captures
        expected_payloads = {"audit-" + role: (i + 1) / 10 for i, role in enumerate(ROLES[:5])}
        observed_payloads = {call["model"]: call.get("temperature") for call in captures}
        output_files = list((Path(projects[0]) / "translated_chapters").glob("*.md"))
        metadata_path = Path(projects[0]) / ".novel/metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else {}
        completed = any(chapter.get("checkpoint", {}).get("status", "").upper() == "COMPLETED" for chapter in metadata.get("chapters", {}).values())
        passed = all(observed_payloads.get(model) == temperature for model, temperature in expected_payloads.items()) and bool(output_files) and completed and not job.get("is_running")
        records.append({"case": "runtime_provider_payloads", "status": "pass" if passed else "fail", "job": job, "captures": captures, "outputs": [path.name for path in output_files], "metadata": metadata})
        before_restart = request(base, "/api/settings" + query)[1]["config"]
        process.terminate()
        process.wait(timeout=10)
        process = subprocess.Popen(command, cwd=fixture, env=env, stdout=log, stderr=log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        deadline = time.monotonic() + 100
        while time.monotonic() < deadline:
            try:
                after_restart = request(base, "/api/settings" + query)
                if after_restart[0] == 200:
                    break
            except (URLError, OSError):
                time.sleep(0.3)
        else:
            raise TimeoutError("Frozen restart did not become ready")
        records.append({"case": "restart_config", "status": "pass" if after_restart[1]["config"] == before_restart else "fail", "settings": list(before_restart)})
        ignored = request(base, "/api/settings" + query, {"procedural_learning_interval": 7}, "PUT")
        ignored_cfg = request(base, "/api/settings" + query)[1]["config"]
        records.append({"case": "procedural_setting_persistence", "setting_id": "project.procedural_learning_interval", "status": "pass" if ignored[0] == 200 and ignored_cfg.get("procedural_learning_interval") == 7 else "fail"})
        # Invalid input: observe both save outcome and the subsequent model reload.
        response = request(base, "/api/settings" + query, {"max_review_loops": 99}, "PUT")
        reread = request(base, "/api/settings" + query)[1]
        records.append({"case": "invalid_review_loop", "status": "pass" if response[0] == 422 and reread["config"] == ignored_cfg else "fail", "save_status": response[0], "after_title": reread.get("title"), "after_loops": reread.get("max_review_loops")})
        missing = request(base, "/api/settings" + query, {"title": "Missing revision"}, "PUT", headers={})
        stale = request(base, "/api/settings" + query, {"title": "Stale revision"}, "PUT", headers={"If-Match": '"obsolete"'})
        records.append({"case": "required_revision", "status": "pass" if missing[0] == 428 and stale[0] == 412 and request(base, "/api/settings" + query)[1]["config"] == ignored_cfg else "fail"})
        write_json(result_path, records)
        print(json.dumps({"cases": len(records), "failed_observations": sum(r.get("status") == "fail" for r in records), "provider_calls": len(captures), "fixture": str(fixture)}))
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        stub.shutdown()
        log.close()
        if records:
            write_json(result_path, records)


def launch_native(mode: str, executable: Path | None = None) -> None:
    """Launch an owned native audit shell with a clean child environment."""
    import socket
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", 15474)) == 0:
            raise RuntimeError("Port 15474 already has a listener; refusing to reuse it")
    workspace = WORK / "workspace"
    env = clean_environment()
    env.update({"HTTPS_PROXY": "http://127.0.0.1:5194", "HTTP_PROXY": "http://127.0.0.1:5194", "NO_PROXY": "127.0.0.1,localhost,::1"})
    env.update({"NOUSETSU_PROJECT_DIR": str(workspace), "NOUSETSU_PYTHON": str(ROOT / ".venv/Scripts/python.exe"), "NOVEL_REGISTRY_DIR": str(WORK / f"native-{mode}/registry"), "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": "--remote-debugging-port=5195", "WEBVIEW2_USER_DATA_FOLDER": str(WORK / f"native-{mode}/webview-profile")})
    if mode == "dev":
        if not (workspace / ".env").exists():
            (workspace / ".env").write_text("NOVEL_MODEL='mock-audit-native'\nNOVEL_FALLBACK_MODEL='mock-audit-native'\nNOVEL_PROJECTS_DIR='" + (WORK / "native-dev/projects").as_posix() + "'\n", encoding="utf-8")
        command = ["cargo", "tauri", "dev", "--no-watch", "--no-dev-server", "--config", str(WORK / "tauri-audit.json")]
    else:
        native_exe = executable or workspace / "src-tauri/target/release/nousetsu-desktop.exe"
        assert native_exe.resolve().is_relative_to(WORK.resolve()) and native_exe.name == "nousetsu-desktop.exe"
        command = [str(native_exe.resolve())]
    # Explicit temporary repositories also avoid startup falling back to host registry.
    for key in list(os.environ):
        if key.startswith(("NOVEL_", "NOUSETSU_")) or key in {"DEFAULT_MODEL", "SOURCE_LANG", "TARGET_LANG", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "CUSTOM_API_KEY", "CUSTOM_API_BASE_URL"}:
            os.environ.pop(key)
    os.environ.update(env)
    os.environ["NOUSETSU_ENV_FILE"] = str(WORK / "native-empty.env")
    from nousetsu.storage.repository import NovelRepository, ProjectRegistry
    for name in ("Native A", "Native B"):
        repo = NovelRepository(WORK / f"native-{mode}/projects" / name)
        if not repo.config_file_path().is_file():
            repo.initialize_project(title=name, source_lang="Japanese", target_lang="English", model_name="mock-audit-native")
            (repo.root_dir / "raw_chapters/0001.txt").write_text("第一章\n旅人は歩き始めた。", encoding="utf-8")
    ProjectRegistry().set_last_active_project(WORK / f"native-{mode}/projects/Native A")
    log_path = WORK / f"native-{mode}-launcher.log"
    with log_path.open("w", encoding="utf-8") as native_log:
        process = subprocess.Popen(command, cwd=workspace, env=env, stdout=native_log, stderr=native_log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    write_json(WORK / f"native-{mode}-process.json", {"pid": process.pid, "mode": mode, "executable": str((workspace / "src-tauri/target/debug/nousetsu-desktop.exe").resolve()) if mode == "dev" else command[0], "workspace": str(workspace), "registry": env["NOVEL_REGISTRY_DIR"], "log": str(log_path)})
    print(json.dumps({"pid": process.pid, "mode": mode, "log": str(log_path)}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "source", "frozen", "stub", "native-dev", "native-release"))
    parser.add_argument("--binary", type=Path, default=WORK / "workspace/src-tauri/binaries/nousetsu-backend/nousetsu-backend.exe")
    parser.add_argument("--port", type=int, default=5191)
    parser.add_argument("--native-exe", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action in {"source", "frozen"}:
        frozen_audit(Path(sys.executable) if args.action == "source" else args.binary.resolve(), args.port, source=args.action == "source")
    elif args.action.startswith("native-"):
        launch_native(args.action.removeprefix("native-"), args.native_exe)
    else:
        ThreadingHTTPServer(("127.0.0.1", args.port), ProviderStub).serve_forever()


if __name__ == "__main__":
    main()
