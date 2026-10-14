"""Generate repair coverage without promoting missing or aggregate evidence to passes."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from nousetsu.models.config import AgentGenerationSettings, GENERATION_ROLES, ProjectConfig

ROOT = Path(__file__).resolve().parents[2]
MODES = ("source_api", "frozen_api", "web_dev", "web_built", "native_dev", "native_release")
STATUSES = {"pass", "fail", "blocked", "not applicable"}
PROCEDURAL = {
    "enable_procedural_graph_learning", "procedural_learning_cadence",
    "procedural_learning_interval", "procedural_learning_min_failures", "procedural_refiner_model",
}
UI_ACTIONS = {"load_env_presets", "apply_model_preset", "clear_model_overrides", "category_search"}
RUNTIME_TESTS = {
    "project.chunk_overlap_lines": ("test_overlap_is_consumed_in_next_chunk", "test_repaired_chunk_overlap_zero_supplies_no_context"),
    "project.filter_scene_characters": ("test_repaired_disabled_scene_filter_retains_full_roster",),
    "project.cross_folder_summaries": ("test_repaired_disabled_scene_filter_retains_full_roster",),
    "project.max_review_loops": ("test_repaired_review_quota_project_precedes_env_and_constructor_wins", "test_saved_review_threshold_requires_both_scores"),
    "project.quality_threshold": ("test_saved_review_threshold_requires_both_scores",),
    "project.max_tpm": ("test_repaired_review_quota_project_precedes_env_and_constructor_wins",),
    "project.max_rpm": ("test_repaired_review_quota_project_precedes_env_and_constructor_wins",),
    "project.enable_post_polish_reconciliation": ("test_repaired_reconciliation_default_inherits_environment",),
    "project.enable_patch_polishing": ("test_settings_during_real_source_job_affect_subsequent_job_only",),
    "project.filter_extractor_entities": ("test_repaired_inherited_extractor_false_get_exposes_raw_null",),
}
for _role in ("extractor", "drafter", "critic", "polisher", "chronicler"):
    RUNTIME_TESTS[f"project.{_role}_model"] = ("test_source_provider_factory_spies_record_real_resolution_without_live_calls",)
    for _control in ("temperature", "thinking_level", "thinking_budget", "use_interactions_api"):
        RUNTIME_TESTS[f"project.generation_settings.{_role}.{_control}"] = ("test_source_provider_factory_spies_record_real_resolution_without_live_calls",)


def read_records(path: Path) -> list[dict]:
    """Absent evidence is blocked; malformed evidence must stop generation."""
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("observations", data.get("cases"))
    if not isinstance(data, list):
        raise ValueError(f"Expected observation list: {path.name}")
    observations = []
    for record in data:
        if isinstance(record, dict) and record.get("case") == "translation_start" and "status" not in record:
            # Transport diagnostic, not a scored settings observation.
            continue
        if not isinstance(record, dict) or record.get("status") not in STATUSES:
            raise ValueError(f"Missing or invalid observation status: {path.name}")
        observations.append(record)
    return observations


def junit_cases(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    cases = {}
    for case in ET.parse(path).getroot().iter("testcase"):
        name = case.attrib.get("name")
        if not name:
            raise ValueError("JUnit testcase has no name")
        status = "fail" if case.find("failure") is not None or case.find("error") is not None else "blocked" if case.find("skipped") is not None else "pass"
        # Keep failures if duplicate test names exist.
        cases[name] = status if cases.get(name) != "fail" else "fail"
    return cases


def frozen_records(data: Path) -> list[dict]:
    records = read_records(data / "frozen-results.json")
    if not records:
        return []
    identity = next((record for record in records if record.get("case") == "isolated_environment"), {})
    components = str(identity.get("path", "")).replace("\\", "/").split("/")
    if not any(component.startswith("frozen-") for component in components):
        raise ValueError("Frozen evidence does not identify an isolated frozen fixture")
    manifest = data / "provenance.json"
    if not manifest.exists():
        return []
    provenance = json.loads(manifest.read_text(encoding="utf-8"))
    artifact = provenance.get("repair_artifacts", {}).get("frozen_backend", {})
    if not artifact:
        return []
    if artifact.get("source_identity") != "built from audited source" or not artifact.get("sha256") or artifact["sha256"] != identity.get("binary_sha256"):
        raise ValueError("Frozen evidence binary does not match fresh audited build provenance")
    return records


def canonical_id(field: str, indexed: dict) -> str:
    if field in indexed:
        return field
    aliases = {"chunk_size_lines": "target_chunk_lines", "translated_dir": "output_dir", "effective_model_name": "model_name", "logs": "action.logs_refresh", "updates": "action.check_updates"}
    field = aliases.get(field, field)
    if field in indexed:
        return field
    return ("env." if field.isupper() else "project.") + field


def current_inventory(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or len({row["setting_id"] for row in rows}) != len(rows):
        raise ValueError("Inventory is empty or has duplicate setting IDs")
    defaults = ProjectConfig().get_effective_config({})
    for row in rows:
        row["notes"] = "Repair inventory; historical source references replaced where schema changed. Coverage is scenario-specific."
        row["evidence"] = ""
        for mode in MODES:
            row[mode] = "blocked"
        key = row["key"]
        for reference in ("schema_ref", "ui_ref", "api_ref", "runtime_consumer"):
            if reference in row:
                row[reference] = re.sub(r"(\.[a-zA-Z]+):\d+", r"\1", row[reference])
        if row["scope"] == "project" and key in ProjectConfig.model_fields:
            field = ProjectConfig.model_fields[key]
            row["schema_default"] = repr(field.default) if field.default_factory is None else "factory"
            row["effective_default"] = repr(defaults.get(key))
            row["type"] = str(field.annotation)
            row["constraints"] = "; ".join(str(item) for item in field.metadata)
            row["schema_ref"] = "src/nousetsu/models/config.py"
            if key in PROCEDURAL:
                row["ui_exposure"] = "editable"
            if field.default is None:
                row["inheritance_reset"] = "Null/reset inherits current environment then built-in default; existing valid concrete saved values remain overrides."
            if key in {"title", "genre", "source_language", "target_language", "cross_folder_summaries"}:
                row["storage"] = ".novel/config.yaml + .novel/bible/bible.yaml (one recoverable transaction)"
                row["inheritance_reset"] = "Explicit project metadata; config is authoritative and synchronized with Bible."
        if row["scope"] == "project_generation":
            control = key.rsplit(".", 1)[-1]
            parts = key.split(".")
            role = next((part for part in parts if part in GENERATION_ROLES), None)
            if control in AgentGenerationSettings.model_fields:
                field = AgentGenerationSettings.model_fields[control]
                row["schema_default"] = repr(field.default)
                row["constraints"] = "; ".join(str(item) for item in field.metadata)
                if role:
                    row["effective_default"] = repr(defaults["generation_settings"][role][control])
            row["inheritance_reset"] = "Null role control inherits legacy project Interactions (where applicable), role environment, shared environment, then built-in role default."
        if row["scope"] == "env_unexposed":
            row["scope"] = "env"
            row["ui_exposure"] = "editable"
            row["api_endpoint"] = "GET/PUT /api/environment"
            row["api_name"] = f"values.{key}"
        if row["setting_id"].startswith("env."):
            row["schema_ref"] = "src/nousetsu/utils/env.py"
            row["api_ref"] = "src/nousetsu/cli/web_server.py"
            row["storage"] = "Selected machine dotenv file; complete atomic replacement; no process-environment mutation."
            row["inheritance_reset"] = "Explicit process value wins; project dotenv overlays selected machine dotenv; blank default clears file override. Blank secret preserves; explicit clearing removes file secret."
            row["application_timing"] = "Next immutable job snapshot; active jobs retain captured environment. Process overrides require a process restart/change."
            if key in {"SOURCE_LANG", "TARGET_LANG"}:
                row["application_timing"] = "Next project creation/default form initialization; existing project languages remain concrete. Process values remain authoritative."
                row["effective_default"] = "Web creation Japanese; CLI parser English" if key == "SOURCE_LANG" else "Thai for creation when no explicit/default override"
            elif key == "NOVEL_PROJECTS_DIR":
                row["application_timing"] = "Next project listing/path resolution or creation; does not relocate existing projects."
            elif row["scope"] == "env_secret" or key == "CUSTOM_API_BASE_URL":
                row["application_timing"] = "Next provider construction/catalog request or new scraper subprocess; active job retains captured provider credentials."
            elif key in {"NOVEL_SCRAPER_PATH", "NOVEL_SCRAPER_PYTHON"}:
                row["application_timing"] = "Next scraper bridge discovery/construction; existing bridge retains its selected executable and directory."
            if key.endswith("TEMPERATURE"):
                row["constraints"] = "Finite numeric value, 0–2; blank removes file override"
            elif key.endswith("THINKING_BUDGET"):
                row["constraints"] = "Integer >=0; blank removes file override"
            elif key in {"NOVEL_MAX_TPM", "NOVEL_MAX_RPM", "NOVEL_PROCEDURAL_LEARNING_INTERVAL", "NOVEL_PROCEDURAL_LEARNING_MIN_FAILURES"}:
                row["constraints"] = "Integer >=1; blank removes file override"
            elif key == "NOVEL_MAX_REVIEW_LOOPS":
                row["constraints"] = "Integer 1–5; blank removes file override"
            elif key == "NOVEL_QUALITY_THRESHOLD":
                row["constraints"] = "Finite numeric value, 5–10; blank removes file override"
            elif key.endswith("THINKING_LEVEL"):
                row["constraints"] = "minimal, low, medium, high; blank removes file override"
            elif key.endswith("USE_INTERACTIONS") or key in {"NOVEL_FILTER_EXTRACTOR_ENTITIES", "NOVEL_POST_POLISH_RECONCILIATION", "NOVEL_ENABLE_PROCEDURAL_GRAPH_LEARNING"}:
                row["constraints"] = "Boolean token: true/false, 1/0, yes/no, on/off; blank removes file override"
            elif key == "NOVEL_PROCEDURAL_LEARNING_CADENCE":
                row["constraints"] = "arc, interval, both; blank removes file override"
            else:
                row["constraints"] = "String without prohibited control characters; secret replace+clear conflict rejected"
        elif row["scope"] in {"project", "project_generation"} and key not in {"title", "genre", "source_language", "target_language", "project_id", "created_at"}:
            row["application_timing"] = "Next runner/job; current job retains captured controls."
        if row["scope"] == "project_creation":
            row["inheritance_reset"] = "Omitted creation languages use current global defaults; explicit inputs win; existing languages stay concrete."
        if "thinking_budget" in key:
            row["notes"] += " Budget is retained but sent only on supported non-Interactions transport; Interactions has no supported budget mapping."
    return rows


def generate(inventory: Path, data: Path) -> dict:
    rows = current_inventory(inventory)
    indexed = {row["setting_id"]: row for row in rows}
    proof = {key: [] for key in indexed}
    runtime = {key: [] for key in indexed}

    def mark(setting, mode, status, evidence):
        if setting not in indexed:
            raise ValueError(f"Evidence refers to unknown setting: {setting}")
        if status not in STATUSES or mode not in MODES:
            raise ValueError("Invalid evidence status or mode")
        prior = indexed[setting][mode]
        if prior != "fail" or status == "fail":
            indexed[setting][mode] = status
        proof[setting].append(f"{mode}: {evidence}")

    for row in rows:
        key = row["key"]
        if row["scope"] == "settings_action" and key in UI_ACTIONS:
            for mode in ("source_api", "frozen_api"):
                mark(row["setting_id"], mode, "not applicable", "UI action; underlying endpoints have separate rows")
        if key == "logs_open":
            for mode in MODES:
                mark(row["setting_id"], mode, "not applicable", "External file-manager opening excluded; no computer-use")
        if key == "created_at" or row["ui_exposure"] == "schema/API legacy":
            for mode in MODES[2:]:
                mark(row["setting_id"], mode, "not applicable", "No editable independent UI control; reset legacy override is covered by its action")

    for filename, mode in (("source-results.json", "source_api"), ("frozen-results.json", "frozen_api")):
        records = frozen_records(data) if mode == "frozen_api" else read_records(data / filename)
        for record in records:
            case, status = record.get("case", "observation"), record["status"]
            setting = record.get("setting_id")
            if setting:
                mark(setting, mode, status, f"{filename}: {case}")
                if setting == "project.generation_settings":
                    actual = record.get("actual", {})
                    if not isinstance(actual, dict):
                        raise ValueError("Generation map evidence is malformed")
                    for role, controls in actual.items():
                        if role not in GENERATION_ROLES or not isinstance(controls, dict):
                            raise ValueError("Generation role evidence is malformed")
                        for control in controls:
                            mark(f"project.generation_settings.{role}.{control}", mode, status, f"{filename}: {case}, explicitly returned nested control")
            if case == "invalid_review_loop":
                mark("project.max_review_loops", mode, status, f"{filename}: invalid_review_loop rejection/disk consistency")
            elif case == "local_provider_catalog":
                mark("action.provider_catalog", mode, status, f"{filename}: local custom-provider /models transport")
            elif case == "runtime_provider_payloads":
                for role in ("extractor", "drafter", "critic", "polisher", "chronicler"):
                    for setting in (f"project.{role}_model", f"project.generation_settings.{role}.temperature"):
                        runtime[setting].append(f"{mode}: {filename} runtime_provider_payloads ({status}); captured model/temperature and completed output")
                        if status == "fail":
                            mark(setting, mode, status, f"{filename}: runtime_provider_payloads failure")

    for record in read_records(data / "browser-results.json"):
        mode = {"web-dev": "web_dev", "web-built": "web_built"}.get(record.get("mode"))
        if mode is None:
            raise ValueError("Browser observation has unknown mode")
        scenario, status = record.get("scenario", "observation"), record["status"]
        for field in record.get("fields", []):
            mark(canonical_id(field, indexed), mode, status, f"browser-results.json: {scenario}")
        actions = []
        if "preset coverage" in scenario:
            actions.append("apply_model_preset")
        if "presets/reset/load-env/custom catalog/navigation" in scenario:
            actions += ["load_env_presets", "clear_model_overrides", "provider_catalog", "category_search"]
        if "clear all" in scenario:
            actions.append("clear_model_overrides")
        for action in actions:
            mark("action." + action, mode, status, f"browser-results.json: {scenario}")

    for mode in ("native_dev", "native_release"):
        for suffix in ("-results.json", "-cdp-results.json"):
            filename = mode.replace("_", "-") + suffix
            for record in read_records(data / filename):
                settings = record.get("setting_ids", record.get("fields", []))
                if record.get("setting_id"):
                    settings = [record["setting_id"]]
                for setting in settings:
                    mark(canonical_id(setting, indexed), mode, record["status"], f"{filename}: {record.get('case', record.get('scenario', 'actual WebView observation'))}; persistence/control behavior only")

    cases = junit_cases(data / "python-junit.xml")
    update_test = "test_github_release_endpoint_compares_tags_and_returns_downloads"
    if update_test in cases:
        mark("action.check_updates", "source_api", cases[update_test], f"python-junit.xml: {update_test}; mocked GitHub release response/version comparison, source API only; no update installation")
    for setting, names in RUNTIME_TESTS.items():
        matched = [(name, status) for name, status in cases.items() if any(name == target or name.startswith(target + "[") for target in names)]
        for name, status in matched:
            runtime[setting].append(f"source Python regression: python-junit.xml {name} ({status}); no inferred frozen/native consumption")
            if status == "fail":
                mark(setting, "source_api", status, f"python-junit.xml: {name}")
    for mode in MODES:
        children = [row for row in rows if row["scope"] == "project_generation"]
        if children and all(row[mode] == "pass" for row in children):
            mark("project.generation_settings", mode, "pass", "Every nested role/control has direct successful evidence")
    for setting, row in indexed.items():
        row["evidence"] = " | ".join(dict.fromkeys(proof[setting]))
        row["runtime_evidence"] = " | ".join(dict.fromkeys(runtime[setting])) or "Not independently consumed in this setting's mode; persistence does not establish runtime/provider parity."
        row["blocked_reason"] = " | ".join(f"{mode}: no direct completed per-setting observation" for mode in MODES if row[mode] == "blocked")
    summary = {mode: dict(Counter(row[mode] for row in rows)) for mode in MODES}
    complete = bool(cases) and all(status == "pass" for status in cases.values()) and all(row[mode] not in {"fail", "blocked"} for row in rows for mode in MODES)
    result = {
        "settings": len(rows), "modes": summary,
        "signoff": "PASS: all applicable setting scenarios observed" if complete else "INCOMPLETE: failed or unobserved setting/mode scenarios remain",
        "status_definition": "Worst directly recorded scenario per setting and mode. Pass establishes the cited scenario, not every boundary or provider behavior. Missing evidence stays blocked. Source JUnit runtime checks are qualified separately and never promoted to native/frozen runtime observations.",
        "python_regressions": dict(Counter(cases.values())),
    }
    data.mkdir(parents=True, exist_ok=True)
    for filename in ("setting-inventory.csv", "setting-mode-matrix.csv"):
        with (data / filename).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(key for row in rows for key in row)))
            writer.writeheader()
            writer.writerows(rows)
    (data / "matrix-summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=ROOT / "audit-results/settings/setting-inventory.csv")
    parser.add_argument("--evidence-dir", type=Path, default=ROOT / "audit-results/settings-repair")
    args = parser.parse_args()
    if args.inventory.resolve().parent == args.evidence_dir.resolve():
        parser.error("Repair output must not overwrite its input inventory")
    print(json.dumps(generate(args.inventory, args.evidence_dir)))


if __name__ == "__main__":
    main()
