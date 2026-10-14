"""Build a settings inventory from source ASTs without importing the application.

Run: uv run python scripts/audit/settings_inventory.py
All mode results start pending. The audit coordinator supplies measured results.
"""
from __future__ import annotations

import ast
import csv
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "audit-results/settings"
CONFIG = "src/nousetsu/models/config.py"
ENV = "src/nousetsu/utils/env.py"
UI = "web/src/components/SettingsView.tsx"
API = "src/nousetsu/cli/web_server.py"
MODES = ("source_api", "frozen_api", "web_dev", "web_built", "native_dev", "native_release")


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def ref(path: str, needle: str) -> str:
    for line, text in enumerate(source(path).splitlines(), 1):
        if needle in text:
            return f"{path}:{line}"
    return ""


def constants(tree: ast.AST) -> dict:
    result = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                result[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    return result


def fields(tree: ast.AST, name: str) -> list[ast.AnnAssign]:
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name)
    return [node for node in cls.body if isinstance(node, ast.AnnAssign)]


def field_default(node: ast.AnnAssign) -> str:
    value = node.value
    if isinstance(value, ast.Call):
        for keyword in value.keywords:
            if keyword.arg == "default":
                return ast.unparse(keyword.value)
            if keyword.arg == "default_factory":
                return "factory: " + ast.unparse(keyword.value)
        if value.args:
            return "required" if isinstance(value.args[0], ast.Constant) and value.args[0].value is Ellipsis else ast.unparse(value.args[0])
    return ast.unparse(value) if value else "required"


def field_constraints(node: ast.AnnAssign) -> str:
    if isinstance(node.value, ast.Call):
        return "; ".join(f"{kw.arg}={ast.unparse(kw.value)}" for kw in node.value.keywords if kw.arg in {"ge", "le", "gt", "lt"})
    return ""


PY_SOURCES = {p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8") for p in (ROOT / "src/nousetsu").rglob("*.py")}


def consumers(key: str) -> str:
    matches = []
    for path, text in PY_SOURCES.items():
        if path.startswith("src/nousetsu/models/") or path in {API, ENV}:
            continue
        for line, value in enumerate(text.splitlines(), 1):
            if re.search(r"\b" + re.escape(key) + r"\b", value) and not value.lstrip().startswith("#"):
                matches.append(f"{path}:{line}")
                break
    return "; ".join(matches[:5]) or "No runtime reference found outside schema/settings layer"


def project_inheritance(key: str) -> str:
    if key in {"max_tpm", "max_rpm", "max_review_loops", "quality_threshold"}:
        return "Constructor truthy override > process environment > concrete project value (observed source; differs from documented cascade)"
    if key.endswith("_model") and key.split("_model")[0] in roles:
        if key == "scraper_model":
            return "Project role > role environment > project primary > machine primary > role built-in; blank/null restores inheritance"
        return "Constructor role > project role > project primary > role environment > machine primary > role built-in; blank/null restores inheritance"
    if key in {"model_name", "fallback_model", "rag_embedding_model", "rag_reranker_model"}:
        return "Constructor override where supported > project > environment > built-in; empty/null model restores inheritance"
    if key.startswith("procedural_") or key == "enable_procedural_graph_learning":
        return "Constructor override > optional project > environment > built-in; schema supported, settings PUT unsupported"
    if key == "filter_extractor_entities":
        return "Constructor explicit Boolean > optional project > environment > True; API null restores inheritance"
    if key == "enable_post_polish_reconciliation":
        return "Constructor explicit Boolean > concrete project True default; environment branch exists but default masks it; API null ignored"
    if key == "use_interactions_api":
        return "Legacy project override below per-role project and above environment; null PUT ignored; clear-all does not clear legacy value"
    if key in {"title", "genre", "source_language", "target_language"}:
        return "Project explicit value; nonempty metadata synchronized to existing Bible; language environment only consulted by CLI creation"
    if key == "cross_folder_summaries":
        return "Concrete project value persists; workflow reads separate Bible value, settings synchronization omits this field"
    if key == "filter_scene_characters":
        return "Concrete project value persists; no runtime consumer found"
    if key in {"created_at", "project_id"}:
        return "Project metadata; created_at read-only in settings PUT; project_id explicitly editable"
    if key == "generation_settings":
        return "Project role controls > legacy interactions override for interactions > role env > shared env > role defaults; PUT replaces map"
    return "Constructor override where supported > concrete project value; no environment alias; missing/null PUT generally preserves"


def timing(key: str) -> str:
    if key in {"created_at", "project_id"}:
        return "Immediate persistence/read; metadata only"
    if key in {"title", "genre", "source_language", "target_language"}:
        return "Next settings GET; Bible loaded at each chapter start; running chapter keeps its loaded state"
    if key in {"raw_dir", "output_dir"}:
        return "Next scanner/path resolution; chapter caches invalidated after save"
    if key == "filter_scene_characters":
        return "Persistence only; runtime effect absent in current source"
    if key == "cross_folder_summaries":
        return "Persistence only; runtime reads Bible field instead"
    if key == "scraper_model":
        return "Next scraper subprocess launch"
    return "Next BatchRunner/workflow construction; active runner retains resolved values"


config_tree = ast.parse(source(CONFIG))
env_tree = ast.parse(source(ENV))
cfg_constants = constants(config_tree)
env_constants = constants(env_tree)
roles = cfg_constants["GENERATION_ROLES"]
ui_text = source(UI)
api_text = source(API)
rows = []


def add(**values: str) -> None:
    rows.append({**values, **{mode: "pending" for mode in MODES}, "evidence": "Inventory source references only; execution evidence not yet supplied"})


labels = {
    "title": "Novel Title", "genre": "Genre", "source_language": "Source Language", "target_language": "Target Language",
    "raw_dir": "Raw Chapters Directory", "output_dir": "Translated Chapters Directory", "model_name": "Primary Model", "fallback_model": "Fallback Model",
    "project_id": "Project Identifier", "created_at": "Created (read-only)", "max_review_loops": "Max Review Loops", "quality_threshold": "Quality Score Threshold",
    "chunk_threshold_lines": "Chunk Threshold (lines)", "target_chunk_lines": "Chunk Size (lines)", "chunk_overlap_lines": "Chunk Overlap (lines)",
    "enable_chunking": "Chunking Enabled", "auto_update_bible": "Auto-Update Novel Bible", "cross_folder_summaries": "Cross-Folder Multi-Volume Memory",
    "filter_scene_characters": "Scene Character Filtering", "filter_extractor_entities": "Extractor Known Entity Filtering",
    "enable_post_polish_reconciliation": "Post-Polish Term Reconciliation", "enable_rag": "Hybrid RAG Enabled", "rag_top_k": "Lore Retrieval Top-K",
    "rag_embedding_model": "Dense Embedding Model", "enable_rag_reranker": "Enable Cross-Encoder Reranker", "rag_reranker_model": "Cross-Encoder Reranker Model",
    "safety_recursive_subdivision": "Subdivision Enabled", "safety_subdivision_min_lines": "Subdivision Min Lines (lines)", "safety_subdivision_max_depth": "Subdivision Max Recursion Depth",
    "max_tpm": "Max Tokens Per Minute (TPM)", "max_rpm": "Max Requests Per Minute (RPM)", "enable_patch_polishing": "Enable Diff/Patch Polishing Engine",
}
for field in fields(config_tree, "ProjectConfig"):
    key = field.target.id
    alias = {"output_dir": "translated_dir", "target_chunk_lines": "chunk_size_lines"}.get(key, key)
    nested_only = key.startswith("procedural_") or key == "enable_procedural_graph_learning"
    readonly = key == "created_at"
    exposed = bool(re.search(r"settings[.?]" + re.escape(alias) + r"\b", ui_text)) or key.endswith("_model") and key[:-6] in roles or key == "generation_settings"
    writable = not nested_only and not readonly
    ui_reference = ref(UI, f"settings.{alias}") if exposed else ""
    if key.endswith("_model") and key[:-6] in roles:
        ui_reference = ref(UI, f"modelKey: '{key}'")
    effective_default = {
        "model_name": "gemini-3.1-flash-lite", "fallback_model": "gemini-3.5-flash-lite",
        "filter_extractor_entities": "True", "rag_embedding_model": "text-multilingual-embedding-002",
        "rag_reranker_model": "gemini-3.5-flash-lite", "enable_procedural_graph_learning": "True",
        "procedural_learning_cadence": "both", "procedural_learning_interval": "15",
        "procedural_learning_min_failures": "2", "procedural_refiner_model": "gemini-3.5-flash-lite",
        "use_interactions_api": "True via per-role resolver", "generation_settings": "Per-role defaults (see 24 expanded rows)",
    }.get(key, field_default(field))
    if key.endswith("_model") and key[:-6] in roles:
        effective_default = cfg_constants["DEFAULT_AGENT_MODELS"][key[:-6]]
    note = ""
    if nested_only:
        note = "Exposed in GET config object, ignored by settings PUT; not editable in SettingsView; environment key not allowlisted"
    elif key == "use_interactions_api":
        note = "Legacy schema/API field; per-role editor replaces direct global project UI; PUT bool(value) coerces strings"
    elif key == "target_chunk_lines":
        note = "API supports both names; chunk_size_lines wins when both supplied; frontend blank save 70 vs default 400"
    elif key == "output_dir":
        note = "API supports both names; translated_dir wins when both supplied"
    elif key == "chunk_threshold_lines":
        note = "Frontend blank save 85 vs default/display 800; onBlur resets blank to 800"
    add(setting_id=f"project.{key}", scope="project", key=key, api_name=alias,
        api_endpoint="GET/PUT /api/settings" if writable else "GET /api/settings (nested config only)" if nested_only else "GET /api/settings",
        type=ast.unparse(field.annotation), schema_default=field_default(field), effective_default=effective_default,
        constraints=field_constraints(field), ui_name=labels.get(key, key.replace("_", " ").title()),
        ui_exposure="editable" if exposed and writable else "read-only" if readonly else "schema/API legacy" if writable else "schema-only",
        storage=".novel/config.yaml" + (" + existing .novel/bible/bible.yaml" if key in {"title", "genre", "source_language", "target_language"} else ""),
        inheritance_reset=project_inheritance(key), runtime_consumer=consumers(key), application_timing=timing(key),
        schema_ref=f"{CONFIG}:{field.lineno}", ui_ref=ui_reference, api_ref=ref(API, f'cfg.{key} =') or ref(API, f'"{key}": cfg.'), notes=note)

for role in roles:
    for field in fields(config_tree, "AgentGenerationSettings"):
        key = field.target.id
        default = {"temperature": str(cfg_constants["DEFAULT_AGENT_TEMPERATURES"][role]), "thinking_level": "medium" if role == "critic" else "None", "thinking_budget": "None", "use_interactions_api": "True"}[key]
        add(setting_id=f"project.generation_settings.{role}.{key}", scope="project_generation", key=f"generation_settings.{role}.{key}",
            api_name=f"generation_settings.{role}.{key}", api_endpoint="GET/PUT /api/settings", type=ast.unparse(field.annotation),
            schema_default=field_default(field), effective_default=default, constraints=field_constraints(field),
            ui_name=f"{role.title()} {key.replace('_', ' ')}", ui_exposure="editable (provider/Interactions dependent visibility)",
            storage=".novel/config.yaml", inheritance_reset="Project non-null > legacy project interactions when applicable > role env > shared env > role default; blank editor sends null; PUT replaces supplied role map",
            runtime_consumer="src/nousetsu/scraper/llm_config.py:78" if role == "scraper" else ref("src/nousetsu/batch/runner.py", 'cfg.get_agent_generation_settings(role)'),
            application_timing="Next scraper subprocess" if role == "scraper" else "Next BatchRunner construction; settings GET resolves current env",
            schema_ref=f"{CONFIG}:{field.lineno}", ui_ref=ref(UI, f"current('{key}')"), api_ref=ref(API, "AgentGenerationSettings.model_validate(values)"),
            notes="Temperature hidden for OpenAI reasoning routes; Gemini controls hidden for non-Gemini; budget hidden while Interactions on; saved values retained")

extra_env = ("NOVEL_ENABLE_PROCEDURAL_GRAPH_LEARNING", "NOVEL_PROCEDURAL_LEARNING_CADENCE", "NOVEL_PROCEDURAL_LEARNING_INTERVAL", "NOVEL_PROCEDURAL_LEARNING_MIN_FAILURES", "NOVEL_PROCEDURAL_REFINER_MODEL")
for key in (*env_constants["ENV_CONFIG_KEYS"], *env_constants["ENV_SECRET_KEYS"], *extra_env):
    secret = key in env_constants["ENV_SECRET_KEYS"]
    editable = key not in extra_env
    role = next((r for r in roles if key.startswith(f"NOVEL_{r.upper()}_")), None)
    suffix = key.removeprefix(f"NOVEL_{role.upper()}_" if role else "NOVEL_")
    value_type = "string (secret)" if secret else "string (bool parsed at runtime)" if suffix.startswith("USE_INTERACTIONS") or key.endswith(("ENTITIES", "RECONCILIATION", "GRAPH_LEARNING")) else "string (float parsed at runtime)" if suffix in {"TEMPERATURE", "QUALITY_THRESHOLD"} else "string (int parsed at runtime)" if suffix in {"THINKING_BUDGET", "MAX_TPM", "MAX_RPM", "MAX_REVIEW_LOOPS", "LEARNING_INTERVAL", "LEARNING_MIN_FAILURES"} else "string"
    default_map = {"DEFAULT_MODEL": "legacy alias; blank", "NOVEL_MODEL": "gemini-3.1-flash-lite", "NOVEL_FALLBACK_MODEL": "gemini-3.5-flash-lite", "SOURCE_LANG": "CLI init English; CLI batch auto; web creation Japanese", "TARGET_LANG": "CLI init Thai; CLI batch English; web creation Thai", "NOVEL_MAX_TPM": "32000", "NOVEL_MAX_RPM": "60", "NOVEL_MAX_REVIEW_LOOPS": "3", "NOVEL_QUALITY_THRESHOLD": "8.5", "NOVEL_PROJECTS_DIR": "project; desktop-provided directory for template placeholders", "NOVEL_USE_INTERACTIONS": "True", "NOVEL_FILTER_EXTRACTOR_ENTITIES": "True", "NOVEL_POST_POLISH_RECONCILIATION": "True (masked by project True default)", "NOVEL_RAG_EMBEDDING_MODEL": "text-multilingual-embedding-002", "NOVEL_RAG_RERANKER_MODEL": "gemini-3.5-flash-lite", "NOVEL_ENABLE_PROCEDURAL_GRAPH_LEARNING": "True", "NOVEL_PROCEDURAL_LEARNING_CADENCE": "both", "NOVEL_PROCEDURAL_LEARNING_INTERVAL": "15", "NOVEL_PROCEDURAL_LEARNING_MIN_FAILURES": "2", "NOVEL_PROCEDURAL_REFINER_MODEL": "gemini-3.5-flash-lite"}
    default = default_map.get(key, "provider/discovery default; blank")
    if role:
        default = cfg_constants["DEFAULT_AGENT_MODELS"][role] if suffix == "MODEL" else str(cfg_constants["DEFAULT_AGENT_TEMPERATURES"][role]) if suffix == "TEMPERATURE" else "medium" if suffix == "THINKING_LEVEL" and role == "critic" else "True" if suffix == "USE_INTERACTIONS" else "None"
    runtime = consumers(key)
    if role and suffix != "MODEL" or key in {"NOVEL_TEMPERATURE", "NOVEL_THINKING_LEVEL", "NOVEL_THINKING_BUDGET", "NOVEL_USE_INTERACTIONS"}:
        runtime = ref(CONFIG, "def resolve_agent_generation_settings(") + "; " + ref("src/nousetsu/batch/runner.py", 'cfg.get_agent_generation_settings(role)')
    ui_reference = ref(UI, f"'{key}'") or ref(UI, key)
    add(setting_id=f"env.{key}", scope="env_secret" if secret else "env_unexposed" if not editable else "env", key=key,
        api_name=(f"api_keys.{key}; clear_api_keys[]" if secret else f"values.{key}"), api_endpoint="GET/PUT /api/environment" if editable else "Unsupported by /api/environment allowlist",
        type=value_type, schema_default="blank editable persisted value", effective_default=str(default), constraints="Allowlisted scalar converted to trimmed string; no semantic bounds" if editable else "Resolver only",
        ui_name=key, ui_exposure="editable secret replacement + explicit clear" if secret else "editable" if editable else "schema/runtime only",
        storage="Resolved .env (NOUSETSU_ENV_FILE > discovered repository/install/app root); process environment updated on successful save",
        inheritance_reset="Blank secret preserves; explicit clear removes file and process key; replace+clear rejected; response status only" if secret else "Blank removes file and process override; project precedence is field-specific; dotenv loads process state without clearing stale keys",
        runtime_consumer=runtime, application_timing="Next provider construction/catalog request" if secret or key == "CUSTOM_API_BASE_URL" else "CLI parser/startup" if key in {"SOURCE_LANG", "TARGET_LANG"} else "Next scraper discovery" if key in {"NOVEL_SCRAPER_PATH", "NOVEL_SCRAPER_PYTHON"} else "Next project listing/path resolution" if key == "NOVEL_PROJECTS_DIR" else "Next runner construction; settings GET resolves environment",
        schema_ref=ref(ENV, f'"{key}"') if editable else ref(CONFIG, f'"{key}"'), ui_ref=ui_reference if editable else "", api_ref=ref(ENV, "def save_env_settings("),
        notes="Actual persisted values and effective defaults differ; environment API returns file values, not full process-effective values. " + ("Unallowlisted procedural key; can only configure externally." if not editable else "Secret status derives from file, whereas provider may use process keys." if secret else ""))

actions = (
    ("load_env_presets", "Load .env model defaults", "handleLoadEnvPresets", "Copies snapshot into form as explicit project routes; save required"),
    ("apply_model_preset", "Apply model preset", "handleApplyPreset", "Copies primary/fallback/five roles; scraper and generation controls retained; save required"),
    ("clear_model_overrides", "Clear all model overrides", "handleClearOverrides", "Clears eight routes and generation map; legacy interactions field retained; save required"),
    ("provider_catalog", "Load/refresh provider model catalog", "onLoadCatalog", "GET /api/model-catalog; live provider calls must be replaced with local provider fixture in audit"),
    ("check_updates", "Check for Updates", "handleCheckUpdates", "Browser release API vs native Tauri updater; installation excluded"),
    ("logs_refresh", "Refresh Logs & Diagnostics", "loadLogsInfo", "GET /api/logs/info; native folder opener vs backend opener"),
    ("logs_open", "Open Logs Folder", "open_logs_directory", "Native invoke/open_logs_directory or POST /api/logs/open-folder"),
    ("category_search", "Search settings categories", "categorySearch", "Session state, filters navigation only"),
)
for key, label, needle, note in actions:
    add(setting_id=f"action.{key}", scope="settings_action", key=key, api_name="UI action", api_endpoint="See notes", type="action/session state", schema_default="n/a", effective_default="n/a", constraints="n/a",
        ui_name=label, ui_exposure="action", storage="None except explicit subsequent save; category search uses session state", inheritance_reset="n/a", runtime_consumer="See notes",
        application_timing="User-triggered", schema_ref="", ui_ref=ref(UI, needle), api_ref="", notes=note)

for field in fields(ast.parse(api_text), "CreateProjectRequest"):
    key = field.target.id
    add(setting_id=f"creation.{key}", scope="project_creation", key=key, api_name=key, api_endpoint="POST /api/projects/create",
        type=ast.unparse(field.annotation), schema_default=field_default(field), effective_default=field_default(field), constraints=field_constraints(field),
        ui_name=key.replace("_", " ").title(), ui_exposure="Project creation modal (outside SettingsView)",
        storage="New project .novel/config.yaml and .novel/bible/bible.yaml; folder_name chooses project directory",
        inheritance_reset="Creation request defaults are independent of editable SOURCE_LANG/TARGET_LANG; project model None subsequently inherits runtime defaults",
        runtime_consumer=ref(API, "source_lang=body.source_language") if key in {"source_language", "target_language"} else ref(API, "async def create_project"),
        application_timing="Project creation only", schema_ref=f"{API}:{field.lineno}", ui_ref="", api_ref=ref(API, '"/api/projects/create"'),
        notes="Languages use Japanese/Thai literals at API creation, unlike ProjectConfig English/Thai and snapshot auto/English defaults")

OUT.mkdir(parents=True, exist_ok=True)
with (OUT / "setting-inventory.csv").open("w", encoding="utf-8", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
counts = {scope: sum(row["scope"] == scope for row in rows) for scope in sorted({r["scope"] for r in rows})}
print({"rows": len(rows), "scopes": counts, "path": str(OUT / "setting-inventory.csv")})
