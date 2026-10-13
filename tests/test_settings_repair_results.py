"""Coverage generation must not turn incomplete evidence into signoff."""
import csv
import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def generator():
    path = Path(__file__).resolve().parents[1] / "scripts/audit/settings_repair_results.py"
    spec = importlib.util.spec_from_file_location("settings_repair_results", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fixtures(tmp_path):
    inventory = tmp_path / "historical.csv"
    headers = ["setting_id", "scope", "key", "ui_exposure", "notes", "evidence", "schema_default", "effective_default", "type", "constraints", "schema_ref", "inheritance_reset", "storage", "application_timing", "api_endpoint", "api_name"]
    entries = [
        ("project.title", "project", "title", "editable"),
        ("action.check_updates", "settings_action", "check_updates", "action"),
        ("env.NOVEL_PROCEDURAL_LEARNING_INTERVAL", "env_unexposed", "NOVEL_PROCEDURAL_LEARNING_INTERVAL", "schema-only"),
    ]
    with inventory.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        for setting, scope, key, exposure in entries:
            writer.writerow({"setting_id": setting, "scope": scope, "key": key, "ui_exposure": exposure, "notes": "old defect claim"})
    data = tmp_path / "repair"
    data.mkdir()
    return inventory, data


def test_missing_evidence_stays_blocked_and_original_unchanged(generator, fixtures):
    inventory, data = fixtures
    before = inventory.read_bytes()
    summary = generator.generate(inventory, data)
    assert summary["signoff"].startswith("INCOMPLETE")
    assert all(counts == {"blocked": 3} for counts in summary["modes"].values())
    assert inventory.read_bytes() == before
    with (data / "setting-inventory.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    procedural = next(row for row in rows if row["setting_id"].startswith("env."))
    assert procedural["scope"] == "env" and procedural["ui_exposure"] == "editable"
    assert all("old defect claim" not in row["notes"] for row in rows)


@pytest.mark.parametrize("record", [{"case": "valid_roundtrip", "setting_id": "project.title"}, {"status": "success"}, {"status": "pass", "setting_id": "project.unknown"}])
def test_invalid_evidence_stops_without_output(generator, fixtures, record):
    inventory, data = fixtures
    (data / "source-results.json").write_text(json.dumps([record]))
    with pytest.raises(ValueError):
        generator.generate(inventory, data)
    assert not (data / "matrix-summary.json").exists()


def test_failure_cannot_be_hidden_by_later_pass_and_not_inferred_other_modes(generator, fixtures):
    inventory, data = fixtures
    (data / "source-results.json").write_text(json.dumps([
        {"case": "failed", "status": "fail", "setting_id": "project.title"},
        {"case": "roundtrip", "status": "pass", "setting_id": "project.title"},
        {"case": "translation_start", "http_status": 200},
    ]))
    summary = generator.generate(inventory, data)
    assert summary["modes"]["source_api"]["fail"] == 1
    assert summary["modes"]["frozen_api"] == {"blocked": 3}
    assert summary["modes"]["native_dev"] == {"blocked": 3}


def test_junit_skips_and_failures_are_not_passes(generator, tmp_path):
    path = tmp_path / "junit.xml"
    path.write_text('<testsuite><testcase name="ok"/><testcase name="skipped"><skipped/></testcase><testcase name="bad"><failure/></testcase></testsuite>')
    assert generator.junit_cases(path) == {"ok": "pass", "skipped": "blocked", "bad": "fail"}


def test_source_results_cannot_masquerade_as_frozen(generator, fixtures):
    inventory, data = fixtures
    (data / "frozen-results.json").write_text(json.dumps([
        {"case": "isolated_environment", "status": "pass", "path": "audit/source-123/.env", "binary_sha256": "same"},
        {"case": "valid_roundtrip", "status": "pass", "setting_id": "project.title"},
    ]))
    with pytest.raises(ValueError, match="isolated frozen fixture"):
        generator.generate(inventory, data)


def test_frozen_pass_requires_matching_fresh_artifact(generator, fixtures):
    inventory, data = fixtures
    (data / "frozen-results.json").write_text(json.dumps([
        {"case": "isolated_environment", "status": "pass", "path": "audit/frozen-123/.env", "binary_sha256": "fresh"},
        {"case": "valid_roundtrip", "status": "pass", "setting_id": "project.title"},
    ]))
    assert generator.generate(inventory, data)["modes"]["frozen_api"] == {"blocked": 3}
    (data / "provenance.json").write_text(json.dumps({"repair_artifacts": {"frozen_backend": {"sha256": "other", "source_identity": "built from audited source"}}}))
    with pytest.raises(ValueError, match="provenance"):
        generator.generate(inventory, data)
    (data / "provenance.json").write_text(json.dumps({"repair_artifacts": {"frozen_backend": {"sha256": "fresh", "source_identity": "built from audited source"}}}))
    assert generator.generate(inventory, data)["modes"]["frozen_api"]["pass"] == 1
