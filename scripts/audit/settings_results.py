"""Merge measured settings evidence; unexercised cells never become passes."""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "audit-results/settings"
MODES = ("source_api", "frozen_api", "web_dev", "web_built", "native_dev", "native_release")


def read_json(name: str, fallback: object) -> object:
    path = DATA / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else fallback


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    with (DATA / "setting-inventory.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    indexed = {row["setting_id"]: row for row in rows}
    evidence: dict[str, list[str]] = {key: [] for key in indexed}
    reasons: dict[str, list[str]] = {key: [] for key in indexed}
    for row in rows:
        for mode in MODES:
            row[mode] = "blocked"
        row["runtime_evidence"] = "Not individually observed"
        row["logic_findings"] = ""

    def mark(setting: str, mode: str, status: str, proof: str) -> None:
        if setting not in indexed:
            return
        row = indexed[setting]
        if row[mode] != "fail" or status == "fail":
            row[mode] = status
        evidence[setting].append(mode + ": " + proof)

    backend = read_json("backend-source-results.json", {})
    backend_tests = backend.get("tests", {})
    backend_complete = backend_tests.get("total", 0) > 0 and all(backend_tests.get(key) == 0 for key in ("failures", "errors", "skipped"))
    for row in rows:
        scope = row["scope"]
        key = row["key"]
        if backend_complete and (scope in {"env", "env_secret", "environment", "global"} or (row["setting_id"].startswith("env.") and scope != "env_unexposed")):
            mark(row["setting_id"], "source_api", "pass", "All allowlisted values/key lifecycle: backend source diagnostics")
        if backend_complete and scope == "project" and key in backend.get("covered_project_fields", []):
            mark(row["setting_id"], "source_api", "pass", "Valid API save, YAML/fresh app reload, A/B isolation")
        if backend_complete and scope == "project_generation":
            mark(row["setting_id"], "source_api", "pass", "Six-role validated map roundtrip and reset; pipeline factory spies")
        if scope == "env_unexposed":
            for mode in MODES:
                mark(row["setting_id"], mode, "not applicable", "Not allowlisted/exposed through settings API or UI; schema/runtime gap recorded")
        if row["ui_exposure"] in {"schema-only", "schema/API legacy", "read-only"}:
            for mode in ("web_dev", "web_built", "native_dev", "native_release"):
                mark(row["setting_id"], mode, "not applicable", "No editable UI control")
        if row["key"] == "created_at":
            if backend_complete:
                mark(row["setting_id"], "source_api", "pass", "Read-only metadata is not overwritten by settings PUT")
            mark(row["setting_id"], "frozen_api", "not applicable", "Read-only; no independent frozen mutation assertion")
        if backend_complete and scope == "project_creation":
            mark(row["setting_id"], "source_api", "pass" if key in {"title", "folder_name"} else "blocked", "Creation diagnostic covers omitted languages and explicit title/folder; remaining inputs not individually exercised")
        if scope == "settings_action" and key in {"load_env_presets", "apply_model_preset", "clear_model_overrides", "category_search"}:
            for mode in ("source_api", "frozen_api"):
                mark(row["setting_id"], mode, "not applicable", "UI action; underlying save/read endpoints audited separately")
        if row["setting_id"] == "action.logs_open":
            for mode in MODES:
                mark(row["setting_id"], mode, "not applicable", "Opening external file-manager windows is deliberately excluded")
    if backend_complete:
        mark("action.provider_catalog", "source_api", "pass", "Isolated TestClient provider/catalog/key-redaction tests")
        mark("action.check_updates", "source_api", "pass", "Mocked release response and version-comparison TestClient checks")

    boolean_keys = {row["key"] for row in rows if row["scope"] == "project" and "bool" in row["type"] and row["key"] in backend.get("covered_project_fields", [])}
    for finding in backend.get("confirmed_findings", []) if backend_complete else []:
        for field in finding.get("fields", []):
            affected: list[str] = []
            if field == "all global settings":
                affected = ["env.NOVEL_MAX_REVIEW_LOOPS", "env.NOVEL_QUALITY_THRESHOLD"]
            elif field == "all project settings":
                affected = ["project.title"]
            elif field == "all environment-derived model/generation values":
                affected = ["env.NOVEL_MODEL"]
            elif field == "all project Boolean fields":
                affected = ["project." + key for key in boolean_keys]
            elif field == "procedural learning fields":
                affected = [row["setting_id"] for row in rows if row["scope"] == "project" and "procedural" in row["key"]]
            elif field in {"thinking_budget", "use_interactions_api"} and finding["id"] == "B17":
                # This omission is provider-specific; Interactions mode does not
                # expose a budget editor. Keep it in logic evidence, not falsely
                # declare a supported custom-provider request failed.
                for row in rows:
                    if row["setting_id"].endswith("thinking_budget"):
                        row["logic_findings"] += "B17 (Interactions-only limitation); "
                continue
            elif field.startswith("NOVEL_") or field in {"SOURCE_LANG", "TARGET_LANG"}:
                affected = ["env." + field]
                if finding["id"] == "B16":
                    affected += ["creation." + ("source_language" if field == "SOURCE_LANG" else "target_language")]
            elif "project." + field in indexed:
                affected = ["project." + field]
            for setting in affected:
                if setting in indexed:
                    indexed[setting]["logic_findings"] += finding["id"] + "; "
                    mark(setting, "source_api", "fail", finding["id"] + ": " + finding["defect"])

    for record in read_json("frozen-results.json", []):
        setting = record.get("setting_id")
        if setting:
            mark(setting, "frozen_api", record["status"], record["case"])
            if setting == "project.generation_settings" and record.get("status") == "pass":
                for role, controls in record.get("actual", {}).items():
                    for control in controls:
                        mark(f"project.generation_settings.{role}.{control}", "frozen_api", "pass", "Validated nested save/GET + restart")
        if record["case"] == "invalid_review_loop":
            mark("project.max_review_loops", "frozen_api", record["status"], "Invalid 99 accepted; next GET silently returns defaults")
        if record["case"] == "local_provider_catalog":
            mark("action.provider_catalog", "frozen_api", record["status"], "Real loopback custom /models transport")
        if record["case"] == "runtime_provider_payloads" and record.get("status") == "pass":
            for role in ("extractor", "drafter", "critic", "polisher", "chronicler"):
                for setting in (f"project.{role}_model", f"project.generation_settings.{role}.temperature"):
                    if setting in indexed:
                        indexed[setting]["runtime_evidence"] = "Frozen: captured selected model/temperature, completed metadata and output; source factory spy"

    for record in read_json("browser-results.json", []):
        mode = {"web-dev": "web_dev", "web-built": "web_built"}.get(record.get("mode"))
        if not mode:
            continue
        scenario = record["scenario"]
        fields = record.get("fields", [])
        if "accessib" in scenario.lower():
            # Aggregate accessibility results have no field-by-field association.
            continue
        if "preset" in scenario.lower() and record.get("status") == "fail":
            mark("action.apply_model_preset", mode, "fail", scenario)
            fields = ["scraper_model"]
        for field in fields:
            setting = field if field.startswith(("env.", "project.", "action.")) else "env." + field if field.isupper() else "project." + field
            if field == "logs":
                setting = "action.logs_refresh"
            elif field == "updates":
                setting = "action.check_updates"
            mark(setting, mode, record.get("status", "blocked"), scenario)
        if "clear" in scenario.lower() and "override" in scenario.lower():
            mark("action.clear_model_overrides", mode, record.get("status", "pass"), scenario)
        if "load-env" in scenario.lower():
            mark("action.load_env_presets", mode, record.get("status", "pass"), scenario)
            mark("action.clear_model_overrides", mode, record.get("status", "pass"), scenario)
        if "catalog" in scenario.lower():
            mark("action.provider_catalog", mode, record.get("status", "pass"), scenario)
        if scenario == "effective project model refresh after global save":
            mark("project.model_name", mode, record.get("status", "blocked"), scenario)

    for mode in ("native_dev", "native_release"):
        native = read_json(mode.replace("_", "-") + "-results.json", {})
        cdp = read_json(mode.replace("_", "-") + "-cdp-results.json", {})
        records = (native if isinstance(native, list) else native.get("observations", native.get("cases", []))) + cdp.get("observations", [])
        for record in records:
            settings = record.get("setting_ids", record.get("fields", []))
            if record.get("setting_id"):
                settings = [record["setting_id"]]
            for setting in settings:
                if setting not in indexed:
                    setting = "env." + setting if setting.isupper() else "project." + setting
                mark(setting, mode, record.get("status", "pass"), record.get("case", record.get("scenario", "Actual native UI observation")))

    for mode in MODES:
        children = [row for row in rows if row["scope"] == "project_generation"]
        if children and all(row[mode] == "pass" for row in children):
            mark("project.generation_settings", mode, "pass", "All six nested role objects independently persisted and verified")

    for setting, row in indexed.items():
        for mode in MODES:
            if row[mode] == "blocked":
                reasons[setting].append(mode + ": no independent completed per-setting observation")
        row["evidence"] = " | ".join(dict.fromkeys(evidence[setting]))
        row["blocked_reason"] = " | ".join(reasons[setting])
        row["logic_findings"] = "; ".join(dict.fromkeys(part.strip() for part in row["logic_findings"].split(";") if part.strip()))
    headers = list(rows[0])
    with (DATA / "setting-mode-matrix.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    summary = {mode: dict(Counter(row[mode] for row in rows)) for mode in MODES}
    write = DATA / "matrix-summary.json"
    write.write_text(json.dumps({"settings": len(rows), "modes": summary, "signoff": "FAIL: confirmed product defects and remaining blocked cells", "status_definition": "Worst individually observed scenario in that mode; a persistence pass is not a live-provider or complete runtime guarantee. Shared source defects are linked separately, not inferred as native UI observations."}, indent=2), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
