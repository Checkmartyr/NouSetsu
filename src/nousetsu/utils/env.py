"""Central environment discovery and dotenv cascade management."""
import hashlib
import json
import math
import tempfile
from types import MappingProxyType
from typing import Mapping
from dotenv.parser import parse_stream
from dotenv.variables import parse_variables
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Union
import dotenv
from nousetsu.utils.providers import usable_key

logger = logging.getLogger(__name__)

ENV_CONFIG_KEYS = (
    "DEFAULT_MODEL",
    "NOVEL_MODEL",
    "NOVEL_FALLBACK_MODEL",
    "NOVEL_SCRAPER_MODEL",
    "NOVEL_SCRAPER_TEMPERATURE",
    "NOVEL_SCRAPER_THINKING_LEVEL",
    "NOVEL_SCRAPER_THINKING_BUDGET",
    "NOVEL_SCRAPER_USE_INTERACTIONS",
    "NOVEL_EXTRACTOR_MODEL",
    "NOVEL_EXTRACTOR_TEMPERATURE",
    "NOVEL_EXTRACTOR_USE_INTERACTIONS",
    "NOVEL_DRAFTER_MODEL",
    "NOVEL_DRAFTER_TEMPERATURE",
    "NOVEL_DRAFTER_USE_INTERACTIONS",
    "NOVEL_CRITIC_MODEL",
    "NOVEL_CRITIC_TEMPERATURE",
    "NOVEL_CRITIC_USE_INTERACTIONS",
    "NOVEL_POLISHER_MODEL",
    "NOVEL_POLISHER_TEMPERATURE",
    "NOVEL_POLISHER_USE_INTERACTIONS",
    "NOVEL_CHRONICLER_MODEL",
    "NOVEL_CHRONICLER_TEMPERATURE",
    "NOVEL_CHRONICLER_USE_INTERACTIONS",
    "SOURCE_LANG",
    "TARGET_LANG",
    "NOVEL_MAX_TPM",
    "NOVEL_MAX_RPM",
    "NOVEL_MAX_REVIEW_LOOPS",
    "NOVEL_QUALITY_THRESHOLD",
    "NOVEL_PROJECTS_DIR",
    "NOVEL_THINKING_LEVEL",
    "NOVEL_EXTRACTOR_THINKING_LEVEL",
    "NOVEL_DRAFTER_THINKING_LEVEL",
    "NOVEL_CRITIC_THINKING_LEVEL",
    "NOVEL_POLISHER_THINKING_LEVEL",
    "NOVEL_CHRONICLER_THINKING_LEVEL",
    "NOVEL_THINKING_BUDGET",
    "NOVEL_EXTRACTOR_THINKING_BUDGET",
    "NOVEL_DRAFTER_THINKING_BUDGET",
    "NOVEL_CRITIC_THINKING_BUDGET",
    "NOVEL_POLISHER_THINKING_BUDGET",
    "NOVEL_CHRONICLER_THINKING_BUDGET",
    "NOVEL_TEMPERATURE",
    "NOVEL_USE_INTERACTIONS",
    "NOVEL_FILTER_EXTRACTOR_ENTITIES",
    "NOVEL_POST_POLISH_RECONCILIATION",
    "NOVEL_RAG_EMBEDDING_MODEL",
    "NOVEL_RAG_RERANKER_MODEL",
    "NOVEL_SCRAPER_PATH",
    "NOVEL_SCRAPER_PYTHON",
    "CUSTOM_API_BASE_URL",
)
ENV_CONFIG_KEYS += (
    "NOVEL_ENABLE_PROCEDURAL_GRAPH_LEARNING", "NOVEL_PROCEDURAL_LEARNING_CADENCE",
    "NOVEL_PROCEDURAL_LEARNING_INTERVAL", "NOVEL_PROCEDURAL_LEARNING_MIN_FAILURES",
    "NOVEL_PROCEDURAL_REFINER_MODEL",
)
ENV_SECRET_KEYS = (
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "CUSTOM_API_KEY",
)


def resolve_env_file() -> Path:
    """Resolve the user-editable environment file for this process."""
    configured_path = os.environ.get("NOUSETSU_ENV_FILE")
    if configured_path:
        return Path(configured_path).expanduser().resolve()
    root = find_repo_root()
    if (root / "pyproject.toml").is_file() or (root / ".git").exists():
        return root / ".env"
    if (Path.cwd() / ".env").is_file():
        return Path.cwd() / ".env"
    from nousetsu.utils.runtime_paths import user_config_dir
    return user_config_dir() / ".env"


def _apply_desktop_projects_default() -> None:
    """Use the Tauri-provided projects directory unless the user configured a custom one."""
    default_dir = os.environ.get("NOUSETSU_DEFAULT_PROJECTS_DIR")
    if not default_dir:
        return
    current_val = os.environ.get("NOVEL_PROJECTS_DIR")
    # If not set, empty, or still set to the default template placeholder, override with Tauri default
    if not current_val or current_val.strip() in ("project", "projects", "./project", ".\\project"):
        os.environ["NOVEL_PROJECTS_DIR"] = default_dir


def find_repo_root() -> Path:
    """Locate the codebase root directory containing pyproject.toml, .git, or central .env."""
    install_dir = os.environ.get("NOUSETSU_INSTALL_DIR")
    if install_dir and Path(install_dir).is_dir():
        return Path(install_dir).resolve()

    default_projects = os.environ.get("NOUSETSU_DEFAULT_PROJECTS_DIR")
    if default_projects:
        p_parent = Path(default_projects).resolve().parent
        if p_parent.is_dir():
            return p_parent

    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        if exe.parent.name == "nousetsu-backend" and exe.parent.parent.name == "binaries":
            return exe.parent.parent.parent.resolve()
        if exe.parent.name == "binaries":
            return exe.parent.parent.resolve()
        return exe.parent.resolve()

    if "site-packages" in Path(__file__).resolve().parts:
        from nousetsu.utils.runtime_paths import user_config_dir
        return user_config_dir()

    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").is_file() or (parent / ".git").exists() or (parent / ".env").is_file():
            return parent
    return current


def load_env(
    project_dir: Optional[Union[str, Path]] = None,
    override: bool = False,
) -> Optional[Path]:
    """Load environment variables from central repo .env and optional project-level .env.

    Cascade precedence:
    1. System / process environment variables (preserved when override=False)
    2. Project-level .env (e.g. project/Villainess/.env) if project_dir provided
    3. Central repo .env (e.g. D:/Code/novel_translation_Agent/.env)
    4. CWD .env if running from custom working directory
    """
    loaded_any: Optional[Path] = None

    configured_env = os.environ.get("NOUSETSU_ENV_FILE")
    if configured_env:
        env_path = Path(configured_env).expanduser()
        if env_path.is_file():
            dotenv.load_dotenv(env_path, override=override)
            _apply_desktop_projects_default()
            return env_path
        _apply_desktop_projects_default()
        return None

    # 1. Central repository .env
    repo_root = find_repo_root()
    central_env = repo_root / ".env"
    if central_env.is_file():
        dotenv.load_dotenv(central_env, override=override)
        loaded_any = central_env

    # 2. CWD .env if different from repo root
    cwd_env = Path.cwd() / ".env"
    if cwd_env.is_file() and cwd_env.resolve() != central_env.resolve():
        dotenv.load_dotenv(cwd_env, override=override)
        if not loaded_any:
            loaded_any = cwd_env

    # 3. Project-specific .env override if provided
    if project_dir:
        proj_path = Path(project_dir)
        proj_env = proj_path / ".env"
        if proj_env.is_file():
            dotenv.load_dotenv(proj_env, override=override)
            loaded_any = proj_env

    _apply_desktop_projects_default()
    return loaded_any


class EnvironmentValidationError(ValueError):
    """A safe field error that never includes the supplied value."""

    def __init__(self, key: str, message: str = "Invalid setting value"):
        self.key = key
        super().__init__(message)


class SettingsRevisionConflict(ValueError):
    pass


def _read_dotenv(path: Path) -> Dict[str, Optional[str]]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8-sig") as stream:
        bindings = list(parse_stream(stream))
    if any(binding.error for binding in bindings):
        raise EnvironmentValidationError("dotenv", "Malformed dotenv file")
    return {binding.key: binding.value for binding in bindings if binding.key is not None}


def resolve_env_with_sources(project_dir=None, environ=None, machine_updates=None):
    """Resolve file layers without modifying the process environment."""
    process = dict(os.environ if environ is None else environ)
    selected = Path(process["NOUSETSU_ENV_FILE"]).expanduser().resolve() if process.get("NOUSETSU_ENV_FILE") else resolve_env_file()
    layers = []
    cwd_file = Path.cwd() / ".env"
    if not process.get("NOUSETSU_ENV_FILE") and cwd_file.resolve() != selected.resolve():
        layers.append((cwd_file, "cwd"))
    layers.append((selected, "machine"))
    if project_dir:
        project_file = Path(project_dir).resolve() / ".env"
        if project_file.resolve() != selected.resolve():
            layers.append((project_file, "project_env"))
    raw = {}
    sources = {}
    for path, origin in layers:
        entries = _read_dotenv(path)
        if origin == "machine" and machine_updates:
            for key, value in machine_updates.items():
                if value is None:
                    entries.pop(key, None)
                else:
                    entries[key] = value
        for key, value in entries.items():
            # A bare key has no value and does not shadow a lower layer.
            if value is not None:
                raw[key] = value
                sources[key] = origin
    raw.update(process)
    sources.update({key: "process" for key in process})
    resolved = {}
    tainted = set(ENV_SECRET_KEYS)

    def expand(key, visiting):
        if key in resolved:
            return resolved[key]
        if key in visiting:
            raise EnvironmentValidationError("dotenv", "Cyclic dotenv interpolation")
        value = raw.get(key, "")
        # Process variables are explicit values, not dotenv expressions.
        if sources.get(key) != "process":
            atoms = list(parse_variables(value))
            if any("${" in getattr(atom, "value", "") for atom in atoms):
                raise EnvironmentValidationError("dotenv", "Malformed dotenv interpolation")
            context = {}
            for atom in atoms:
                name = getattr(atom, "name", None)
                if name is not None and name in raw:
                    context[name] = expand(name, visiting | {key})
                    if name in tainted:
                        tainted.add(key)
            value = "".join(atom.resolve(context) for atom in atoms)
        if key in ENV_CONFIG_KEYS and key in tainted:
            raise EnvironmentValidationError(key, "A non-secret setting cannot reference credentials")
        resolved[key] = value
        return value

    for key in raw:
        expand(key, set())
    default_dir = process.get("NOUSETSU_DEFAULT_PROJECTS_DIR")
    current = resolved.get("NOVEL_PROJECTS_DIR", "")
    if default_dir and (not current or (sources.get("NOVEL_PROJECTS_DIR") != "process" and current.strip() in ("project", "projects", "./project", ".\\project"))):
        resolved["NOVEL_PROJECTS_DIR"] = default_dir
        sources["NOVEL_PROJECTS_DIR"] = "desktop_default"
    return MappingProxyType(resolved), MappingProxyType(sources)


def resolve_env(project_dir=None, environ=None) -> Mapping[str, str]:
    return resolve_env_with_sources(project_dir, environ)[0]


def settings_revision(path: Path, environ: Mapping[str, str]) -> str:
    """Opaque fingerprint includes relevant effective environment, including credentials."""
    relevant = {key: environ.get(key) for key in (*ENV_CONFIG_KEYS, *ENV_SECRET_KEYS)}
    digest = hashlib.sha256(str(path.resolve()).encode())
    digest.update(path.read_bytes() if path.is_file() else b"<missing>")
    digest.update(json.dumps(relevant, sort_keys=True).encode())
    return digest.hexdigest()


def _normalize_env_value(key: str, raw: object) -> str:
    if raw is None:
        return ""
    if not isinstance(raw, (str, int, float, bool)):
        raise EnvironmentValidationError(key)
    value = str(raw).strip()
    if any(char in value for char in "\n\r\0") or len(value) > 8192:
        raise EnvironmentValidationError(key)
    if not value:
        return value
    is_bool = key.endswith("_USE_INTERACTIONS") or key in {"NOVEL_USE_INTERACTIONS", "NOVEL_FILTER_EXTRACTOR_ENTITIES", "NOVEL_POST_POLISH_RECONCILIATION", "NOVEL_ENABLE_PROCEDURAL_GRAPH_LEARNING"}
    if is_bool:
        if value.lower() not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
            raise EnvironmentValidationError(key, "Expected a Boolean value")
        return "true" if value.lower() in {"true", "1", "yes", "on"} else "false"
    bounds = None
    if key.endswith("_THINKING_BUDGET"):
        bounds = (0, None, int)
    elif key in {"NOVEL_MAX_TPM", "NOVEL_MAX_RPM", "NOVEL_PROCEDURAL_LEARNING_INTERVAL", "NOVEL_PROCEDURAL_LEARNING_MIN_FAILURES"}:
        bounds = (1, None, int)
    elif key == "NOVEL_MAX_REVIEW_LOOPS":
        bounds = (1, 5, int)
    elif key == "NOVEL_QUALITY_THRESHOLD":
        bounds = (5, 10, float)
    elif key.endswith("_TEMPERATURE"):
        bounds = (0, 2, float)
    if bounds:
        lower, upper, cast = bounds
        try:
            if isinstance(raw, bool):
                raise ValueError
            number = cast(value)
            if not math.isfinite(number) or number < lower or (upper is not None and number > upper):
                raise ValueError
        except (ValueError, OverflowError):
            raise EnvironmentValidationError(key, "Number is invalid or outside its allowed range") from None
        return str(number)
    if key.endswith("_THINKING_LEVEL") and value not in {"minimal", "low", "medium", "high"}:
        raise EnvironmentValidationError(key, "Unsupported thinking level")
    if key == "NOVEL_PROCEDURAL_LEARNING_CADENCE" and value not in {"arc", "interval", "both"}:
        raise EnvironmentValidationError(key, "Unsupported learning cadence")
    if key == "CUSTOM_API_BASE_URL":
        from nousetsu.utils.model_catalog import _custom_models_url
        try:
            _custom_models_url(value)
        except ValueError:
            raise EnvironmentValidationError(key, "Expected an HTTP(S) provider base URL without credentials or query") from None
    if not isinstance(raw, str):
        raise EnvironmentValidationError(key, "Expected a string")
    return value


def credential_values(project_dir=None):
    """Include shadowed file credentials when sanitizing display fields."""
    paths = {resolve_env_file()}
    if not os.environ.get("NOUSETSU_ENV_FILE"):
        paths.add(Path.cwd() / ".env")
    if project_dir:
        paths.add(Path(project_dir) / ".env")
    secrets = []
    for path in paths:
        try:
            parsed = _read_dotenv(path)
            secrets.extend(parsed[key] for key in ENV_SECRET_KEYS if parsed.get(key))
        except (EnvironmentValidationError, OSError):
            continue
    return secrets


def redact_settings(value, environ, extra_secrets=None):
    """Prevent credentials copied into display fields from reaching responses."""
    if extra_secrets is None:
        extra_secrets = credential_values()
    secrets = [environ.get(key) for key in ENV_SECRET_KEYS if environ.get(key)] + list(extra_secrets)
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, "[redacted]")
        return value
    if isinstance(value, dict):
        return {key: redact_settings(item, environ, extra_secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_settings(item, environ, extra_secrets) for item in value]
    return value


def get_env_settings() -> Dict[str, object]:
    from nousetsu.storage.settings_store import file_lock, SettingsLockTimeout
    env_path = resolve_env_file()
    with file_lock(env_path.with_name(env_path.name + ".lock")):
        for _ in range(3):
            before = env_path.read_bytes() if env_path.exists() else None
            result = _get_env_settings()
            after = env_path.read_bytes() if env_path.exists() else None
            if before == after:
                return result
        raise SettingsLockTimeout("Settings changed while reading; try again")


def _get_env_settings() -> Dict[str, object]:
    """Return raw editable values, effective origins and safe validation diagnostics."""
    env_path = resolve_env_file()
    errors = []
    try:
        parsed = _read_dotenv(env_path)
        effective, origins = resolve_env_with_sources()
    except EnvironmentValidationError as error:
        parsed = {}
        effective = dict(os.environ)
        origins = {key: "process" for key in effective}
        errors.append({"loc": [error.key], "msg": str(error)})
    for key in ENV_CONFIG_KEYS:
        try:
            _normalize_env_value(key, effective.get(key, ""))
        except EnvironmentValidationError as error:
            errors.append({"loc": [key], "msg": str(error)})
    return redact_settings({
        "env_file_path": str(env_path),
        "values": {key: parsed.get(key) or "" for key in ENV_CONFIG_KEYS},
        "effective_values": get_env_snapshot(effective),
        "sources": {key: origins.get(key, "builtin") for key in ENV_CONFIG_KEYS},
        "validation_errors": errors,
        "api_key_status": {key: usable_key(effective.get(key)) for key in ENV_SECRET_KEYS},
        "revision": settings_revision(env_path, effective),
    }, effective)


def save_env_settings(values, api_keys, clear_api_keys, expected_revision=None) -> Dict[str, object]:
    """Validate all changes, then replace the dotenv once under its stable lock."""
    from nousetsu.storage.repository import atomic_write_file
    from nousetsu.storage.settings_store import file_lock
    if set(values) - set(ENV_CONFIG_KEYS) or set(api_keys) - set(ENV_SECRET_KEYS) or set(clear_api_keys) - set(ENV_SECRET_KEYS):
        raise EnvironmentValidationError("settings", "Unsupported environment setting key")
    updates = {key: _normalize_env_value(key, raw) for key, raw in {**values, **api_keys}.items()}
    if any(key in clear_api_keys and updates.get(key) for key in clear_api_keys):
        raise EnvironmentValidationError("api_keys", "A key cannot be replaced and cleared together")
    env_path = resolve_env_file()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(env_path.with_name(env_path.name + ".lock")):
        current = get_env_settings()
        if expected_revision is not None and expected_revision != current["revision"]:
            raise SettingsRevisionConflict("Settings changed; reload before saving")
        original = env_path.read_text(encoding="utf-8-sig") if env_path.exists() else ""
        candidate = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=env_path.parent, delete=False) as temp:
                candidate = Path(temp.name)
                temp.write(original)
            for key, value in updates.items():
                if key in ENV_SECRET_KEYS and not value:
                    continue
                if value:
                    dotenv.set_key(candidate, key, value, quote_mode="always", encoding="utf-8")
                else:
                    dotenv.unset_key(candidate, key, encoding="utf-8")
            for key in clear_api_keys:
                dotenv.unset_key(candidate, key, encoding="utf-8")
            parsed_candidate = _read_dotenv(candidate)
            candidate_process = {key: value for key, value in os.environ.items() if key not in parsed_candidate}
            candidate_process["NOUSETSU_ENV_FILE"] = str(candidate)
            candidate_effective = resolve_env(environ=candidate_process)
            for key in ENV_CONFIG_KEYS:
                _normalize_env_value(key, candidate_effective.get(key, ""))
            atomic_write_file(env_path, candidate.read_text(encoding="utf-8"), strict=True, permissions=0o600)
        finally:
            if candidate is not None:
                candidate.unlink(missing_ok=True)
        return get_env_settings()


def get_env_snapshot(environ: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    """Return a non-secret snapshot of supported NouSetsu environment variables."""
    env = resolve_env() if environ is None else environ
    return {
        "DEFAULT_MODEL": env.get("DEFAULT_MODEL", ""),
        "NOVEL_MODEL": env.get("NOVEL_MODEL", env.get("DEFAULT_MODEL", "gemini-3.1-flash-lite")),
        "NOVEL_FALLBACK_MODEL": env.get("NOVEL_FALLBACK_MODEL", "gemini-3.5-flash-lite"),
        "NOVEL_EXTRACTOR_MODEL": env.get("NOVEL_EXTRACTOR_MODEL", ""),
        "NOVEL_DRAFTER_MODEL": env.get("NOVEL_DRAFTER_MODEL", ""),
        "NOVEL_CRITIC_MODEL": env.get("NOVEL_CRITIC_MODEL", "gemma-4-26b-a4b-it"),
        "NOVEL_POLISHER_MODEL": env.get("NOVEL_POLISHER_MODEL", ""),
        "NOVEL_CHRONICLER_MODEL": env.get("NOVEL_CHRONICLER_MODEL", "gemma-4-26b-a4b-it"),
        "SOURCE_LANG": env.get("SOURCE_LANG", "auto"),
        "TARGET_LANG": env.get("TARGET_LANG", "English"),
        "NOVEL_MAX_TPM": env.get("NOVEL_MAX_TPM", "32000"),
        "NOVEL_MAX_RPM": env.get("NOVEL_MAX_RPM", "60"),
        "NOVEL_MAX_REVIEW_LOOPS": env.get("NOVEL_MAX_REVIEW_LOOPS", "3"),
        "NOVEL_QUALITY_THRESHOLD": env.get("NOVEL_QUALITY_THRESHOLD", "8.5"),
        "NOVEL_PROJECTS_DIR": env.get("NOVEL_PROJECTS_DIR", "project"),
        "NOVEL_THINKING_LEVEL": env.get("NOVEL_THINKING_LEVEL", ""),
        "NOVEL_CRITIC_THINKING_LEVEL": env.get("NOVEL_CRITIC_THINKING_LEVEL", ""),
        "NOVEL_POLISHER_THINKING_LEVEL": env.get("NOVEL_POLISHER_THINKING_LEVEL", ""),
        **{
            key: env.get(key, "")
            for key in ENV_CONFIG_KEYS
            if key not in {
                "DEFAULT_MODEL", "NOVEL_MODEL", "NOVEL_FALLBACK_MODEL",
                "NOVEL_EXTRACTOR_MODEL", "NOVEL_DRAFTER_MODEL", "NOVEL_CRITIC_MODEL",
                "NOVEL_POLISHER_MODEL", "NOVEL_CHRONICLER_MODEL", "SOURCE_LANG",
                "TARGET_LANG", "NOVEL_MAX_TPM", "NOVEL_MAX_RPM",
                "NOVEL_MAX_REVIEW_LOOPS", "NOVEL_QUALITY_THRESHOLD", "NOVEL_PROJECTS_DIR",
                "NOVEL_THINKING_LEVEL", "NOVEL_CRITIC_THINKING_LEVEL",
                "NOVEL_POLISHER_THINKING_LEVEL",
            }
        },
    }
