"""Integrity checks for audit coverage: missing evidence must never yield a pass."""
import csv
import importlib.util
import json
from pathlib import Path


def load_merger(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / "scripts/audit/settings_results.py"
    spec = importlib.util.spec_from_file_location("settings_results_audit", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "DATA", tmp_path)
    rows = [
        {"setting_id": "env.NOVEL_MODEL", "scope": "env", "key": "NOVEL_MODEL", "type": "str", "ui_exposure": "editable"},
        {"setting_id": "env.NOVEL_QUALITY_THRESHOLD", "scope": "env", "key": "NOVEL_QUALITY_THRESHOLD", "type": "str", "ui_exposure": "editable"},
        {"setting_id": "project.title", "scope": "project", "key": "title", "type": "str", "ui_exposure": "editable"},
    ]
    with (tmp_path / "setting-inventory.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return module


def matrix(tmp_path):
    with (tmp_path / "setting-mode-matrix.csv").open(encoding="utf-8", newline="") as stream:
        return {row["setting_id"]: row for row in csv.DictReader(stream)}


def test_missing_or_failed_source_evidence_never_produces_pass(tmp_path, monkeypatch):
    merger = load_merger(tmp_path, monkeypatch)
    merger.main()
    assert all(row["source_api"] == "blocked" for row in matrix(tmp_path).values())
    (tmp_path / "backend-source-results.json").write_text(json.dumps({"tests": {"total": 3, "failures": 1, "errors": 0, "skipped": 0}, "covered_project_fields": ["title"]}), encoding="utf-8")
    merger.main()
    assert all(row["source_api"] == "blocked" for row in matrix(tmp_path).values())


def test_measured_shared_failures_are_mapped_and_cannot_be_overwritten(tmp_path, monkeypatch):
    merger = load_merger(tmp_path, monkeypatch)
    (tmp_path / "backend-source-results.json").write_text(json.dumps({
        "tests": {"total": 3, "failures": 0, "errors": 0, "skipped": 0},
        "covered_project_fields": ["title"],
        "confirmed_findings": [
            {"id": "B05", "fields": ["all environment-derived model/generation values"], "defect": "Measured model leakage"},
            {"id": "B13", "fields": ["all global settings"], "defect": "Measured loops/threshold partial write"},
            {"id": "B14", "fields": ["all project settings"], "defect": "Measured stale title overwrite"},
        ],
    }), encoding="utf-8")
    (tmp_path / "browser-results.json").write_text(json.dumps([
        {"mode": "web-dev", "scenario": "blank value", "fields": ["title"], "status": "fail"},
        {"mode": "web-dev", "scenario": "valid title", "fields": ["title"], "status": "pass"},
    ]), encoding="utf-8")
    merger.main()
    rows = matrix(tmp_path)
    assert rows["env.NOVEL_MODEL"]["source_api"] == "fail"
    assert rows["env.NOVEL_QUALITY_THRESHOLD"]["source_api"] == "fail"
    assert rows["project.title"]["source_api"] == rows["project.title"]["web_dev"] == "fail"
    assert rows["project.title"]["native_release"] == "blocked"
