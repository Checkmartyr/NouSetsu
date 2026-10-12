"""Hermetic real settings backend for the browser audit; never uses host .env.

Run with uv run python scripts/audit/settings_fixture_server.py --port 5186
--mode dev. Audit-only endpoints expose sanitized disk evidence and reset fixtures;
all product endpoints and serializers execute unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import socket
import tempfile
import sys


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--mode", choices=("dev", "built"), required=True)
    args = parser.parse_args()
    evidence = Path("audit-results/settings").resolve()
    root = Path(tempfile.mkdtemp(prefix=f"nousetsu-settings-{args.mode}-"))
    projects = root / "projects"
    env_file = root / "audit.env"
    for key in list(os.environ):
        if key.startswith(("NOVEL_", "NOUSETSU_")) or key in {
            "DEFAULT_MODEL", "SOURCE_LANG", "TARGET_LANG", "GEMINI_API_KEY",
            "GOOGLE_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY",
            "CUSTOM_API_KEY", "CUSTOM_API_BASE_URL",
        }:
            # Save the explicit audit dist before scrubbing inherited settings.
            if key == "NOUSETSU_SETTINGS_AUDIT_DIST":
                continue
            os.environ.pop(key)
    os.environ.update({
        "NOUSETSU_ENV_FILE": str(env_file),
        "NOVEL_REGISTRY_DIR": str(root / "registry"),
        "NOVEL_PROJECTS_DIR": str(projects),
        "NOUSETSU_LOGS_DIR": str(root / "logs"),
    })
    env_file.write_text(
        f"NOVEL_PROJECTS_DIR='{projects.as_posix()}'\n"
        "NOVEL_MODEL='mock-audit-shared'\nNOVEL_FALLBACK_MODEL='mock-audit-fallback'\n"
        "NOVEL_USE_INTERACTIONS='true'\nNOVEL_MAX_TPM='32000'\n"
        "NOVEL_MAX_RPM='60'\nNOVEL_MAX_REVIEW_LOOPS='3'\n"
        "NOVEL_QUALITY_THRESHOLD='8.5'\n", encoding="utf-8",
    )
    # Fail closed if any audited action unexpectedly tries a commercial provider.
    connect = socket.socket.connect

    def local_connect(self, address):
        if isinstance(address, tuple) and address[0] not in ("127.0.0.1", "localhost", "::1"):
            raise OSError("Settings audit blocks outbound network connections")
        return connect(self, address)

    socket.socket.connect = local_connect
    import dotenv
    logging.getLogger("dotenv.main").setLevel(logging.ERROR)
    import uvicorn
    import yaml
    from nousetsu.storage.repository import NovelRepository, ProjectRegistry
    from nousetsu.utils.env import ENV_CONFIG_KEYS, ENV_SECRET_KEYS, load_env, save_env_settings
    from nousetsu.cli import web_server

    for name in ("Audit A", "Audit B"):
        repo = NovelRepository(projects / name)
        repo.initialize_project(title=name, source_lang="Japanese", target_lang="English")
        (repo.root_dir / "raw_chapters" / "0001.txt").write_text(
            "第一章\n太郎は家に帰った。\n", encoding="utf-8",
        )
    ProjectRegistry().set_last_active_project(projects / "Audit A")
    saved_files = {
        path: path.read_bytes() for path in root.rglob("*")
        if path.is_file() and path.suffix in (".yaml", ".json", ".env")
    }
    dist = Path(os.environ.get("NOUSETSU_SETTINGS_AUDIT_DIST", "web/dist")).resolve()
    # resolve_project_dir(None) falls back to CWD when the registry is empty.
    # Keep that fallback inside the fixture, including the no-project scenario.
    os.chdir(root)
    app = web_server.create_app(dist_dir=dist if args.mode == "built" else root / "no-dist")
    original_count = len(app.router.routes)

    def snapshot():
        parsed = dotenv.dotenv_values(env_file)
        return {
            "mode": args.mode, "pid": os.getpid(), "root": str(root),
            "projects": {key: str(projects / f"Audit {key}") for key in ("A", "B")},
            "env_file": str(env_file),
            "env_values": {key: parsed.get(key) for key in ENV_CONFIG_KEYS},
            "secret_hashes": {
                key: hashlib.sha256((parsed.get(key) or "").encode()).hexdigest()
                for key in ENV_SECRET_KEYS
            },
            "config": {key: yaml.safe_load((projects / f"Audit {key}" / ".novel/config.yaml").read_text(encoding="utf-8")) for key in ("A", "B")},
            "bible": {key: yaml.safe_load((projects / f"Audit {key}" / ".novel/bible/bible.yaml").read_text(encoding="utf-8")) for key in ("A", "B")},
            "resolved": {key: {
                "filter_extractor_entities": NovelRepository(projects / f"Audit {key}").load_config().get_filter_extractor_entities(),
                "generation": {role: NovelRepository(projects / f"Audit {key}").load_config().get_agent_generation_settings(role) for role in ("extractor", "drafter", "critic", "polisher", "chronicler", "scraper")},
            } for key in ("A", "B")},
        }

    @app.get("/api/audit/fixture")
    async def fixture():
        return snapshot()

    @app.post("/api/audit/reset")
    async def reset():
        for path, content in saved_files.items():
            assert path.resolve().is_relative_to(root.resolve())
            path.write_bytes(content)
        for key in (*ENV_CONFIG_KEYS, *ENV_SECRET_KEYS):
            os.environ.pop(key, None)
        load_env()
        web_server._PROJECT_META_CACHE.clear()
        web_server._invalidate_chapter_caches()
        return snapshot()

    @app.get("/api/audit/provider/v1/models")
    async def catalog():
        return {"object": "list", "data": [{"id": "audit-local-model", "object": "model"}]}

    @app.post("/api/audit/no-project")
    async def no_project():
        empty = root / "empty-projects"
        empty.mkdir(exist_ok=True)
        save_env_settings({"NOVEL_PROJECTS_DIR": str(empty)}, {}, [])
        ProjectRegistry()._save_raw({"last_active": None, "projects": []})
        web_server._invalidate_chapter_caches()
        return {"projects_dir": str(empty)}

    # Ensure fixture routes precede the product SPA catch-all without replacing it.
    new_routes = app.router.routes[original_count:]
    app.router.routes = new_routes + app.router.routes[:original_count]
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / f"browser-{args.mode}-fixture.json").write_text(
        json.dumps({**snapshot(), "dist": str(dist),
                    "frontend_index_sha256": hashlib.sha256((dist / "index.html").read_bytes()).hexdigest() if (dist / "index.html").exists() else None,
                    "backend_source_sha256": hashlib.sha256(Path(web_server.__file__).read_bytes()).hexdigest()}, indent=2), encoding="utf-8",
    )
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
