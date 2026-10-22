"""First-install configuration, shared by browser, desktop and terminal."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from nousetsu.models.config import GENERATION_ROLES, ProjectConfig
from nousetsu.storage.repository import atomic_write_file, get_projects_root_dir, ProjectRegistry
from nousetsu.utils.env import (
    ENV_CONFIG_KEYS, ENV_SECRET_KEYS, EnvironmentValidationError,
    _normalize_env_value, get_env_settings, resolve_env, resolve_env_file,
    resolve_env_with_sources, save_env_settings,
)
from nousetsu.utils.providers import PROVIDER_KEYS, model_ready, provider_for_model, provider_key, usable_key
from nousetsu.utils.runtime_paths import documents_dir

ROUTE_KEYS = ["DEFAULT_MODEL", "NOVEL_MODEL", "NOVEL_FALLBACK_MODEL", *[f"NOVEL_{role.upper()}_MODEL" for role in GENERATION_ROLES], "NOVEL_RAG_RERANKER_MODEL", "NOVEL_PROCEDURAL_REFINER_MODEL"]


class SetupCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    locale: Literal["en", "th"] = "en"
    provider: Literal["gemini", "openai", "openrouter", "custom"] = "gemini"
    model: str = ""
    skip_ai: bool = False
    route_all: bool = False
    values: dict[str, str] = Field(default_factory=dict)
    api_keys: dict[str, str] = Field(default_factory=dict, repr=False)
    clear_api_keys: list[str] = Field(default_factory=list)


class SetupCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["local", "catalog", "connection", "folder"] = "local"
    candidate: SetupCandidate


def setup_record_path() -> Path:
    return resolve_env_file().with_name("setup.json")


def read_setup_record() -> dict:
    try:
        result = json.loads(setup_record_path().read_text(encoding="utf-8"))
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError):
        return {}


def connection_fingerprint(env) -> str:
    connection_keys = [key for key in ENV_CONFIG_KEYS if key in ROUTE_KEYS or key.endswith(("_TEMPERATURE", "_THINKING_LEVEL", "_THINKING_BUDGET", "_USE_INTERACTIONS")) or key == "CUSTOM_API_BASE_URL"]
    relevant = {key: env.get(key, "") for key in (*connection_keys, *ENV_SECRET_KEYS)}
    return hashlib.sha256(json.dumps(relevant, sort_keys=True).encode()).hexdigest()


def translation_routes(config: ProjectConfig, env, primary=None, fallback=None) -> list[str]:
    resolved_primary = primary or config.get_model_name(env)
    if resolved_primary.startswith(("mock", "test")):
        return [resolved_primary]
    return [config.get_agent_model(role, env) for role in GENERATION_ROLES[:5]] + [fallback or config.get_fallback_model(env)]


def missing_translation_routes(config, env, primary=None, fallback=None) -> list[str]:
    return [route for route in translation_routes(config, env, primary, fallback) if not model_ready(route, env)]


def get_setup() -> dict:
    snapshot = get_env_settings()
    env, origins = resolve_env_with_sources()
    record = read_setup_record()
    providers = {provider: bool(provider_key(provider, env)) for provider in PROVIDER_KEYS}
    primary = env.get("NOVEL_MODEL") or env.get("DEFAULT_MODEL", "gemini-3.1-flash-lite")
    provider = provider_for_model(primary, env)
    registered = any(Path(path).is_dir() and (Path(path) / ".novel").is_dir() for path in ProjectRegistry().list_project_paths())
    existing = any(providers.values()) or registered or record.get("completed") is True
    values = dict(snapshot["values"])
    values["SOURCE_LANG"] = env.get("SOURCE_LANG") or "auto"
    values["TARGET_LANG"] = env.get("TARGET_LANG") or "English"
    configured_path = env.get("NOVEL_PROJECTS_DIR", "")
    explicit_path = configured_path and configured_path.strip() not in {"project", "projects", "./project", ".\\project"}
    values["NOVEL_PROJECTS_DIR"] = str(get_projects_root_dir()) if existing or explicit_path or record else str(documents_dir() / "NouSetsu")
    missing = missing_translation_routes(ProjectConfig(), env)
    readiness = "needs_attention" if snapshot["validation_errors"] or (any(providers.values()) and missing) or record.get("failed_fingerprint") == connection_fingerprint(env) else "not_connected" if missing else "tested" if record.get("verified_fingerprint") == connection_fingerprint(env) else "configured"
    result = {
        "completed": record.get("completed") is True, "existing": existing,
        "locale": record.get("locale") if record.get("locale") in {"en", "th"} else "en", "readiness": readiness,
        "provider": provider, "model": primary.split(":", 1)[-1],
        "credential_sources": {name: origins.get("GOOGLE_API_KEY" if name == "gemini" and not usable_key(env.get("GEMINI_API_KEY")) else key, "missing") for name, key in PROVIDER_KEYS.items()},
        "providers": providers, "semantic_retrieval": providers["gemini"],
        "values": values, "environment": snapshot,
        "installation": "desktop" if os.environ.get("NOUSETSU_APP_DATA_DIR") else "python",
        "fields": list(ENV_CONFIG_KEYS), "revision": snapshot["revision"],
    }
    from nousetsu.utils.env import redact_settings
    return redact_settings(result, env)


def candidate_environment(candidate: SetupCandidate):
    if set(candidate.values) - set(ENV_CONFIG_KEYS) or set(candidate.api_keys) - set(ENV_SECRET_KEYS) or set(candidate.clear_api_keys) - set(ENV_SECRET_KEYS):
        raise EnvironmentValidationError("settings", "Unsupported setting")
    values = dict(candidate.values)
    if candidate.model.strip() and not candidate.skip_ai:
        model_id = candidate.model.strip()
        # UI accepts provider-native IDs, never a second conflicting route prefix.
        if any(model_id.startswith(p + ":") for p in PROVIDER_KEYS):
            raise EnvironmentValidationError("model", "Enter the model ID without a provider prefix")
        route = model_id if candidate.provider == "gemini" else candidate.provider + ":" + model_id
        if candidate.route_all:
            values = {**dict.fromkeys(ROUTE_KEYS, route), **{key: value for key, value in values.items() if key not in ROUTE_KEYS or value.strip()}}
        values["NOVEL_MODEL"] = route
    updates = {key: _normalize_env_value(key, value) or None for key, value in values.items()}
    for key, value in candidate.api_keys.items():
        if value.strip():
            if key in candidate.clear_api_keys:
                raise EnvironmentValidationError(key, "Cannot replace and remove the same key")
            updates[key] = _normalize_env_value(key, value)
    updates.update({key: None for key in candidate.clear_api_keys})
    env, origins = resolve_env_with_sources(machine_updates=updates)
    for key in ENV_CONFIG_KEYS:
        _normalize_env_value(key, env.get(key, ""))
    return values, env, origins


def validate_candidate(candidate: SetupCandidate, check_storage=True):
    values, env, origins = candidate_environment(candidate)
    if not env.get("TARGET_LANG", "").strip():
        raise EnvironmentValidationError("TARGET_LANG", "Choose the translation language")
    if not candidate.skip_ai and missing_translation_routes(ProjectConfig(), env):
        raise EnvironmentValidationError("api_key", "Connect AI or choose Set up AI later")
    if not candidate.skip_ai:
        auxiliary_routes = {"NOVEL_RAG_RERANKER_MODEL": ProjectConfig().get_rag_reranker_model(env)}
        if env.get("NOVEL_ENABLE_PROCEDURAL_GRAPH_LEARNING", "true").lower() not in {"false", "0", "no", "off"}:
            auxiliary_routes["NOVEL_PROCEDURAL_REFINER_MODEL"] = ProjectConfig().get_procedural_refiner_model(env)
        for field, route in auxiliary_routes.items():
            if not model_ready(route, env):
                raise EnvironmentValidationError(field, "Add this service's key, or use the connected model for all translation tasks")
    if check_storage:
        raw = env.get("NOVEL_PROJECTS_DIR", "").strip()
        if not raw:
            raise EnvironmentValidationError("NOVEL_PROJECTS_DIR", "Choose a folder for your novels")
        # Resolve relative folders exactly as the runtime does.
        from nousetsu.storage.repository import get_codebase_root
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = get_codebase_root() / path
        try:
            path.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryFile(dir=path):
                pass
        except OSError:
            raise EnvironmentValidationError("NOVEL_PROJECTS_DIR", "This folder is not writable. Choose another folder") from None
    return values, env, origins


def choose_folder() -> str | None:
    # Tk runs in a separate process so FastAPI worker threads never own its event loop.
    script = "import tkinter as t; from tkinter import filedialog; r=t.Tk(); r.withdraw(); print(filedialog.askdirectory()); r.destroy()"
    try:
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60, creationflags=0x08000000 if sys.platform == "win32" else 0)
        if result.returncode == 0:
            return result.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        pass
    raise EnvironmentValidationError("NOVEL_PROJECTS_DIR", "Folder picker unavailable. Enter or paste a folder path")


class ConnectionSample(BaseModel):
    translation: str = Field(description="English translation of the supplied Japanese sample")


def test_connection(candidate: SetupCandidate, env):
    from langchain_core.messages import HumanMessage
    from nousetsu.agents.llm import get_llm, MockNovelLLM
    role = "drafter"
    config = ProjectConfig()
    settings = config.get_agent_generation_settings(role, env)
    model = get_llm(config.get_agent_model(role, env), environ=env, **{
        "temperature": settings["temperature"], "thinking_level": settings["thinking_level"],
        "thinking_budget": settings["thinking_budget"], "use_interactions": settings["use_interactions_api"],
    })
    if isinstance(model, MockNovelLLM):
        raise EnvironmentValidationError("model", "Choose a real AI model to test the connection")
    if hasattr(model, "max_retries"):
        model.max_retries = 0
    if hasattr(model, "timeout"):
        model.timeout = 20
    if hasattr(model, "request_timeout"):
        model.request_timeout = 20
    # No fallback/retry wrapper or trace collection: this is one explicit sample request.
    output = model.with_structured_output(ConnectionSample, include_raw=True).invoke([
        HumanMessage(content='Translate into English: おはよう。 Return only JSON matching {"translation": "English translation"}.')
    ])
    parsed = output.get("parsed") if isinstance(output, dict) else output
    if not isinstance(parsed, ConnectionSample) or not parsed.translation.strip():
        raise EnvironmentValidationError("model", "This model did not return the required structured response. Choose another model")


def connection_error(error: Exception) -> tuple[str, str]:
    # Inspect upstream failures privately; never return provider bodies or credentials.
    message = str(error).lower()
    if any(code in message for code in ("401", "403", "unauthorized", "api_key_invalid", "api key not valid")):
        return "key_rejected", "This key was rejected. Check it or create another key"
    if any(code in message for code in ("429", "quota", "resource_exhausted")):
        return "quota", "Your service limit was reached. Check your account or try again later"
    if any(code in message for code in ("404", "not found")):
        return "model_unavailable", "This model is unavailable. Choose another model"
    return "connection_failed", "Could not connect. Check your connection, service address and model, then try again"


def complete_setup(candidate: SetupCandidate, revision: str, verified_fingerprint: str = "", failed_fingerprint: str = "") -> dict:
    values, env, origins = validate_candidate(candidate)
    saved = save_env_settings(values, candidate.api_keys, candidate.clear_api_keys, expected_revision=revision)
    record = {"completed": True, "version": 1, "locale": candidate.locale}
    if not candidate.skip_ai and verified_fingerprint == connection_fingerprint(env):
        record["verified_fingerprint"] = connection_fingerprint(resolve_env())
    elif not candidate.skip_ai and failed_fingerprint == connection_fingerprint(env):
        record["failed_fingerprint"] = connection_fingerprint(resolve_env())
    try:
        atomic_write_file(setup_record_path(), json.dumps(record, ensure_ascii=False), strict=True, permissions=0o600)
    except OSError:
        return {"success": False, "settings_saved": True, "revision": saved["revision"], "code": "completion_write_failed"}
    return {"success": True, "settings_saved": True, "revision": saved["revision"]}


def run_terminal_setup(console):
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    from rich.markup import escape
    snapshot = get_setup()
    locale = Prompt.ask("Language / ภาษา", choices=["en", "th"], default=snapshot["locale"])
    def t(en, th):
        return th if locale == "th" else en
    console.print(t("Let’s get NouSetsu ready. Settings and keys are stored on this computer.", "ตั้งค่า NouSetsu การตั้งค่าและคีย์จะเก็บไว้ในเครื่องนี้"))
    skip = not Confirm.ask(t("Connect AI now?", "เชื่อมต่อ AI ตอนนี้หรือไม่?"), default=any(snapshot["providers"].values()))
    candidate = SetupCandidate(locale=locale, skip_ai=skip, provider=snapshot["provider"], model=snapshot["model"] if snapshot["existing"] else "", route_all=not snapshot["existing"])
    verified = ""
    failed = ""
    if not skip:
        candidate.provider = Prompt.ask(t("AI service", "บริการ AI"), choices=list(PROVIDER_KEYS), default=candidate.provider)
        candidate.route_all = candidate.provider != snapshot["provider"] or not snapshot["existing"]
        if candidate.provider != snapshot["provider"]:
            candidate.model = ""
        console.print(t("Use the service's API-key page to create a connection key. Leave blank to keep an existing key.", "สร้างคีย์จากหน้าคีย์ API ของผู้ให้บริการ เว้นว่างเพื่อใช้คีย์เดิม"))
        key = Prompt.ask(t("Connection key (blank keeps saved key)", "คีย์เชื่อมต่อ (เว้นว่างเพื่อใช้คีย์เดิม)"), password=True, default="")
        if key:
            candidate.api_keys[PROVIDER_KEYS[candidate.provider]] = key
        if candidate.provider == "custom":
            candidate.values["CUSTOM_API_BASE_URL"] = Prompt.ask(t("Service address", "ที่อยู่บริการ"), default=snapshot["values"].get("CUSTOM_API_BASE_URL", ""))
        from nousetsu.utils.model_catalog import fetch_model_catalog
        _, env, _ = candidate_environment(candidate)
        try:
            models = fetch_model_catalog(candidate.provider, provider_key(candidate.provider, env), env.get("CUSTOM_API_BASE_URL"))
            console.print(escape("\n".join(models)))
        except Exception:
            console.print(t("Model discovery unavailable; enter a model ID.", "โหลดรายชื่อโมเดลไม่ได้ กรุณาป้อนรหัสโมเดล"))
        candidate.model = Prompt.ask(t("AI model ID", "รหัสโมเดล AI"), default=candidate.model)
    candidate.values["SOURCE_LANG"] = Prompt.ask(t("Original language (auto detects it)", "ภาษาต้นฉบับ (auto ตรวจจับอัตโนมัติ)"), default=snapshot["values"]["SOURCE_LANG"])
    candidate.values["TARGET_LANG"] = Prompt.ask(t("Translate into", "แปลเป็นภาษา"), default=snapshot["values"]["TARGET_LANG"] if snapshot["existing"] else "Thai" if locale == "th" else "English")
    candidate.values["NOVEL_PROJECTS_DIR"] = Prompt.ask(t("Save your novels in", "โฟลเดอร์เก็บนิยาย"), default=snapshot["values"]["NOVEL_PROJECTS_DIR"])
    if not snapshot["existing"]:
        candidate.values.update(NOVEL_MAX_REVIEW_LOOPS="3", NOVEL_QUALITY_THRESHOLD="8.5")
    if Confirm.ask(t("Edit advanced installation defaults?", "แก้ไขการตั้งค่าขั้นสูงหรือไม่?"), default=False):
        console.print(t("Blank inherits the application default. Project-only controls are available after creating a novel.", "เว้นว่างเพื่อใช้ค่าเริ่มต้นของแอป การตั้งค่าเฉพาะนิยายใช้ได้หลังสร้างโครงการ"))
        for setting in ENV_CONFIG_KEYS:
            if setting in {"SOURCE_LANG", "TARGET_LANG", "NOVEL_PROJECTS_DIR", "NOVEL_MODEL"}:
                continue
            candidate.values[setting] = Prompt.ask(setting, default=candidate.values.get(setting, "" if candidate.route_all and setting in ROUTE_KEYS else snapshot["values"].get(setting, "")))
    if not skip and Confirm.ask(t("Test connection? Sends a small sample; your service may charge.", "ทดสอบการเชื่อมต่อหรือไม่? ส่งตัวอย่างสั้น ๆ บริการอาจคิดค่าบริการ"), default=False):
        env = None
        try:
            _, env, _ = validate_candidate(candidate, False)
            test_connection(candidate, env)
            verified = connection_fingerprint(env)
            console.print(t("Connection tested successfully", "ทดสอบการเชื่อมต่อสำเร็จ"))
        except Exception as error:
            if env is not None:
                failed = connection_fingerprint(env)
            console.print(t(connection_error(error)[1], "ทดสอบไม่สำเร็จ ตรวจสอบคีย์ โมเดล และการเชื่อมต่อ หรือลองอีกครั้ง"))
    table = Table(title=t("Review setup", "ตรวจสอบการตั้งค่า"))
    table.add_column(t("Setting", "การตั้งค่า")); table.add_column(t("Value", "ค่า"))
    from nousetsu.utils.env import redact_settings
    for label, value in [(t("AI service", "บริการ AI"), t("Connect later", "เชื่อมต่อภายหลัง") if skip else f"{candidate.provider} / {candidate.model}"), *candidate.values.items()]:
        table.add_row(escape(label), escape(redact_settings(value, candidate.api_keys)))
    console.print(table)
    if Confirm.ask(t("Finish setup?", "บันทึกการตั้งค่าหรือไม่?"), default=True):
        try:
            result = complete_setup(candidate, snapshot["revision"], verified, failed)
            if not result["success"]:
                console.print(t("Settings saved, but completion could not be recorded. Run setup again to retry.", "บันทึกค่าแล้ว แต่บันทึกสถานะไม่สำเร็จ กรุณาเรียกตั้งค่าอีกครั้ง"))
                return
        except (ValueError, OSError):
            console.print(t("Could not finish. Check settings and folder permissions, then run setup again.", "บันทึกไม่สำเร็จ ตรวจสอบการตั้งค่าและสิทธิ์ของโฟลเดอร์ แล้วเรียกตั้งค่าอีกครั้ง"))
            return
        console.print(t("Setup complete. Next: nousetsu init or nousetsu web", "ตั้งค่าเสร็จแล้ว ขั้นต่อไป: nousetsu init หรือ nousetsu web"))
